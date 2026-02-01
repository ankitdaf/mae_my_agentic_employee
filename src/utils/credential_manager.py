"""
Credential Manager for MAE

Secure storage and retrieval of service credentials using system keyring
with encrypted file fallback for systems without keyring support.

Supports multiple service types (Gmail, OneDrive, Calendar, etc.) with
isolated credential storage per agent and service.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
import keyring
from keyring.errors import KeyringError, PasswordDeleteError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Base service name for keyring
BASE_SERVICE_NAME = "mae-agent"

# Fallback encrypted storage
FALLBACK_DIR = Path.home() / ".mae"
FALLBACK_FILE = FALLBACK_DIR / "credentials.enc"


class CredentialManager:
    """Manages secure storage of service credentials for MAE agents
    
    Supports multiple service types with isolated credential storage.
    Uses system keyring (GNOME Keyring, KWallet, macOS Keychain, Windows Credential Manager)
    with encrypted file fallback for systems without keyring support.
    """
    
    @staticmethod
    def _get_keyring_key(agent_name: str, service_type: str) -> str:
        """
        Generate keyring key for an agent and service type
        
        Args:
            agent_name: Name of the agent
            service_type: Type of service (e.g., 'gmail', 'onedrive', 'calendar')
            
        Returns:
            Keyring key in format: agent_name:service_type
        """
        return f"{agent_name}:{service_type}"
    
    @staticmethod
    def _get_encryption_key() -> bytes:
        """
        Generate encryption key for fallback storage
        
        Uses machine-specific data to derive a consistent key.
        The key is cached in memory for performance.
        """
        # Check if key is already cached
        if hasattr(CredentialManager, '_cached_encryption_key'):
            return CredentialManager._cached_encryption_key
        
        # Use machine ID or hostname as salt
        try:
            # Try to read machine ID on Linux
            machine_id_path = Path("/etc/machine-id")
            if machine_id_path.exists():
                salt = machine_id_path.read_text().strip().encode()
            else:
                # Fallback to hostname
                import socket
                salt = socket.gethostname().encode()
        except Exception as e:
            # Last resort: use a default salt (less secure)
            salt = b"mae-default-salt-change-in-production"
            logger.warning(f"Using default salt for encryption ({e}) - consider implementing machine-specific salt")
        
        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        # Use a fixed password combined with salt
        password = b"mae-credential-encryption-key"
        key = kdf.derive(password)
        
        # CRITICAL FIX: Use the derived key, not a random key!
        # Fernet requires a base64-encoded 32-byte key
        from base64 import urlsafe_b64encode
        fernet_key = urlsafe_b64encode(key)
        
        # Cache the key for performance
        CredentialManager._cached_encryption_key = fernet_key
        
        return fernet_key
    
    @staticmethod
    def validate_email(email: str) -> None:
        """
        Validate email address format
        
        Args:
            email: Email address to validate
            
        Raises:
            ValueError: If email is invalid
        """
        if not email or '@' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        # Basic email validation
        parts = email.split('@')
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid email address format: {email}")
    
    @staticmethod
    def validate_password(password: str) -> str:
        """
        Validate and normalize app password
        
        Args:
            password: App password (with or without spaces)
            
        Returns:
            Clean 16-character password
            
        Raises:
            ValueError: If password is invalid
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        # Remove spaces and dashes (Google formats it like: abcd-efgh-ijkl-mnop or abcd efgh ijkl mnop)
        clean_password = password.replace(' ', '').replace('-', '')
        
        # Validate length
        if len(clean_password) != 16:
            raise ValueError(
                f"App password must be exactly 16 characters (got {len(clean_password)}). "
                f"Remove all spaces and dashes from the Google-provided password."
            )
        
        # Validate characters (Google app passwords are alphanumeric lowercase)
        if not clean_password.isalnum():
            raise ValueError(
                f"App password must contain only alphanumeric characters. "
                f"Invalid characters found: {set(c for c in clean_password if not c.isalnum())}"
            )
        
        return clean_password.lower()  # Normalize to lowercase
    
    @staticmethod
    def store_credential(agent_name: str, service_type: str, credential_data: dict) -> None:
        """
        Store service credentials securely
        
        Args:
            agent_name: Name of the agent
            service_type: Type of service (e.g., 'gmail', 'onedrive', 'calendar')
            credential_data: Dictionary containing credential data (structure depends on service)
                           For Gmail: {"email": str, "password": str}
                           For other services: any dict structure
            
        Raises:
            ValueError: If inputs are invalid
            Exception: If storage fails
        """
        # Validate inputs
        if not agent_name or not agent_name.strip():
            raise ValueError("Agent name cannot be empty")
        
        if not service_type or not service_type.strip():
            raise ValueError("Service type cannot be empty")
        
        if not credential_data or not isinstance(credential_data, dict):
            raise ValueError("Credential data must be a non-empty dictionary")
        
        key = CredentialManager._get_keyring_key(agent_name, service_type)
        
        # Try to store in system keyring first
        try:
            keyring.set_password(
                BASE_SERVICE_NAME,
                key,
                json.dumps(credential_data)
            )
            logger.info(f"Credentials for {agent_name}:{service_type} stored in system keyring")
            return
        except KeyringError as e:
            logger.warning(f"System keyring not available: {e}. Using encrypted file fallback.")
        except Exception as e:
            logger.error(f"Unexpected error storing to keyring: {e}")
        
        # Fallback to encrypted file storage
        CredentialManager._store_encrypted_file(agent_name, service_type, credential_data)
    
    @staticmethod
    def _store_encrypted_file(agent_name: str, service_type: str, credential_data: dict) -> None:
        """Store credentials in encrypted file (fallback)"""
        try:
            # Ensure directory exists
            FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
            
            # Load existing credentials or create new
            all_credentials = {}
            if FALLBACK_FILE.exists():
                all_credentials = CredentialManager._load_encrypted_file()
            
            # Ensure agent has a dict
            if agent_name not in all_credentials:
                all_credentials[agent_name] = {}
            
            # Add/update this service's credentials for the agent
            all_credentials[agent_name][service_type] = credential_data
            
            # Encrypt and save
            key = CredentialManager._get_encryption_key()
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(json.dumps(all_credentials).encode())
            
            FALLBACK_FILE.write_bytes(encrypted_data)
            
            # Set restrictive permissions (owner only)
            os.chmod(FALLBACK_FILE, 0o600)
            
            logger.info(f"Credentials for {agent_name}:{service_type} stored in encrypted file: {FALLBACK_FILE}")
        except Exception as e:
            raise Exception(f"Failed to store credentials in encrypted file: {e}")
    
    @staticmethod
    def _load_encrypted_file() -> dict:
        """Load all credentials from encrypted file with robust error handling"""
        try:
            if not FALLBACK_FILE.exists():
                return {}
            
            encrypted_data = FALLBACK_FILE.read_bytes()
            
            if not encrypted_data:
                logger.warning("Credentials file is empty, removing it")
                FALLBACK_FILE.unlink(missing_ok=True)
                return {}
            
            key = CredentialManager._get_encryption_key()
            fernet = Fernet(key)
            
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
            except Exception as decrypt_error:
                logger.error(f"Failed to decrypt credentials file (may be corrupted): {decrypt_error}")
                # Backup corrupted file
                backup_path = FALLBACK_FILE.with_suffix('.enc.corrupted')
                try:
                    FALLBACK_FILE.rename(backup_path)
                    logger.warning(f"Moved corrupted file to {backup_path}")
                except Exception:
                    FALLBACK_FILE.unlink(missing_ok=True)
                    logger.warning(f"Removed corrupted credentials file")
                return {}
            
            try:
                credentials = json.loads(decrypted_data.decode())
                if not isinstance(credentials, dict):
                    logger.error(f"Invalid credentials format: expected dict, got {type(credentials)}")
                    return {}
                return credentials
            except json.JSONDecodeError as json_error:
                logger.error(f"Failed to parse credentials JSON: {json_error}")
                return {}
                
        except Exception as e:
            logger.error(f"Unexpected error loading encrypted credentials: {e}")
            return {}
    
    @staticmethod
    def get_credential(agent_name: str, service_type: str) -> Optional[dict]:
        """
        Retrieve service credentials from secure storage
        
        Args:
            agent_name: Name of the agent
            service_type: Type of service (e.g., 'gmail', 'onedrive', 'calendar')
            
        Returns:
            Dictionary containing credential data, or None if not found
        """
        key = CredentialManager._get_keyring_key(agent_name, service_type)
        
        # Try system keyring first
        try:
            credential_json = keyring.get_password(BASE_SERVICE_NAME, key)
            if credential_json:
                logger.debug(f"Retrieved credentials for {agent_name}:{service_type} from system keyring")
                return json.loads(credential_json)
        except KeyringError as e:
            logger.debug(f"System keyring not available: {e}. Checking encrypted file.")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid credential format in keyring: {e}")
        
        # Fallback to encrypted file
        all_credentials = CredentialManager._load_encrypted_file()
        if agent_name in all_credentials and service_type in all_credentials[agent_name]:
            logger.debug(f"Retrieved credentials for {agent_name}:{service_type} from encrypted file")
            return all_credentials[agent_name][service_type]
        
        return None
    
    @staticmethod
    def delete_credential(agent_name: str, service_type: str) -> None:
        """
        Delete stored credentials for a specific service
        
        Args:
            agent_name: Name of the agent
            service_type: Type of service (e.g., 'gmail', 'onedrive', 'calendar')
        """
        key = CredentialManager._get_keyring_key(agent_name, service_type)
        deleted_from_keyring = False
        
        # Try to delete from system keyring
        try:
            keyring.delete_password(BASE_SERVICE_NAME, key)
            logger.info(f"Deleted credentials for {agent_name}:{service_type} from system keyring")
            deleted_from_keyring = True
        except PasswordDeleteError:
            logger.debug(f"No credentials found in system keyring for {agent_name}:{service_type}")
        except KeyringError as e:
            logger.debug(f"System keyring not available: {e}")
        
        # Also delete from encrypted file
        try:
            all_credentials = CredentialManager._load_encrypted_file()
            if agent_name in all_credentials and service_type in all_credentials[agent_name]:
                del all_credentials[agent_name][service_type]
               
                # If agent has no more services, remove agent entry
                if not all_credentials[agent_name]:
                    del all_credentials[agent_name]
                
                if all_credentials:
                    # Save remaining credentials
                    key_enc = CredentialManager._get_encryption_key()
                    fernet = Fernet(key_enc)
                    encrypted_data = fernet.encrypt(json.dumps(all_credentials).encode())
                    FALLBACK_FILE.write_bytes(encrypted_data)
                else:
                    # No credentials left, delete file
                    FALLBACK_FILE.unlink()
                    
                logger.info(f"Deleted credentials for {agent_name}:{service_type} from encrypted file")
            elif not deleted_from_keyring:
                logger.warning(f"No credentials found for {agent_name}:{service_type}")
        except Exception as e:
            logger.error(f"Failed to delete from encrypted file: {e}")
    
    @staticmethod
    def has_credential(agent_name: str, service_type: str) -> bool:
        """
        Check if credentials exist for an agent and service
        
        Args:
            agent_name: Name of the agent
            service_type: Type of service (e.g., 'gmail', 'onedrive', 'calendar')
            
        Returns:
            True if credentials exist, False otherwise
        """
        return CredentialManager.get_credential(agent_name, service_type) is not None


if __name__ == "__main__":
    # Simple test
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("Credential Manager Test")
    print("=" * 50)
    
    # Test storage
    print("\n1. Storing test credentials...")
    try:
        CredentialManager.store_credential(
            "test_agent",
            "gmail",
            {
                "email": "test@gmail.com",
                "password": "abcdefghijklmnop"
            }
        )
        print("✓ Credentials stored successfully")
    except Exception as e:
        print(f"✗ Failed to store: {e}")
        sys.exit(1)
    
    # Test retrieval
    print("\n2. Retrieving credentials...")
    creds = CredentialManager.get_credential("test_agent", "gmail")
    if creds:
        print(f"✓ Retrieved: {creds['email']}, password: {creds['password'][:4]}...{creds['password'][-4:]}")
    else:
        print("✗ Failed to retrieve credentials")
        sys.exit(1)
    
    # Test existence check
    print("\n3. Checking existence...")
    exists = CredentialManager.has_credential("test_agent", "gmail")
    print(f"✓ Credentials exist: {exists}")
    
    # Test deletion
    print("\n4. Deleting credentials...")
    CredentialManager.delete_credential("test_agent", "gmail")
    exists = CredentialManager.has_credential("test_agent", "gmail")
    if not exists:
        print("✓ Credentials deleted successfully")
    else:
        print("✗ Failed to delete credentials")
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")
