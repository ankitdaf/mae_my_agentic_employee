#!/bin/bash

# Find where the script is located to determine project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Possible conda paths
CONDA_PATHS=(
    "$HOME/devzone/miniforge3/etc/profile.d/conda.sh"
    "$HOME/miniconda3/etc/profile.d/conda.sh"
    "$HOME/anaconda3/etc/profile.d/conda.sh"
    "/opt/miniforge3/etc/profile.d/conda.sh"
)

CONDA_FOUND=false
for path in "${CONDA_PATHS[@]}"; do
    if [ -f "$path" ]; then
        source "$path"
        CONDA_FOUND=true
        break
    fi
done

if [ "$CONDA_FOUND" = false ]; then
    echo "Conda not found in common locations!"
    # Try to find conda in PATH as a fallback
    if command -v conda &> /dev/null; then
        eval "$(conda shell.bash hook)"
    else
        echo "Conda not found in PATH either."
        exit 1
    fi
fi

# Activate environment
conda activate rknn || { echo "Failed to activate rknn environment"; exit 1; }

# Ensure we are in the correct directory
cd "$PROJECT_ROOT"

# Run agent
python3 -m src.orchestrator.main
