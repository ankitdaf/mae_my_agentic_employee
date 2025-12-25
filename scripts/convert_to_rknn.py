#!/usr/bin/env python3
"""Convert trained MobileBERT model to RKNN format"""

# Apply ONNX compatibility patch for RKNN Toolkit 2.3.2
import sys
from pathlib import Path
import onnx
import numpy as np
from onnx import TensorProto

# Patch onnx.mapping for newer ONNX versions (removed in ONNX 1.15.0)
if not hasattr(onnx, "mapping"):
    class Mapping:
        pass
    onnx.mapping = Mapping()
    onnx.mapping.TENSOR_TYPE_TO_NP_TYPE = {
        TensorProto.FLOAT: np.dtype("float32"),
        TensorProto.BOOL: np.dtype("bool"),
        TensorProto.INT32: np.dtype("int32"),
        TensorProto.INT64: np.dtype("int64"),
        TensorProto.STRING: np.dtype("object"),
        TensorProto.INT8: np.dtype("int8"),
        TensorProto.UINT8: np.dtype("uint8"),
        TensorProto.FLOAT16: np.dtype("float16"),
        TensorProto.DOUBLE: np.dtype("float64"),
        TensorProto.UINT32: np.dtype("uint32"),
        TensorProto.UINT64: np.dtype("uint64"),
    }
    onnx.mapping.NP_TYPE_TO_TENSOR_TYPE = {
        np.dtype("float32"): TensorProto.FLOAT,
        np.dtype("bool"): TensorProto.BOOL,
        np.dtype("int32"): TensorProto.INT32,
        np.dtype("int64"): TensorProto.INT64,
        np.dtype("object"): TensorProto.STRING,
        np.dtype("int8"): TensorProto.INT8,
        np.dtype("uint8"): TensorProto.UINT8,
        np.dtype("float16"): TensorProto.FLOAT16,
        np.dtype("float64"): TensorProto.DOUBLE,
        np.dtype("uint32"): TensorProto.UINT32,
        np.dtype("uint64"): TensorProto.UINT64,
    }

sys.path.insert(0, str(Path(__file__).parent))
from rknn.api import RKNN
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import json

print("="*60)
print("MobileBERT to RKNN Conversion Script")
print("="*60)

# Load trained model
print("\n[1/7] Loading trained model...")
model_path = "./models/email_classifier_pytorch"
try:
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model.eval()
    print("✓ Model loaded successfully")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    print("\nMake sure you've trained the model first:")
    print("  python train_email_classifier.py --dataset training_data/email_dataset_*.json")
    sys.exit(1)

# Prepare dummy input for ONNX export
print("\n[2/7] Preparing sample input...")
sample_text = "[SUBJECT] Test email [SENDER] Test <test@example.com> [BODY] This is a test email body."
inputs = tokenizer(
    sample_text,
    padding="max_length",
    truncation=True,
    max_length=384,
    return_tensors="pt"
)
print("✓ Sample input prepared")

# Export to ONNX
print("\n[3/7] Exporting to ONNX...")
try:
    # Convert inputs to int32 (RKNN doesn't support int64)
    inputs_int32 = {
        'input_ids': inputs['input_ids'].to(torch.int32),
        'attention_mask': inputs['attention_mask'].to(torch.int32)
    }
    
    torch.onnx.export(
        model,
        (inputs_int32['input_ids'], inputs_int32['attention_mask']),
        "./models/email_classifier.onnx",
        input_names=['input_ids', 'attention_mask'],
        output_names=['logits'],
        dynamic_axes={
            'input_ids': {0: 'batch'},
            'attention_mask': {0: 'batch'}
        },
        opset_version=11,  # Use opset 11 for better RKNN compatibility
        do_constant_folding=True
    )
    print("✓ ONNX export complete")
except Exception as e:
    print(f"✗ ONNX export failed: {e}")
    sys.exit(1)

# Prepare calibration dataset for quantization
print("\n[4/7] Preparing calibration dataset...")
try:
    with open('data/training/email_dataset_20251207_001715.json', 'r') as f:
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
    
    # Tokenize and save as numpy arrays (use int32 for RKNN compatibility)
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
            inputs['input_ids'].astype(np.int32),  # int32 instead of int64
            inputs['attention_mask'].astype(np.int32)  # int32 instead of int64
        ])
    
    # Save calibration data
    np.save('./models/calibration_data.npy', calibration_data)
    print(f"✓ Calibration dataset prepared ({len(calibration_data)} samples)")
except Exception as e:
    print(f"✗ Failed to prepare calibration data: {e}")
    sys.exit(1)

# Convert ONNX to RKNN
print("\n[5/7] Converting to RKNN...")
rknn = RKNN()

# Config for RKNN Toolkit 2.3.2
rknn.config(
    target_platform='rk3566',
    optimization_level=3,
    output_optimize=True
)

# Load ONNX with fixed input shapes (RKNN doesn't support dynamic batch)
ret = rknn.load_onnx(
    model='./models/email_classifier.onnx',
    inputs=['input_ids', 'attention_mask'],
    input_size_list=[[1, 384], [1, 384]]  # Fixed batch size of 1
)
if ret != 0:
    print('✗ Load ONNX model failed!')
    sys.exit(ret)

print("✓ ONNX model loaded")

# Build with quantization
print("\n[6/7] Building RKNN model...")
print("(This may take several minutes...)")
print("Note: Quantization disabled for integer input model")
ret = rknn.build(
    do_quantization=False  # Disable quantization for integer inputs
)
if ret != 0:
    print('✗ Build RKNN model failed!')
    sys.exit(ret)

print("✓ RKNN model built")

# Export
ret = rknn.export_rknn('./models/email_classifier.rknn')
if ret != 0:
    print('✗ Export RKNN model failed!')
    sys.exit(ret)

print("✓ RKNN model exported successfully!")

# Test the model
print("\n[7/7] Testing RKNN model...")
ret = rknn.init_runtime()
if ret != 0:
    print('✗ Init runtime failed!')
    sys.exit(ret)

# Test inference
test_cases = [
    "[SUBJECT] Invoice from Amazon [SENDER] Amazon <no-reply@amazon.com> [BODY] Your order has been shipped.",
    "[SUBJECT] Weekly Newsletter [SENDER] TechCrunch <newsletter@techcrunch.com> [BODY] Here are this week's top stories.",
    "[SUBJECT] 50% OFF Sale [SENDER] Shop <marketing@shop.com> [BODY] Limited time offer! Buy now.",
    "[SUBJECT] Meeting tomorrow [SENDER] John <john@company.com> [BODY] Can we meet at 3pm?"
]

class_names = ['transactions', 'feed', 'promotions', 'inbox']

print("\nTest predictions:")
for i, test_text in enumerate(test_cases, 1):
    test_inputs = tokenizer(
        test_text,
        padding="max_length",
        truncation=True,
        max_length=384,
        return_tensors="np"
    )
    
    outputs = rknn.inference(inputs=[
        test_inputs['input_ids'].astype(np.int32),
        test_inputs['attention_mask'].astype(np.int32)
    ])
    
    # Get prediction
    logits = outputs[0][0]
    predicted_class = np.argmax(logits)
    confidence = np.exp(logits) / np.sum(np.exp(logits))  # Softmax
    
    print(f"\n  Test {i}: {class_names[predicted_class]} (confidence: {confidence[predicted_class]:.2%})")
    print(f"    Subject: {test_text.split('[SENDER]')[0].replace('[SUBJECT]', '').strip()[:50]}...")

rknn.release()

# Save tokenizer config separately
print("\n[Final] Saving tokenizer config...")
tokenizer.save_pretrained("./models/tokenizer")

print("\n" + "="*60)
print("✓ Conversion complete!")
print("="*60)
print("\nFiles ready for deployment:")
print("  - models/email_classifier.rknn")
print("  - models/tokenizer/")
print("\nNext steps:")
print("  1. Transfer to RK3566:")
print("     scp models/email_classifier.rknn <user>@<ip-address>:/path/to/mae/models/")
print("     scp -r models/tokenizer <user>@<ip-address>:/path/to/mae/models/")
print("  2. Update config on RK3566 (classification.use_ai_model: true)")
print("  3. Test: python scripts/test_classification.py")
