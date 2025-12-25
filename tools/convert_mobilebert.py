"""
MobileBERT to RKNN Conversion Script

Run this on an x86 Ubuntu PC with rknn-toolkit2 installed.
This script converts MobileBERT from Hugging Face to RKNN format for RK3566.

Requirements:
    pip install rknn-toolkit2 transformers torch onnx

Usage:
    python convert_mobilebert.py
"""
import os
import torch
import numpy as np
from transformers import MobileBertForSequenceClassification, MobileBertTokenizer
from rknn.api import RKNN


def export_to_onnx(model, tokenizer, output_path="mobilebert.onnx"):
    """Export MobileBERT to ONNX format"""
    print("Exporting model to ONNX...")
    
    # Set model to eval mode
    model.eval()
    
    # Create dummy input
    dummy_text = "This is a sample email for testing."
    inputs = tokenizer(
        dummy_text,
        padding='max_length',
        truncation=True,
        max_length=128,
        return_tensors='pt'
    )
    
    # Export to ONNX
    torch.onnx.export(
        model,
        (inputs['input_ids'], inputs['attention_mask']),
        output_path,
        input_names=['input_ids', 'attention_mask'],
        output_names=['logits'],
        dynamic_axes={
            'input_ids': {0: 'batch_size'},
            'attention_mask': {0: 'batch_size'}
        },
        opset_version=11
    )
    
    print(f"ONNX model saved to {output_path}")


def convert_to_rknn(onnx_path="mobilebert.onnx", output_path="mobilebert.rknn"):
    """Convert ONNX model to RKNN format"""
    print("Converting ONNX to RKNN...")
    
    # Create RKNN object
    rknn = RKNN(verbose=True)
    
    # Config for RK3566
    print("Configuring for RK3566 target...")
    rknn.config(
        target_platform='rk3566',
        quantized_dtype='asymmetric_quantized-8',
        optimization_level=3,
        mean_values=[[0, 0, 0]],
        std_values=[[1, 1, 1]]
    )
    
    # Load ONNX model
    print(f"Loading ONNX model from {onnx_path}...")
    ret = rknn.load_onnx(model=onnx_path)
    if ret != 0:
        print(f"Load ONNX failed! ret={ret}")
        return False
    
    # Build model with quantization
    print("Building RKNN model (this may take a few minutes)...")
    
    # Create dataset for quantization (sample inputs)
    # In production, use real email samples
    dataset_path = create_quantization_dataset()
    
    ret = rknn.build(do_quantization=True, dataset=dataset_path)
    if ret != 0:
        print(f"Build failed! ret={ret}")
        return False
    
    # Export RKNN model
    print(f"Exporting RKNN model to {output_path}...")
    ret = rknn.export_rknn(output_path)
    if ret != 0:
        print(f"Export failed! ret={ret}")
        return False
    
    print(f"RKNN model saved to {output_path}")
    
    # Release
    rknn.release()
    
    return True


def create_quantization_dataset(num_samples=100):
    """Create dataset for quantization calibration"""
    print("Creating quantization dataset...")
    
    dataset_path = "quantization_dataset.txt"
    
    # Generate random sample data
    # In production, use real email text samples
    sample_texts = [
        "Important meeting tomorrow at 10am",
        "Your invoice is attached",
        "Reminder: project deadline next week",
        "Newsletter subscription",
        "Urgent: action required",
        # Add more samples...
    ]
    
    tokenizer = MobileBertTokenizer.from_pretrained('google/mobilebert-uncased')
    
    with open(dataset_path, 'w') as f:
        for i in range(num_samples):
            text = sample_texts[i % len(sample_texts)]
            inputs = tokenizer(
                text,
                padding='max_length',
                truncation=True,
                max_length=128,
                return_tensors='np'
            )
            
            # Save as space-separated values
            input_ids = inputs['input_ids'].flatten()
            f.write(' '.join(map(str, input_ids)) + '\n')
    
    print(f"Dataset saved to {dataset_path}")
    return dataset_path


def main():
    """Main conversion pipeline"""
    print("=== MobileBERT to RKNN Conversion ===\n")
    
    # Step 1: Download or load pretrained model
    print("Step 1: Loading MobileBERT model...")
    model_name = 'google/mobilebert-uncased'
    
    # For classification, we need a classification head
    # You may need to fine-tune this on your email dataset first
    model = MobileBertForSequenceClassification.from_pretrained(
        model_name,
        num_labels=2  # Important / Not Important
    )
    tokenizer = MobileBertTokenizer.from_pretrained(model_name)
    
    print(f"Model loaded: {model_name}\n")
    
    # Step 2: Export to ONNX
    onnx_path = "mobilebert.onnx"
    export_to_onnx(model, tokenizer, onnx_path)
    print()
    
    # Step 3: Convert to RKNN
    rknn_path = "mobilebert.rknn"
    success = convert_to_rknn(onnx_path, rknn_path)
    
    if success:
        print("\n=== Conversion Complete! ===")
        print(f"RKNN model saved to: {rknn_path}")
        print(f"\nNext steps:")
        print(f"1. Transfer {rknn_path} to your RK3566 board")
        print(f"2. Place it in: /path/to/mae/data/models/")
        print(f"3. Update config/settings.yaml to point to the model")
    else:
        print("\n=== Conversion Failed ===")
        print("Check the error messages above")


if __name__ == "__main__":
    main()
