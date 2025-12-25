# NPU-Accelerated Email Classification Setup

This guide explains how to train, convert, and deploy a MobileBERT model for email classification on the RK3566's NPU.

## Overview

- **Model**: MobileBERT (lightweight BERT variant)
- **Hardware**: RK3566 NPU (1 TOPS)
- **Framework**: RKNN Toolkit 2 (development) + RKNN Toolkit Lite 2 (deployment)
- **Task**: 4-class classification (Transactions, Feed, Promotions, Inbox)

## Two-Machine Setup

This setup requires **two machines**:

1. **Development Machine (Your Laptop)**: Train and convert the model
   - OS: Linux/macOS/Windows (x86_64)
   - RKNN Toolkit 2 (full version)
   - PyTorch/TensorFlow for training

2. **Deployment Device (RK3566)**: Run inference on NPU
   - OS: Linux (aarch64)
   - RKNN Toolkit Lite 2 (inference only)
   - Headless server

---

# Part 1: Development Machine Setup (Laptop)

## Prerequisites

- Python 3.8-3.10 (RKNN Toolkit 2 compatibility)
- pip and virtualenv
- Git

## Step 1: Install RKNN Toolkit 2 (Full Version)

On your **laptop**:

```bash
# Create virtual environment
python3 -m venv ~/venv-rknn
source ~/venv-rknn/bin/activate

# Download RKNN Toolkit 2 (x86_64 version)
wget https://github.com/rockchip-linux/rknn-toolkit2/releases/download/v1.6.0/rknn_toolkit2-1.6.0+81f21f4d-cp38-cp38-linux_x86_64.whl

# Install (adjust for your Python version)
pip install rknn_toolkit2-1.6.0+81f21f4d-cp38-cp38-linux_x86_64.whl

# Install dependencies
pip install torch torchvision transformers datasets numpy onnx
```

Verify installation:
```bash
python3 -c "from rknn.api import RKNN; print('RKNN Toolkit 2 installed successfully')"
```

## Step 2: Prepare Training Data

You need labeled email data for training. Options:

### Option A: Use Existing Dataset

Download a pre-labeled email dataset:
- **Enron Email Dataset** (labeled)
- **SpamAssassin Public Corpus**
- **Kaggle Email Classification datasets**

### Option B: Label Your Own Emails

Create a simple labeling script:

```python
# scripts/label_emails.py
import json
from pathlib import Path

def label_email(subject, body_preview):
    print(f"\nSubject: {subject}")
    print(f"Body: {body_preview[:200]}...")
    print("\n1: Transactions")
    print("2: Feed")
    print("3: Promotions")
    print("4: Inbox")
    
    while True:
        choice = input("Label (1/2/3/4): ").strip()
        if choice in ['1', '2', '3', '4']:
            labels = {'1': 'transactions', '2': 'feed', '3': 'promotions', '4': 'inbox'}
            return labels[choice]

# Use with your cached emails
```

### Option C: Use Pre-trained Model (Recommended for Quick Start)

Use a pre-trained text classification model and fine-tune it:
- **distilbert-base-uncased** (smaller, faster)
- **MobileBERT** (optimized for mobile/edge)

## Step 3: Fine-tune MobileBERT

**On your laptop** (with RKNN Toolkit 2 installed):

```python
# scripts/train_email_classifier.py
from transformers import (
    AutoModelForSequenceClassification, 
    AutoTokenizer, 
    Trainer, 
    TrainingArguments,
    DataCollatorWithPadding
)
from datasets import Dataset
import json
import torch

# Load your dataset
with open('data/email_dataset_<timestamp>.json', 'r') as f:
    data = json.load(f)

# Prepare training data with concatenated inputs
# Format: [SUBJECT] {subject} [SENDER] {sender} [BODY] {body}
def prepare_input(email):
    subject = email.get('subject', '')
    sender = f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>"
    body = email.get('body_text', '')[:1000]  # Limit body length
    
    return f"[SUBJECT] {subject} [SENDER] {sender} [BODY] {body}"

# Map labels to integers
label_map = {'transactions': 0, 'feed': 1, 'promotions': 2, 'inbox': 3}

train_data = [
    {
        "text": prepare_input(email),
        "label": label_map[email['label']]
    }
    for email in data['emails']
]

# Split into train/validation (80/20)
split_idx = int(len(train_data) * 0.8)
train_dataset = Dataset.from_list(train_data[:split_idx])
val_dataset = Dataset.from_list(train_data[split_idx:])

# Load pre-trained MobileBERT and tokenizer
model_name = "google/mobilebert-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(
    model_name, 
    num_labels=4  # transactions, feed, promotions, inbox
)

# Tokenize datasets
def tokenize_function(examples):
    return tokenizer(
        examples["text"], 
        padding="max_length", 
        truncation=True, 
        max_length=384  # Increased for concatenated inputs
    )

tokenized_train = train_dataset.map(tokenize_function, batched=True)
tokenized_val = val_dataset.map(tokenize_function, batched=True)

# Training arguments
training_args = TrainingArguments(
    output_dir="./models/email_classifier",
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=16,
    learning_rate=2e-5,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="accuracy",
    logging_dir="./logs",
)

# Define metrics
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = predictions.argmax(axis=-1)
    
    accuracy = accuracy_score(labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average='weighted'
    )
    
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1
    }

# Train
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_val,
    compute_metrics=compute_metrics,
)

print("Starting training...")
trainer.train()

# Save model and tokenizer
model.save_pretrained("./models/email_classifier_pytorch")
tokenizer.save_pretrained("./models/email_classifier_pytorch")

print("\n✓ Model and tokenizer saved to ./models/email_classifier_pytorch")

# Evaluate
results = trainer.evaluate()
print(f"\nValidation Results:")
print(f"  Accuracy: {results['eval_accuracy']:.2%}")
print(f"  F1 Score: {results['eval_f1']:.2%}")
```

**Run training**:

```bash
# On your laptop
cd ~/path/to/mae-project
source ~/venv-rknn/bin/activate

python scripts/train_email_classifier.py
```

Expected training time: 30-60 minutes (depending on dataset size and hardware).

## Step 4: Convert Model to RKNN Format

On your development machine (laptop):

```python
# scripts/convert_to_rknn.py
from rknn.api import RKNN
import torch
import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import json

# Load your trained PyTorch model
model_path = "./models/email_classifier_pytorch"
model = AutoModelForSequenceClassification.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

model.eval()

# Prepare dummy input for ONNX export
sample_text = "[SUBJECT] Test email [SENDER] Test <test@example.com> [BODY] This is a test email body."
inputs = tokenizer(
    sample_text,
    padding="max_length",
    truncation=True,
    max_length=384,
    return_tensors="pt"
)

# Export to ONNX
print("Exporting to ONNX...")
torch.onnx.export(
    model,
    (inputs['input_ids'], inputs['attention_mask']),
    "./models/email_classifier.onnx",
    input_names=['input_ids', 'attention_mask'],
    output_names=['logits'],
    dynamic_axes={
        'input_ids': {0: 'batch'},
        'attention_mask': {0: 'batch'}
    },
    opset_version=12
)

print("✓ ONNX export complete")

# Prepare calibration dataset for quantization
# Use a subset of your training data
print("Preparing calibration dataset...")
with open('data/email_dataset_<timestamp>.json', 'r') as f:
    data = json.load(f)

# Take 100 samples for calibration
calibration_samples = data['emails'][:100]

# Prepare calibration data
def prepare_input(email):
    subject = email.get('subject', '')
    sender = f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>"
    body = email.get('body_text', '')[:1000]
    return f"[SUBJECT] {subject} [SENDER] {sender} [BODY] {body}"

calibration_texts = [prepare_input(email) for email in calibration_samples]

# Tokenize and save as numpy arrays
calibration_data = []
for text in calibration_texts:
    inputs = tokenizer(
        text,
        padding="max_length",
        truncation=True,
        max_length=384,
        return_tensors="np"
    )
    calibration_data.append([
        inputs['input_ids'].astype(np.int64),
        inputs['attention_mask'].astype(np.int64)
    ])

# Save calibration data
np.save('./models/calibration_data.npy', calibration_data)

print("✓ Calibration dataset prepared")

# Convert ONNX to RKNN
print("Converting to RKNN...")
rknn = RKNN()

# Config
rknn.config(
    target_platform='rk3566',
    optimization_level=3,
    quantize_input_node=True,
    output_optimize=1
)

# Load ONNX
ret = rknn.load_onnx(model='./models/email_classifier.onnx')
if ret != 0:
    print('✗ Load ONNX model failed!')
    exit(ret)

print("✓ ONNX model loaded")

# Build with quantization
print("Building RKNN model with INT8 quantization...")
ret = rknn.build(
    do_quantization=True,
    dataset='./models/calibration_data.npy'
)
if ret != 0:
    print('✗ Build RKNN model failed!')
    exit(ret)

print("✓ RKNN model built")

# Export
ret = rknn.export_rknn('./models/email_classifier.rknn')
if ret != 0:
    print('✗ Export RKNN model failed!')
    exit(ret)

print("✓ RKNN model exported successfully!")

# Test the model
print("\nTesting RKNN model...")
ret = rknn.init_runtime()
if ret != 0:
    print('✗ Init runtime failed!')
    exit(ret)

# Test inference
test_text = "[SUBJECT] Invoice from Amazon [SENDER] Amazon <no-reply@amazon.com> [BODY] Your order has been shipped."
test_inputs = tokenizer(
    test_text,
    padding="max_length",
    truncation=True,
    max_length=384,
    return_tensors="np"
)

outputs = rknn.inference(inputs=[
    test_inputs['input_ids'].astype(np.int64),
    test_inputs['attention_mask'].astype(np.int64)
])

# Get prediction
logits = outputs[0][0]
predicted_class = np.argmax(logits)
class_names = ['transactions', 'feed', 'promotions', 'inbox']

print(f"Test prediction: {class_names[predicted_class]}")
print(f"Logits: {logits}")

rknn.release()

# Save tokenizer config separately
print("\nSaving tokenizer config...")
tokenizer.save_pretrained("./models/tokenizer")

print("\n✓ All done! Files ready for deployment:")
print("  - models/email_classifier.rknn")
print("  - models/tokenizer/")
```

**Run conversion**:

```bash
# On your laptop
cd ~/path/to/mae-project
source ~/venv-rknn/bin/activate

python scripts/convert_to_rknn.py
```

---

# Part 2: RK3566 Deployment (Device)

## Prerequisites

- RK3566 device with Linux (aarch64)
- SSH access to device
- Python 3.8+

## Step 1: Install RKNN Toolkit Lite

SSH into your **RK3566 device**:

```bash
ssh <user>@<ip-address>
cd /path/to/mae
```

Install RKNN Toolkit Lite (inference only):

```bash
# Download RKNN Toolkit Lite (aarch64 version)
wget https://github.com/rockchip-linux/rknn-toolkit2/releases/download/v1.6.0/rknn_toolkit_lite2-1.6.0-cp313-cp313-linux_aarch64.whl

# Install (adjust for your Python version)
pip install rknn_toolkit_lite2-*.whl
```

Verify installation:
```bash
python3 -c "from rknnlite.api import RKNNLite; print('RKNN Lite installed successfully')"
```

## Step 2: Transfer Model and Tokenizer from Laptop

From your **laptop** (after completing Part 1):

```bash
# Transfer RKNN model
scp models/email_classifier.rknn <user>@<ip-address>:/path/to/mae/models/

# Transfer tokenizer directory
scp -r models/tokenizer <user>@<ip-address>:/path/to/mae/models/
```

## Step 3: Update Configuration

On **RK3566**, edit `config/agents/personal.yaml`:

```yaml
classification:
  topics_i_care_about:
    - "finance"
    - "taxes"
    - "stocks"
  use_ai_model: true  # Enable AI model
  model_path: "models/email_classifier.rknn"
  tokenizer_path: "models/tokenizer"  # Directory containing tokenizer files
  max_length: 384  # Max tokens for input (increased for concatenated fields)
```

## Step 4: Test the Model

On **RK3566**:

```bash
ssh <user>@<ip-address>
cd /path/to/mae
source venv/bin/activate

# Test classification
python -c "
from src.agents.classifier import EmailClassifier
from pathlib import Path

classifier = EmailClassifier(
    model_path=Path('models/email_classifier.rknn'),
    use_model=True,
    agent_name='test'
)

test_email = {
    'subject': 'URGENT: Action required',
    'body_text': 'Please verify your account immediately.'
}

result = classifier.classify(test_email)
print(f'Category: {result[\"category\"]}')
print(f'Confidence: {result[\"confidence\"]:.2f}')
print(f'Method: {result[\"method\"]}')
"
```

## Quick Start: Use Pre-converted Model (Easiest)

If you want to skip training and just test the NPU:

1. Download a pre-converted RKNN model (if available from Rockchip examples)
2. Or use the rule-based classifier initially and add AI later

## Performance Expectations

- **Inference Time**: ~50-100ms per email (on NPU)
- **Memory Usage**: ~100-200MB for model
- **Accuracy**: 85-95% (depends on training data quality)

## Troubleshooting

### "rknnlite not found"
```bash
pip install rknn_toolkit_lite2-*.whl
```

### "Model load failed"
- Check model path is correct
- Verify RKNN model was converted for rk3566 platform
- Check file permissions

### "Out of memory"
- Reduce max_length in config (try 64 instead of 128)
- Use quantized model (INT8 instead of FP16)

## Next Steps

1. Start with rule-based classification (current setup)
2. Collect and label ~1000-5000 emails
3. Train/fine-tune MobileBERT
4. Convert to RKNN
5. Deploy and test
6. Iterate and improve

## Resources

- [RKNN Toolkit 2 Documentation](https://github.com/rockchip-linux/rknn-toolkit2)
- [MobileBERT Paper](https://arxiv.org/abs/2004.02984)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
