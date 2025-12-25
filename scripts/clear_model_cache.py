#!/usr/bin/env python3
"""
Clear HuggingFace cache for MobileBERT model

This removes cached .bin files that might be causing torch.load issues
"""

import shutil
from pathlib import Path
import os

def clear_mobilebert_cache():
    """Clear cached MobileBERT model files"""
    
    # HuggingFace cache directory
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    
    if not cache_dir.exists():
        print(f"✓ No cache directory found at {cache_dir}")
        return
    
    # Find MobileBERT cache directories
    mobilebert_dirs = list(cache_dir.glob("models--google--mobilebert-uncased*"))
    
    if not mobilebert_dirs:
        print("✓ No cached MobileBERT model found")
        return
    
    print(f"Found {len(mobilebert_dirs)} MobileBERT cache director(ies):")
    for dir_path in mobilebert_dirs:
        print(f"  - {dir_path}")
        
        # Remove .bin files specifically
        bin_files = list(dir_path.rglob("*.bin"))
        if bin_files:
            print(f"    Removing {len(bin_files)} .bin file(s)...")
            for bin_file in bin_files:
                bin_file.unlink()
                print(f"      ✓ Removed {bin_file.name}")
        
        # Optionally remove the entire directory to force fresh download
        response = input(f"\n  Remove entire cache directory? (y/N): ").strip().lower()
        if response == 'y':
            shutil.rmtree(dir_path)
            print(f"    ✓ Removed {dir_path}")
        else:
            print(f"    Kept directory (removed .bin files only)")
    
    print("\n✓ Cache cleanup complete!")
    print("\nThe model will be re-downloaded with safetensors format on next run.")

if __name__ == "__main__":
    clear_mobilebert_cache()
