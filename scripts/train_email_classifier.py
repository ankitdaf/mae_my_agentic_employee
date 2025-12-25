#!/usr/bin/env python3
"""
Train Email Classifier using MobileBERT

Fine-tunes google/mobilebert-uncased on email classification dataset.
Uses concatenation with special separators: [SUBJECT] [SENDER] [BODY]

Usage:
    python scripts/train_email_classifier.py --dataset data/email_dataset_<timestamp>.json
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, List
import sys

# Force safetensors usage to avoid torch.load vulnerability
os.environ['SAFETENSORS_FAST_GPU'] = '1'
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '0'

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback
)
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prepare_input(email: Dict) -> str:
    """
    Prepare model input by concatenating fields with special separators
    
    Format: [SUBJECT] {subject} [SENDER] {sender} [BODY] {body}
    
    Args:
        email: Email dictionary with subject, sender_name, sender_email, body_text
    
    Returns:
        Concatenated input string
    """
    subject = email.get('subject', '')
    sender_name = email.get('sender_name', '')
    sender_email = email.get('sender_email', '')
    sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    body = email.get('body_text', '')[:1000]  # Limit body length
    
    # Concatenate with special separators
    input_text = f"[SUBJECT] {subject} [SENDER] {sender} [BODY] {body}"
    
    return input_text


def load_dataset(dataset_path: Path) -> List[Dict]:
    """
    Load email dataset from JSON or CSV file
    
    Args:
        dataset_path: Path to dataset file (.json or .csv)
    
    Returns:
        List of email dictionaries
    """
    logger.info(f"Loading dataset from {dataset_path}...")
    
    emails = []
    
    if dataset_path.suffix.lower() == '.json':
        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        emails = data['emails']
        if 'metadata' in data and 'by_label' in data['metadata']:
            logger.info(f"  By label: {data['metadata']['by_label']}")
            
    elif dataset_path.suffix.lower() == '.csv':
        import csv
        with open(dataset_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Ensure required fields exist and label is present
                if 'label' in row and row['label']:
                    emails.append(row)
                    
        # Count labels for logging
        label_counts = {}
        for email in emails:
            label = email.get('label')
            label_counts[label] = label_counts.get(label, 0) + 1
        logger.info(f"  By label: {label_counts}")
        
    else:
        raise ValueError(f"Unsupported file format: {dataset_path.suffix}")
    
    logger.info(f"✓ Loaded {len(emails)} emails")
    
    return emails


def prepare_datasets(emails: List[Dict], train_split: float = 0.8):
    """
    Prepare training and validation datasets
    
    Args:
        emails: List of email dictionaries
        train_split: Fraction of data to use for training
    
    Returns:
        Tuple of (train_dataset, val_dataset)
    """
    logger.info("Preparing datasets...")
    
    # Map labels to integers
    label_map = {'transactions': 0, 'feed': 1, 'promotions': 2, 'inbox': 3}
    
    # Prepare data
    prepared_data = [
        {
            "text": prepare_input(email),
            "label": label_map[email['label']]
        }
        for email in emails
    ]
    
    # Shuffle
    np.random.seed(42)
    np.random.shuffle(prepared_data)
    
    # Split
    split_idx = int(len(prepared_data) * train_split)
    train_data = prepared_data[:split_idx]
    val_data = prepared_data[split_idx:]
    
    logger.info(f"✓ Split dataset:")
    logger.info(f"  Training: {len(train_data)} emails")
    logger.info(f"  Validation: {len(val_data)} emails")
    
    # Create HuggingFace datasets
    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data)
    
    return train_dataset, val_dataset


def tokenize_datasets(train_dataset, val_dataset, tokenizer, max_length: int = 384):
    """
    Tokenize datasets
    
    Args:
        train_dataset: Training dataset
        val_dataset: Validation dataset
        tokenizer: HuggingFace tokenizer
        max_length: Maximum sequence length
    
    Returns:
        Tuple of (tokenized_train, tokenized_val)
    """
    logger.info("Tokenizing datasets...")
    
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=max_length
        )
    
    tokenized_train = train_dataset.map(tokenize_function, batched=True)
    tokenized_val = val_dataset.map(tokenize_function, batched=True)
    
    logger.info("✓ Tokenization complete")
    
    return tokenized_train, tokenized_val


def compute_metrics(eval_pred):
    """
    Compute evaluation metrics
    
    Args:
        eval_pred: Tuple of (predictions, labels)
    
    Returns:
        Dictionary of metrics
    """
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


def remove_pytorch_bin_files(model_name: str):
    """
    Remove .bin files from HuggingFace cache for a specific model
    
    This forces the model to load from safetensors files only,
    avoiding the torch.load vulnerability in PyTorch < 2.6
    
    Args:
        model_name: Model name (e.g., 'google/mobilebert-uncased')
    """
    from pathlib import Path
    import shutil
    
    # HuggingFace cache directory
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    
    if not cache_dir.exists():
        return
    
    # Convert model name to cache directory format
    # e.g., "google/mobilebert-uncased" -> "models--google--mobilebert-uncased"
    cache_model_name = "models--" + model_name.replace("/", "--")
    
    # Find matching cache directories
    model_dirs = list(cache_dir.glob(f"{cache_model_name}*"))
    
    for model_dir in model_dirs:
        # Find all .bin files
        bin_files = list(model_dir.rglob("*.bin"))
        
        if bin_files:
            logger.info(f"Removing {len(bin_files)} .bin file(s) from cache to force safetensors loading...")
            for bin_file in bin_files:
                try:
                    bin_file.unlink()
                    logger.info(f"  ✓ Removed {bin_file.name}")
                except Exception as e:
                    logger.warning(f"  ✗ Could not remove {bin_file.name}: {e}")


def train_model(
    train_dataset,
    val_dataset,
    output_dir: Path,
    num_epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 2e-5,
    model_name: str = "google/mobilebert-uncased"
):
    """
    Train MobileBERT model
    
    Args:
        train_dataset: Tokenized training dataset
        val_dataset: Tokenized validation dataset
        output_dir: Output directory for model
        num_epochs: Number of training epochs
        batch_size: Training batch size
        learning_rate: Learning rate
        model_name: Base model to train from
    """
    logger.info("Initializing model...")
    
    # Load pre-trained MobileBERT
    # model_name is passed as argument
    
    # Remove any cached .bin files to force safetensors loading
    remove_pytorch_bin_files(model_name)
    
    logger.info(f"Loading tokenizer from {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        use_fast=True
    )
    
    logger.info(f"Loading model from {model_name}...")
    try:
        # Try loading with safetensors only
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=4,  # transactions, feed, promotions, inbox
            use_safetensors=True,  # Force safetensors to avoid torch.load vulnerability
            ignore_mismatched_sizes=True,  # Allow loading with different num_labels
        )
    except (ValueError, OSError) as e:
        if "torch.load" in str(e) or "weights_only" in str(e):
            logger.error("\n" + "="*60)
            logger.error("ERROR: PyTorch version too old for torch.load")
            logger.error("="*60)
            logger.error("\nThe cached model files are in PyTorch format (.bin)")
            logger.error("which requires PyTorch >= 2.6 to load safely.")
            logger.error("\nSOLUTION: Clear the cache and re-download with safetensors:")
            logger.error("\n  python scripts/clear_model_cache.py")
            logger.error("\nThen run this script again.")
            logger.error("="*60)
            raise
        else:
            raise
    
    logger.info(f"✓ Loaded {model_name}")
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir=str(output_dir / "logs"),
        logging_steps=50,
        warmup_steps=100,
        fp16=False,  # Set to True if you have GPU with FP16 support
    )
    
    # Tokenize datasets
    tokenized_train, tokenized_val = tokenize_datasets(
        train_dataset, val_dataset, tokenizer
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_val,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )
    
    # Train
    logger.info("\n" + "="*60)
    logger.info("Starting training...")
    logger.info("="*60)
    
    trainer.train()
    
    logger.info("\n✓ Training complete!")
    
    # Evaluate
    logger.info("\nEvaluating model...")
    results = trainer.evaluate()
    
    logger.info("\n" + "="*60)
    logger.info("VALIDATION RESULTS")
    logger.info("="*60)
    logger.info(f"Accuracy:  {results['eval_accuracy']:.2%}")
    logger.info(f"Precision: {results['eval_precision']:.2%}")
    logger.info(f"Recall:    {results['eval_recall']:.2%}")
    logger.info(f"F1 Score:  {results['eval_f1']:.2%}")
    logger.info("="*60)
    
    # Save model and tokenizer
    logger.info(f"\nSaving model to {output_dir}...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("✓ Model and tokenizer saved!")
    
    # Compute confusion matrix
    predictions = trainer.predict(tokenized_val)
    pred_labels = predictions.predictions.argmax(axis=-1)
    true_labels = predictions.label_ids
    
    cm = confusion_matrix(true_labels, pred_labels)
    class_names = ['transactions', 'feed', 'promotions', 'inbox']
    
    logger.info("\nConfusion Matrix:")
    logger.info("                  Predicted")
    logger.info("                  " + "  ".join(f"{c[:4]:>4}" for c in class_names))
    for i, row in enumerate(cm):
        logger.info(f"Actual {class_names[i][:4]:>4}  " + "  ".join(f"{v:>4}" for v in row))
    
    return model, tokenizer


def main():
    parser = argparse.ArgumentParser(description='Train email classification model')
    parser.add_argument(
        '--dataset',
        type=Path,
        required=True,
        help='Path to email dataset JSON file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('models/email_classifier_pytorch'),
        help='Output directory for trained model'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=3,
        help='Number of training epochs'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=8,
        help='Training batch size'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=2e-5,
        help='Learning rate'
    )
    parser.add_argument(
        '--base-model',
        type=str,
        default="google/mobilebert-uncased",
        help='Base model to train from (HuggingFace ID or local path)'
    )
    parser.add_argument(
        '--train-split',
        type=float,
        default=0.8,
        help='Fraction of data to use for training (rest for validation)'
    )
    
    args = parser.parse_args()
    
    # Validate dataset path
    if not args.dataset.exists():
        logger.error(f"Dataset not found: {args.dataset}")
        sys.exit(1)
        
    try:
        # Load dataset
        emails = load_dataset(args.dataset)
        
        # Prepare datasets
        train_dataset, val_dataset = prepare_datasets(emails, args.train_split)
        
        # Train model
        model, tokenizer = train_model(
            train_dataset,
            val_dataset,
            args.output,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            model_name=args.base_model
        )
        
        logger.info("\n" + "="*60)
        logger.info("✓ Training complete!")
        logger.info("="*60)
        logger.info(f"\nModel saved to: {args.output}")
        logger.info("\nNext steps:")
        logger.info("  1. Convert to RKNN: python scripts/convert_to_rknn.py")
        logger.info("  2. Transfer to RK3566:")
        logger.info(f"     scp models/email_classifier.rknn <user>@<ip-address>:/path/to/mae/models/")
        logger.info(f"     scp -r models/tokenizer <user>@<ip-address>:/path/to/mae/models/")
    
    except KeyboardInterrupt:
        logger.info("\n\nTraining interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
