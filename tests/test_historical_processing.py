import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.agents.email_agent import EmailAgent
import src.agents.email.gmail_client
import src.agents.email.email_parser
import src.agents.email.email_storage
import src.agents.classifier.classifier
import src.agents.classifier.topic_matcher
import src.agents.classifier.sender_manager
import src.agents.actions.email_deleter
import src.agents.actions.attachment_saver

class TestHistoricalProcessing(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.get_agent_name.return_value = "test_agent"
        
        def config_get_side_effect(section, key=None, default=None):
            if section == 'classification' and key == 'model_path':
                return "models/email_classifier.rknn"
            if section == 'classification' and key == 'tokenizer_path':
                return "models/tokenizer"
            if section == 'classification' and key == 'use_ai_model':
                return True
            if section == 'email' and key == 'address':
                return "test@example.com"
            if section == 'email' and key == 'credentials_path':
                return "config/secrets/gmail_credentials.json"
            if section == 'deletion':
                return {'dry_run': True}
            if section == 'attachments':
                return {}
            if section == 'calendar' and key == 'enabled':
                return False
            if section == 'calendar' and key == 'credentials_path':
                return None
            return default
            
        self.config.get.side_effect = config_get_side_effect
        self.config.agent_data_dir = Path("data/test")
        self.config.email_cache_dir = Path("data/test/cache")
        self.config.oauth_token_path = Path("data/test/tokens.json")
        
        self.token_manager = MagicMock()
        
        # Mock dependencies
        with patch('src.agents.email.gmail_client.GmailClient'), \
             patch('src.agents.email.email_parser.EmailParser'), \
             patch('src.agents.email.email_storage.EmailStorage'), \
             patch('src.agents.classifier.classifier.EmailClassifier'), \
             patch('src.agents.classifier.topic_matcher.TopicMatcher'), \
             patch('src.agents.classifier.sender_manager.SenderManager'), \
             patch('src.agents.actions.email_deleter.EmailDeleter'), \
             patch('src.agents.actions.attachment_saver.AttachmentSaver'):
            
            self.agent = EmailAgent(self.config, self.token_manager)
            
    def test_process_historical_emails(self):
        # Setup mocks
        self.agent.gmail_client = MagicMock()
        self.agent.gmail_client.__enter__.return_value = self.agent.gmail_client
        self.agent.classifier = MagicMock()
        
        # Mock list_folders
        self.agent.gmail_client.list_folders.return_value = ["INBOX", "Promotions", "[Gmail]/Trash"]
        
        # Mock fetch_emails
        email1 = {'id': '1', 'subject': 'Promo 1', 'from_email': 'promo@test.com'}
        email2 = {'id': '2', 'subject': 'Important', 'from_email': 'boss@test.com'}
        
        def fetch_side_effect(folder, **kwargs):
            if folder == "Promotions":
                return [email1]
            elif folder == "INBOX":
                return [email2]
            return []
            
        self.agent.gmail_client.fetch_emails.side_effect = fetch_side_effect
        
        # Mock classify
        def classify_side_effect(email):
            if email['id'] == '1':
                return {'category': 'promotions', 'confidence': 0.9, 'method': 'mock'}
            else:
                return {'category': 'inbox', 'confidence': 0.9, 'method': 'mock'}
                
        self.agent.classifier.classify.side_effect = classify_side_effect
        
        # Run historical processing
        self.agent.dry_run = False
        self.agent.process_historical_emails("2023-01-01", "2023-01-05", ["promotions"])
        
        # Verify
        # Should list folders
        self.agent.gmail_client.list_folders.assert_called_once()
        
        # Should fetch from INBOX and Promotions (skip Trash)
        self.assertEqual(self.agent.gmail_client.fetch_emails.call_count, 2)
        
        # Should add label to email1 only
        self.agent.gmail_client.add_label.assert_called_once_with('1', 'MarkedForDeletion')

if __name__ == '__main__':
    unittest.main()
