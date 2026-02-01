
import unittest
from unittest.mock import Mock, patch, mock_open
import json
import datetime
from fastapi.testclient import TestClient
from src.server.app import app

client = TestClient(app)

# Mock data
MOCK_AGENT_NAME = "test_agent"
MOCK_TOKEN_PATH = f"data/{MOCK_AGENT_NAME}/oauth_tokens.json"

class TestAuthStatus(unittest.TestCase):
    
    def setUp(self):
        self.mock_token_data = json.dumps({
            "token": "access_token",
            "refresh_token": "refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
            "expiry": (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).isoformat() + "Z"
        })

    @patch("src.server.app.Credentials")
    @patch("src.server.app.Request")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_auth_status_expired_refresh_success(self, mock_exists, mock_file, mock_request, mock_creds):
        # Setup
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = self.mock_token_data
        
        # Mock credentials
        creds_instance = Mock()
        creds_instance.valid = False
        creds_instance.expired = True
        creds_instance.refresh_token = "valid_refresh_token"
        mock_creds.from_authorized_user_info.return_value = creds_instance
        
        # Mock successful refresh
        def refresh_side_effect(request):
            creds_instance.valid = True
            creds_instance.expired = False
        creds_instance.refresh.side_effect = refresh_side_effect
        
        # Execute
        response = client.get(f"/api/auth/status/{MOCK_AGENT_NAME}")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["valid"])
        creds_instance.refresh.assert_called_once()

    @patch("src.server.app.Credentials")
    @patch("src.server.app.Request")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_auth_status_expired_refresh_failure(self, mock_exists, mock_file, mock_request, mock_creds):
        # Setup
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = self.mock_token_data
        
        # Mock credentials
        creds_instance = Mock()
        creds_instance.valid = False
        creds_instance.expired = True
        creds_instance.refresh_token = "invalid_refresh_token"
        mock_creds.from_authorized_user_info.return_value = creds_instance
        
        # Mock failed refresh
        creds_instance.refresh.side_effect = Exception("Token refresh failed")
        
        # Execute
        response = client.get(f"/api/auth/status/{MOCK_AGENT_NAME}")
        
        # Assert
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # This assertion expects the FIX to be in place. 
        self.assertFalse(data["valid"])

if __name__ == "__main__":
    unittest.main()
