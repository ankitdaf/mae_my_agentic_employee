import sys
import time
import logging
from pathlib import Path
import shutil
import os

# Add src to path
sys.path.append(str(Path.cwd()))

from src.orchestrator.token_manager import TokenManager, TokenType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_token_manager")

def test_token_manager_robustness():
    # Setup test dir
    test_dir = Path("data/test_locks")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    
    tm = TokenManager(test_dir)
    agent_name = "test_agent"
    
    print("\n[Test 1] Normal Acquisition and Release")
    acquired = tm.acquire(TokenType.IMAP, agent_name=agent_name)
    assert acquired, "Failed to acquire token"
    assert TokenType.IMAP in tm.acquired_locks, "Token not in acquired_locks"
    
    tm.release(TokenType.IMAP, agent_name=agent_name)
    assert TokenType.IMAP not in tm.acquired_locks, "Token still in acquired_locks after release"
    print("✓ Passed")
    
    print("\n[Test 2] Re-entrancy (Self-Deadlock Prevention)")
    # Acquire once
    tm.acquire(TokenType.IMAP, agent_name=agent_name)
    
    # Acquire again (should succeed immediately due to re-entrancy check)
    t0 = time.time()
    acquired = tm.acquire(TokenType.IMAP, agent_name=agent_name, timeout=2)
    elapsed = time.time() - t0
    
    assert acquired, "Failed to re-acquire token"
    assert elapsed < 1.0, f"Re-acquisition took too long ({elapsed}s) - re-entrancy check failed?"
    print("✓ Passed")
    
    # Cleanup
    tm.release(TokenType.IMAP, agent_name=agent_name)
    
    print("\n[Test 3] Robust Release (Simulate Failure)")
    # Acquire
    tm.acquire(TokenType.IMAP, agent_name=agent_name)
    fd = tm.acquired_locks[TokenType.IMAP]
    
    # Manually close FD to simulate some error state where FD is bad
    os.close(fd)
    
    # Try to release - should not crash and should clean up
    try:
        tm.release(TokenType.IMAP, agent_name=agent_name)
        print("✓ Release handled invalid FD gracefully")
    except Exception as e:
        print(f"✗ Release crashed: {e}")
        raise
        
    assert TokenType.IMAP not in tm.acquired_locks, "Token not cleaned up after failed release"
    print("✓ Passed")
    
    print("\nAll TokenManager robustness tests passed!")

if __name__ == "__main__":
    test_token_manager_robustness()
