import unittest
import shutil
from pathlib import Path
from datetime import datetime, timezone
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.agents.email.email_storage import EmailStorage

class TestEmailDeduplication(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("data/test_deduplication")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.storage = EmailStorage(self.test_dir, "test_agent")
        
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_email_exists_recent(self):
        email1 = {
            'id': '1',
            'hash': 'hash1',
            'subject': 'Email 1',
            'date': 'Mon, 20 Nov 2023 10:00:00 +0000'
        }
        email2 = {
            'id': '2',
            'hash': 'hash2',
            'subject': 'Email 2',
            'date': 'Tue, 21 Nov 2023 10:00:00 +0000'
        }
        
        # Initially doesn't exist
        self.assertFalse(self.storage.email_exists('hash1'))
        
        # Save email1
        self.storage.save_email(email1)
        self.storage.update_watermark(email1)
        self.assertTrue(self.storage.email_exists('hash1'))
        
        # Save email2 (newer)
        self.storage.save_email(email2)
        self.storage.update_watermark(email2)
        self.assertTrue(self.storage.email_exists('hash2'))
        
        # email1 should STILL exist because we track recent hashes
        self.assertTrue(self.storage.email_exists('hash1'))
        
        # Verify no index file exists
        self.assertFalse((self.test_dir / "email_index.json").exists())

    def test_recent_hashes_limit(self):
        # Add 205 emails
        for i in range(205):
            # Use increasing dates to ensure latest_email updates
            day = (i // 24) + 1
            hour = i % 24
            email = {
                'id': str(i),
                'hash': f'hash{i}',
                'subject': f'Email {i}',
                'date': f'Mon, {day} Nov 2023 {hour:02d}:00:00 +0000'
            }
            self.storage.update_watermark(email)
            
        # Check that hash204 exists (latest)
        self.assertTrue(self.storage.email_exists('hash204'))
        
        # Check that hash0 does NOT exist (should be pushed out, limit is 200)
        # 0 to 204 is 205 items. 
        # Kept: 5 to 204.
        # Dropped: 0 to 4.
        self.assertFalse(self.storage.email_exists('hash0'))
        self.assertFalse(self.storage.email_exists('hash4'))
        
        # Check that hash5 exists
        self.assertTrue(self.storage.email_exists('hash5'))
        
    def test_get_latest_email_info(self):
        # Save two emails with different dates
        email1 = {
            'id': '1',
            'hash': 'hash1',
            'subject': 'Older Email',
            'date': 'Mon, 20 Nov 2023 10:00:00 +0000'
        }
        email2 = {
            'id': '2',
            'hash': 'hash2',
            'subject': 'Newer Email',
            'date': 'Tue, 21 Nov 2023 10:00:00 +0000'
        }
        
        self.storage.save_email(email1)
        self.storage.update_watermark(email1)
        self.storage.save_email(email2)
        self.storage.update_watermark(email2)
        
        latest = self.storage.get_latest_email_info()
        
        self.assertEqual(latest['hash'], 'hash2')
        self.assertEqual(latest['subject'], 'Newer Email')
        # Check if date_parsed is a datetime object
        self.assertIsInstance(latest['date_parsed'], datetime)
        self.assertEqual(latest['date_parsed'].day, 21)

if __name__ == '__main__':
    unittest.main()
