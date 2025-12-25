import unittest
import csv
import json
import shutil
from pathlib import Path
from datetime import datetime
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.agents.email.email_storage import EmailStorage

class TestCSVStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("data/test_csv_storage")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.storage = EmailStorage(self.test_dir, "test_agent")
        
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_init_creates_csv(self):
        self.assertTrue((self.test_dir / "emails.csv").exists())
        with open(self.test_dir / "emails.csv", 'r') as f:
            header = f.readline().strip()
            self.assertTrue("id,date,sender_email" in header)
            
    def test_save_email_does_not_create_json(self):
        email_data = {
            'id': '123',
            'hash': 'hash123',
            'subject': 'Test Email',
            'from_email': 'test@example.com',
            'date': datetime.now().isoformat()
        }
        self.storage.save_email(email_data)
        
        # Check index exists
        self.assertTrue((self.test_dir / "email_index.json").exists())
        
        # Check individual JSON does NOT exist
        self.assertFalse((self.test_dir / "metadata" / "hash123.json").exists())
        
    def test_update_classification_appends_to_csv(self):
        email_data = {
            'id': '123',
            'hash': 'hash123',
            'subject': 'Test Email',
            'from_email': 'test@example.com',
            'from_name': 'Test Sender',
            'body_text': 'This is a test body.\nWith newlines.',
            'date': datetime.now().isoformat()
        }
        
        # First save to index
        self.storage.save_email(email_data)
        
        # Update classification
        classification = {'category': 'promotions', 'confidence': 0.95}
        self.storage.update_classification('hash123', classification, email_data)
        
        # Verify CSV content
        with open(self.test_dir / "emails.csv", 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['id'], '123')
            self.assertEqual(row['label'], 'promotions')
            self.assertEqual(row['confidence'], '0.95')
            # Verify newlines are removed and spaces collapsed
            self.assertEqual(row['body_text'], 'This is a test body. With newlines.')

if __name__ == '__main__':
    unittest.main()
