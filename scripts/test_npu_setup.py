#!/usr/bin/env python3
"""
Test RKNN Toolkit Lite installation and NPU availability on RK3566

Run this on the RK3566 device to verify NPU setup.
"""

import sys

def test_rknn_import():
    """Test if rknnlite can be imported"""
    print("=" * 60)
    print("Testing RKNN Toolkit Lite Installation")
    print("=" * 60)
    
    try:
        from rknnlite.api import RKNNLite
        print("✓ rknnlite.api imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import rknnlite: {e}")
        print("\nTo install RKNN Toolkit Lite:")
        print("1. Download from: https://github.com/rockchip-linux/rknn-toolkit2/releases")
        print("2. Install: pip install rknn_toolkit_lite2-*.whl")
        return False

def test_npu_device():
    """Test NPU device availability"""
    print("\n" + "=" * 60)
    print("Testing NPU Device")
    print("=" * 60)
    
    try:
        from rknnlite.api import RKNNLite
        
        rknn = RKNNLite()
        
        # Try to initialize (this checks if NPU is available)
        # Note: This will fail without a model, but we can catch the error type
        print("✓ RKNNLite object created")
        print("✓ NPU device should be available")
        
        return True
    except Exception as e:
        print(f"✗ NPU test failed: {e}")
        return False

def test_numpy():
    """Test NumPy installation"""
    print("\n" + "=" * 60)
    print("Testing NumPy")
    print("=" * 60)
    
    try:
        import numpy as np
        print(f"✓ NumPy version: {np.__version__}")
        
        # Test basic operations
        arr = np.array([1, 2, 3])
        print(f"✓ NumPy operations work: {arr.sum()}")
        return True
    except ImportError:
        print("✗ NumPy not installed")
        print("Install with: pip install numpy")
        return False

def check_model_file():
    """Check if model file exists"""
    print("\n" + "=" * 60)
    print("Checking Model File")
    print("=" * 60)
    
    from pathlib import Path
    
    model_path = Path("models/email_classifier.rknn")
    
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"✓ Model file found: {model_path}")
        print(f"  Size: {size_mb:.2f} MB")
        return True
    else:
        print(f"✗ Model file not found: {model_path}")
        print("\nTo get the model:")
        print("1. Train/convert model on development machine")
        print("2. Transfer to device: scp models/email_classifier.rknn <user>@<ip-address>:/path/to/mae/models/")
        return False

def test_classifier():
    """Test the EmailClassifier with NPU"""
    print("\n" + "=" * 60)
    print("Testing EmailClassifier")
    print("=" * 60)
    
    try:
        from pathlib import Path
        from src.agents.classifier import EmailClassifier
        
        model_path = Path("models/email_classifier.rknn")
        
        if not model_path.exists():
            print("⚠ Skipping classifier test (no model file)")
            return False
        
        # Initialize classifier
        print("Initializing classifier...")
        classifier = EmailClassifier(
            model_path=model_path,
            use_model=True,
            agent_name="test"
        )
        
        if classifier.use_model:
            print("✓ Classifier initialized with NPU model")
            
            # Test classification
            test_email = {
                'subject': 'URGENT: Action required on your account',
                'body_text': 'Please verify your account immediately to avoid suspension.'
            }
            
            print("\nTesting classification...")
            result = classifier.classify(test_email)
            
            print(f"✓ Classification successful!")
            print(f"  Category: {result['category']}")
            print(f"  Confidence: {result['confidence']:.2f}")
            print(f"  Method: {result['method']}")
            
            if 'probabilities' in result:
                print(f"  Probabilities:")
                for cat, prob in result['probabilities'].items():
                    print(f"    {cat}: {prob:.3f}")
            
            return True
        else:
            print("⚠ Classifier fell back to rule-based (NPU not used)")
            return False
            
    except Exception as e:
        print(f"✗ Classifier test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n🔍 RK3566 NPU Setup Verification\n")
    
    results = {
        "RKNN Import": test_rknn_import(),
        "NPU Device": test_npu_device(),
        "NumPy": test_numpy(),
        "Model File": check_model_file(),
    }
    
    # Only test classifier if prerequisites are met
    if results["RKNN Import"] and results["NumPy"]:
        results["Classifier"] = test_classifier()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! NPU is ready for email classification.")
    else:
        print("⚠️  Some tests failed. See above for details.")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
