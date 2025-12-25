"""
Resource Token Manager for MAE

File-based locking system to manage shared resources like NPU, IMAP connections, etc.
Prevents resource contention between multiple agent processes.
"""

import os
import time
import fcntl
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from enum import Enum

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Types of resource tokens"""
    NPU = "npu"              # NPU model inference
    IMAP = "imap"            # IMAP connection (to avoid rate limits)
    CALENDAR = "calendar"    # Google Calendar API
    GENERAL = "general"      # General processing token


class TokenAcquisitionError(Exception):
    """Raised when token acquisition fails"""
    pass


class TokenManager:
    """Manage resource tokens using file-based locks"""
    
    DEFAULT_LOCK_DIR = Path(__file__).parent.parent.parent / 'data' / 'locks'
    DEFAULT_TIMEOUT = 300  # 5 minutes
    
    def __init__(self, lock_dir: Optional[Path] = None):
        """
        Initialize token manager
        
        Args:
            lock_dir: Directory for lock files (default: data/locks)
        """
        self.lock_dir = lock_dir or self.DEFAULT_LOCK_DIR
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.acquired_locks = {}  # Track acquired locks
        
        logger.debug(f"TokenManager initialized with lock_dir: {self.lock_dir}")
    
    def _get_lock_file(self, token_type: TokenType) -> Path:
        """Get lock file path for token type"""
        return self.lock_dir / f"{token_type.value}.lock"
    
    def acquire(self, token_type: TokenType, timeout: int = DEFAULT_TIMEOUT,
                agent_name: str = "unknown") -> bool:
        """
        Acquire a resource token (blocking with timeout)
        
        Args:
            token_type: Type of token to acquire
            timeout: Maximum time to wait in seconds
            agent_name: Name of agent acquiring token (for logging)
        
        Returns:
            True if acquired, False if timeout
        
        Raises:
            TokenAcquisitionError: If acquisition fails
        """
        lock_file = self._get_lock_file(token_type)
        start_time = time.time()
        
        logger.info(f"[{agent_name}] Attempting to acquire {token_type.value} token...")
        
        while True:
            try:
                # Open/create lock file
                fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
                
                # Try to acquire exclusive lock (non-blocking)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    
                    # Write agent info to lock file
                    os.ftruncate(fd, 0)
                    os.write(fd, f"{agent_name}|{time.time()}".encode())
                    
                    # Store file descriptor for later release
                    self.acquired_locks[token_type] = fd
                    
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[{agent_name}] Acquired {token_type.value} token "
                        f"(waited {elapsed:.2f}s)"
                    )
                    return True
                
                except IOError:
                    # Lock is held by another process
                    os.close(fd)
                    
                    # Check timeout
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        logger.error(
                            f"[{agent_name}] Failed to acquire {token_type.value} token "
                            f"(timeout after {elapsed:.2f}s)"
                        )
                        return False
                    
                    # Check for stale locks
                    if self._is_stale_lock(lock_file):
                        logger.warning(
                            f"[{agent_name}] Detected stale {token_type.value} lock, "
                            f"attempting cleanup..."
                        )
                        self._cleanup_stale_lock(lock_file)
                    
                    # Wait before retry
                    time.sleep(1)
            
            except Exception as e:
                logger.error(f"[{agent_name}] Error acquiring token: {e}")
                raise TokenAcquisitionError(f"Failed to acquire {token_type.value} token: {e}")
    
    def release(self, token_type: TokenType, agent_name: str = "unknown"):
        """
        Release a resource token
        
        Args:
            token_type: Type of token to release
            agent_name: Name of agent releasing token (for logging)
        """
        if token_type not in self.acquired_locks:
            logger.warning(
                f"[{agent_name}] Attempted to release {token_type.value} token "
                f"that was not acquired"
            )
            return
        
        try:
            fd = self.acquired_locks[token_type]
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            del self.acquired_locks[token_type]
            
            logger.info(f"[{agent_name}] Released {token_type.value} token")
        
        except Exception as e:
            logger.error(f"[{agent_name}] Error releasing token: {e}")
    
    def _is_stale_lock(self, lock_file: Path, max_age: int = 3600) -> bool:
        """
        Check if a lock file is stale (older than max_age)
        
        Args:
            lock_file: Path to lock file
            max_age: Maximum age in seconds (default: 1 hour)
        
        Returns:
            True if lock is stale
        """
        try:
            if not lock_file.exists():
                return False
            
            # Try to read lock file content
            with open(lock_file, 'r') as f:
                content = f.read().strip()
            
            if not content:
                return True
            
            # Parse timestamp from lock file
            parts = content.split('|')
            if len(parts) < 2:
                return True
            
            timestamp = float(parts[1])
            age = time.time() - timestamp
            
            return age > max_age
        
        except Exception as e:
            logger.error(f"Error checking lock staleness: {e}")
            return False
    
    def _cleanup_stale_lock(self, lock_file: Path):
        """
        Attempt to clean up a stale lock file
        
        Args:
            lock_file: Path to lock file
        """
        try:
            lock_file.unlink()
            logger.info(f"Cleaned up stale lock: {lock_file}")
        except Exception as e:
            logger.error(f"Failed to cleanup stale lock: {e}")
    
    @contextmanager
    def token(self, token_type: TokenType, agent_name: str = "unknown",
              timeout: int = DEFAULT_TIMEOUT):
        """
        Context manager for acquiring and releasing tokens
        
        Usage:
            with token_manager.token(TokenType.NPU, "my_agent"):
                # Do work with NPU
                ...
        
        Args:
            token_type: Type of token to acquire
            agent_name: Name of agent (for logging)
            timeout: Maximum time to wait
        
        Yields:
            None
        
        Raises:
            TokenAcquisitionError: If acquisition fails or times out
        """
        acquired = self.acquire(token_type, timeout, agent_name)
        
        if not acquired:
            raise TokenAcquisitionError(
                f"Failed to acquire {token_type.value} token within {timeout}s"
            )
        
        try:
            yield
        finally:
            self.release(token_type, agent_name)
    
    def release_all(self, agent_name: str = "unknown"):
        """
        Release all acquired tokens (cleanup on exit)
        
        Args:
            agent_name: Name of agent (for logging)
        """
        for token_type in list(self.acquired_locks.keys()):
            self.release(token_type, agent_name)
    
    def get_lock_status(self) -> dict:
        """
        Get status of all locks
        
        Returns:
            Dictionary mapping token types to lock status
        """
        status = {}
        
        for token_type in TokenType:
            lock_file = self._get_lock_file(token_type)
            
            if not lock_file.exists():
                status[token_type.value] = "available"
            else:
                try:
                    with open(lock_file, 'r') as f:
                        content = f.read().strip()
                    
                    if content:
                        parts = content.split('|')
                        if len(parts) >= 2:
                            agent = parts[0]
                            timestamp = float(parts[1])
                            age = time.time() - timestamp
                            status[token_type.value] = f"locked by {agent} ({age:.0f}s ago)"
                        else:
                            status[token_type.value] = "locked (unknown)"
                    else:
                        status[token_type.value] = "locked (empty)"
                
                except Exception as e:
                    status[token_type.value] = f"error: {e}"
        
        return status


if __name__ == "__main__":
    # Test token manager
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        # Show lock status
        tm = TokenManager()
        status = tm.get_lock_status()
        print("\nLock Status:")
        for token, state in status.items():
            print(f"  {token}: {state}")
    else:
        # Test acquiring and releasing tokens
        tm = TokenManager()
        agent_name = "test_agent"
        
        print(f"\n[Test] Acquiring NPU token...")
        tm.acquire(TokenType.NPU, agent_name=agent_name, timeout=5)
        
        print(f"[Test] Acquired! Holding for 3 seconds...")
        time.sleep(3)
        
        print(f"[Test] Releasing NPU token...")
        tm.release(TokenType.NPU, agent_name=agent_name)
        
        print(f"\n[Test] Testing context manager...")
        with tm.token(TokenType.IMAP, agent_name=agent_name, timeout=5):
            print(f"[Test] Inside context manager, holding for 2 seconds...")
            time.sleep(2)
        
        print(f"[Test] Exited context manager, token auto-released")
        
        print("\n✓ All tests passed!")
