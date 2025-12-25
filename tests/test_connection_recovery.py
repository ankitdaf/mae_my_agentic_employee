import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

# Mock google modules before imports
sys.modules['google'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google.auth.transport'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['google_auth_oauthlib'] = MagicMock()
sys.modules['google_auth_oauthlib.flow'] = MagicMock()

from src.agents.email.gmail_client import GmailClient, GmailConnectionError

class TestConnectionRecovery(unittest.TestCase):
    def setUp(self):
        self.client = GmailClient("test@example.com", Path("token"), Path("creds"), "test_agent")
        self.client.imap = MagicMock()
        # Mock connect/disconnect to avoid real auth
        self.client.connect = MagicMock()
        self.client.disconnect = MagicMock()
        # Mock noop to succeed by default
        self.client.imap.noop.return_value = ('OK', [b''])
        
    def test_list_folders_retry(self):
        # Simulate failure then success
        self.client.imap.list.side_effect = [
            Exception("Connection reset"),
            ('OK', [b'(\\HasNoChildren) "/" "INBOX"'])
        ]
        
        # Should succeed on second attempt
        folders = self.client.list_folders()
        self.assertEqual(folders, ["INBOX"])
        self.assertEqual(self.client.imap.list.call_count, 2)
        
    def test_fetch_emails_retry(self):
        # Mock select to succeed
        self.client.imap.select.return_value = ('OK', [b'1'])
        
        # Simulate search failure then success
        self.client.imap.search.side_effect = [
            Exception("Connection reset"),
            ('OK', [b'1 2'])
        ]
        
        # Mock fetch to succeed
        self.client.imap.fetch.return_value = ('OK', [(b'1 (RFC822 {10}', b'Header: value\r\n\r\nBody')])
        
        # Should succeed on second attempt
        emails = self.client.fetch_emails(folder="INBOX", limit=1)
        self.assertEqual(len(emails), 1)
        self.assertEqual(self.client.imap.search.call_count, 2)

if __name__ == '__main__':
    unittest.main()
