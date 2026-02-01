"""
Test App Password Authentication

Tests for the credential manager and app password authentication flow.
"""

import pytest
import os
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.credential_manager import CredentialManager


class TestCredentialManager:
    """Test credential storage and retrieval"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.test_agent = "test_agent_app_password"
        self.test_email = "test@gmail.com"
        self.test_password = "abcd efgh ijkl mnop"
        
    def teardown_method(self):
        """Cleanup after tests"""
        try:
            CredentialManager.delete_credential(self.test_agent, "gmail")
        except:
            pass
    
    def test_store_and_retrieve_credentials(self):
        """Test storing and retrieving app password"""
        # Store credentials
        CredentialManager.store_credential(
            self.test_agent,
            "gmail",
            {
                "email": self.test_email.lower(),
                "password": self.test_password.replace(' ', '').lower()
            }
        )
        
        # Retrieve credentials
        creds = CredentialManager.get_credential(self.test_agent, "gmail")
        
        assert creds is not None
        assert creds['email'] == self.test_email.lower()
        assert creds['password'] == self.test_password.replace(' ', '').lower()
        assert len(creds['password']) == 16
    
    def test_password_normalization(self):
        """Test password normalization logic directly since wrappers are removed"""
        # Test the utility validation/normalization method
        normalized = CredentialManager._validate_password("abcd efgh ijkl mnop")
        assert normalized == "abcdefghijklmnop"
        
        normalized = CredentialManager._validate_password("abcd-efgh-ijkl-mnop")
        assert normalized == "abcdefghijklmnop"
    
    def test_invalid_password_length(self):
        """Test that invalid password length raises error"""
        with pytest.raises(ValueError, match="must be 16 characters"):
            CredentialManager._validate_password("short")
    
    def test_has_credential(self):
        """Test checking credential existence"""
        # Should not exist initially
        assert not CredentialManager.has_credential(self.test_agent, "gmail")
        
        # Store credentials
        CredentialManager.store_credential(
            self.test_agent,
            "gmail",
            {
                "email": self.test_email,
                "password": "abcdefghijklmnop"
            }
        )
        
        # Should exist now
        assert CredentialManager.has_credential(self.test_agent, "gmail")
    
    def test_delete_credential(self):
        """Test credential deletion"""
        # Store credentials
        CredentialManager.store_credential(
            self.test_agent,
            "gmail",
            {
                "email": self.test_email,
                "password": "abcdefghijklmnop"
            }
        )
        
        # Verify stored
        assert CredentialManager.has_credential(self.test_agent, "gmail")
        
        # Delete
        CredentialManager.delete_credential(self.test_agent, "gmail")
        
        # Verify deleted
        assert not CredentialManager.has_credential(self.test_agent, "gmail")
        assert CredentialManager.get_credential(self.test_agent, "gmail") is None
    
    def test_multiple_agents(self):
        """Test storing credentials for multiple agents"""
        agent1 = "agent1"
        agent2 = "agent2"
        
        try:
            # Store for both agents
            CredentialManager.store_credential(agent1, "gmail", {"email": "user1@gmail.com", "password": "aaaabbbbccccdddd"})
            CredentialManager.store_credential(agent2, "gmail", {"email": "user2@gmail.com", "password": "eeeeffffgggghhhh"})
            
            # Retrieve and verify
            creds1 = CredentialManager.get_credential(agent1, "gmail")
            creds2 = CredentialManager.get_credential(agent2, "gmail")
            
            assert creds1['email'] == "user1@gmail.com"
            assert creds2['email'] == "user2@gmail.com"
            assert creds1['password'] != creds2['password']
            
        finally:
            # Cleanup
            CredentialManager.delete_credential(agent1, "gmail")
            CredentialManager.delete_credential(agent2, "gmail")
    
    def test_invalid_email_formats(self):
        """Test that invalid email formats are rejected by the validator"""
        invalid_emails = [
            "",
            "notanemail",
            "@gmail.com",
            "test@",
            "test@@gmail.com",
            "   ",
        ]
        
        for invalid_email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email"):
                CredentialManager._validate_email(invalid_email)
    
    def test_empty_agent_name(self):
        """Test that empty agent name is rejected by store_credential"""
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            CredentialManager.store_credential(
                "",
                "gmail",
                {"email": self.test_email, "password": "abcdefghijklmnop"}
            )
    
    def test_invalid_passwords(self):
        """Test that invalid passwords are rejected by the validator"""
        # Empty password
        with pytest.raises(ValueError, match="Password cannot be empty"):
            CredentialManager._validate_password("")
            
        # Special characters
        invalid_passwords = [
            "abcd efgh ijkl mno!",  # Contains !
            "abcd@efghijklmnop",     # Contains @
            "abcd#efgh-ijkl-mnop",  # Contains #
        ]
        
        for invalid_password in invalid_passwords:
            with pytest.raises(ValueError, match="alphanumeric characters"):
                CredentialManager._validate_password(invalid_password)
    
    def test_update_existing_credentials(self):
        """Test updating credentials for an existing agent and service"""
        # Store initial credentials
        CredentialManager.store_credential(
            self.test_agent,
            "gmail",
            {"email": "old@gmail.com", "password": "aaaabbbbccccdddd"}
        )
        
        # Update with new credentials
        CredentialManager.store_credential(
            self.test_agent,
            "gmail",
            {"email": "new@gmail.com", "password": "eeeeffffgggghhhh"}
        )
        
        # Verify updated credentials
        creds = CredentialManager.get_credential(self.test_agent, "gmail")
        assert creds['email'] == "new@gmail.com"
        assert creds['password'] == "eeeeffffgggghhhh"
    
    def test_get_nonexistent_credentials(self):
        """Test retrieving credentials for non-existent agent/service"""
        creds = CredentialManager.get_credential("nonexistent_agent", "gmail")
        assert creds is None
        
        creds = CredentialManager.get_credential(self.test_agent, "nonexistent_service")
        assert creds is None
    
    def test_delete_nonexistent_credentials(self):
        """Test deleting non-existent credentials doesn't raise error"""
        # Should not raise an error
        CredentialManager.delete_credential("nonexistent_agent", "gmail")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
