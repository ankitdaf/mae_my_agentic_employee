import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

# Mock rknnlite and transformers before import
sys.modules['rknnlite'] = MagicMock()
sys.modules['rknnlite.api'] = MagicMock()
sys.modules['transformers'] = MagicMock()

from src.agents.classifier.classifier import EmailClassifier

class TestClassifierSanitization(unittest.TestCase):
    def setUp(self):
        self.classifier = EmailClassifier(model_path=None, use_model=False, agent_name="test")
        
    def test_prepare_model_input_sanitization(self):
        email_data = {
            'subject': 'Subject\nWith\nNewlines',
            'from_name': 'Sender\tName',
            'from_email': 'sender@example.com',
            'body_text': 'Body\nText\r\nWith\tSpecial  Chars'
        }
        
        input_text = self.classifier._prepare_model_input(email_data)
        
        # Expected: [SUBJECT] Subject With Newlines [SENDER] Sender Name <sender@example.com> [BODY] Body Text With Special Chars
        expected_subject = "Subject With Newlines"
        expected_sender = "Sender Name <sender@example.com>"
        expected_body = "Body Text With Special Chars"
        
        self.assertIn(f"[SUBJECT] {expected_subject}", input_text)
        self.assertIn(f"[SENDER] {expected_sender}", input_text)
        self.assertIn(f"[BODY] {expected_body}", input_text)
        
        # Verify no newlines or tabs
        self.assertNotIn('\n', input_text)
        self.assertNotIn('\t', input_text)
        self.assertNotIn('\r', input_text)

    def test_classify_with_rules_sanitization(self):
        # This test indirectly verifies sanitization in _classify_with_rules 
        # by checking if it runs without error on messy input
        email_data = {
            'subject': 'Invoice\nPayment',
            'body_text': 'Please pay\nnow',
            'from_email': 'billing@company.com',
            'from_name': 'Billing\tDept'
        }
        
        result = self.classifier.classify(email_data)
        self.assertEqual(result['category'], 'transactions')

if __name__ == '__main__':
    unittest.main()
