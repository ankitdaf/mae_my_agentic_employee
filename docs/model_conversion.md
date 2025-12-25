# Model Conversion Guide

This guide explains how to convert MobileBERT to RKNN format for deployment on RK3566.

## Prerequisites

### PC Requirements (x86/x64)
- Ubuntu 20.04 or 22.04
- Python 3.8+
- At least 8GB RAM
- 10GB free disk space

### Software Installation

1. **Clone rknn-toolkit2**:
   ```bash
   git clone https://github.com/airockchip/rknn-toolkit2.git
   cd rknn-toolkit2
   ```

2. **Install rknn-toolkit2** (PC only):
   ```bash
   cd rknn-toolkit2/packages
   pip install rknn_toolkit2-*-cp3*-linux_x86_64.whl
   ```

3. **Install other dependencies**:
   ```bash
   pip install transformers torch onnx
   ```

## Conversion Process

### Step 1: Fine-tune MobileBERT (Optional but Recommended)

For best results, fine-tune MobileBERT on your own email dataset before conversion.

```python
from transformers import MobileBertForSequenceClassification, Trainer
# ... your fine-tuning code
```

### Step 2: Run Conversion Script

Navigate to the MAE project:

```bash
cd /path/to/mae
python tools/convert_mobilebert.py
```

This will:
1. Download MobileBERT from Hugging Face
2. Export to ONNX format
3. Convert ONNX to RKNN with INT8 quantization
4. Generate `mobilebert.rknn`

### Step 3: Transfer to RK3566

Copy the model to your RK3566 board:

```bash
scp mobilebert.rknn <user>@<ip-address>:/path/to/mae/data/models/
```

### Step 4: Install Runtime on RK3566

On your RK3566 board:

1. **Enable NPU**:
   ```bash
   sudo rsetup
   # Navigate: Overlays → Manage overlays → Enable NPU
   # Reboot
   ```

2. **Install rknn-toolkit-lite2**:
   ```bash
   cd rknn-toolkit2/rknn-toolkit-lite2/packages
   pip install rknn_toolkit_lite2-*-cp3*-linux_aarch64.whl
   ```

3. **Verify NPU is active**:
   ```bash
   ls /dev/rknpu*
   # Should show: /dev/rknpu0
   ```

## Troubleshooting

### Model Conversion Fails
- **Error**: `unsupported operator`
  - Solution: Check ONNX opset version (use opset 11 or 13)
  
- **Error**: `quantization failed`
  - Solution: Provide more calibration samples in dataset

### Runtime Issues on RK3566
- **Error**: `librknnrt.so not found`
  - Solution: Install RKNPU2 runtime libraries
  ```bash
  sudo apt-get update
  sudo apt-get install rockchip-rknpu2
  ```

- **Error**: `NPU init failed`
  - Solution: Check NPU overlay is enabled in `rsetup`

## Performance Tuning

### Quantization Dataset
Use real email samples for better accuracy:

```python
# In convert_mobilebert.py, replace sample_texts with:
with open('email_samples.txt', 'r') as f:
    sample_texts = f.readlines()
```

### Batch Size
Adjust batch size based on RAM:
- 2GB RAM: batch_size=1
- Larger models: Consider memory usage

## References
- [RKNN-Toolkit2 Documentation](https://github.com/airockchip/rknn-toolkit2)
- [MobileBERT Paper](https://arxiv.org/abs/2004.02984)
