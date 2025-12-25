#!/bin/bash

# Source conda (adjust path if needed)
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
    echo "Conda not found!"
    exit 1
fi

# Activate environment
conda activate rknn

# Ensure we are in the correct directory
cd /path/to/mae

# Run agent
python3 -m src.orchestrator.main
