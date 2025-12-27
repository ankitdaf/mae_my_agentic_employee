"""
Email Storage for MAE

File-based storage for email metadata and processing state.
Prevents reprocessing of emails and enables offline access.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.utils.text_utils import sanitize_text
from src.utils.datetime_utils import ensure_aware

logger = logging.getLogger(__name__)


class EmailStorage:
    """File-based email cache and metadata storage"""
    
    def __init__(self, cache_dir: Path, agent_name: str = "unknown"):
        """
        Initialize email storage
        
        Args:
            cache_dir: Directory to store email cache
            agent_name: Agent name for logging
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.agent_name = agent_name
        
        # Create subdirectories
        self.metadata_dir = self.cache_dir / 'metadata'
        self.metadata_dir.mkdir(exist_ok=True)
        
        self.state_file = self.cache_dir / 'processing_state.json'
        self.csv_file = self.cache_dir / 'emails.csv'
        
        # Initialize CSV if it doesn't exist
        if not self.csv_file.exists():
            self._init_csv()
            
        logger.debug(f"[{agent_name}] Email storage initialized at {cache_dir}")

    def _init_csv(self):
        """Initialize CSV file with headers"""
        import csv
        headers = [
            'id', 'date', 'sender_email', 'sender_name', 'subject', 
            'body_text', 'label', 'confidence', 'source_folder', 'processing_state', 'saved_at'
        ]
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def _append_to_csv(self, email_data: Dict[str, Any]):
        """
        Append email data to CSV file
        
        Args:
            email_data: Email data dictionary
        """
        import csv
        try:
            # Prepare row data
            classification = email_data.get('classification', {})
            row = [
                email_data.get('id', ''),
                email_data.get('date', ''),
                sanitize_text(email_data.get('from_email', '')),
                sanitize_text(email_data.get('from_name', '')),
                sanitize_text(email_data.get('subject', '')),
                sanitize_text(email_data.get('body_text', '')[:5000]),
                sanitize_text(classification.get('category', '')),
                classification.get('confidence', 0.0),
                sanitize_text(email_data.get('source_folder', '')),
                email_data.get('processing_state', 'unknown'),
                datetime.now().isoformat()
            ]
            
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to append to CSV: {e}")
    
    def save_email(self, email_data: Dict[str, Any], processing_state: str = "new"):
        """
        Save email metadata to storage
        
        Args:
            email_data: Parsed email data
            processing_state: Processing state (new, classified, actioned)
        """
        try:
            email_id = email_data['id']
            email_hash = email_data.get('hash', email_id)
            
            # Create email metadata (exclude raw bytes)
            metadata = {
                'id': email_id,
                'hash': email_hash,
                'message_id': email_data.get('message_id', ''),
                'subject': email_data.get('subject', ''),
                'from': email_data.get('from', ''),
                'from_email': email_data.get('from_email', ''),
                'from_name': email_data.get('from_name', ''),
                'to': email_data.get('to', ''),
                'date': email_data.get('date', ''),
                'date_parsed': str(email_data.get('date_parsed', '')),
                'size': email_data.get('size', 0),
                'body_text': email_data.get('body_text', ''),
                'body_html': email_data.get('body_html', ''),
                'has_attachments': email_data.get('has_attachments', False),
                'attachment_count': email_data.get('attachment_count', 0),
                'attachments': [
                    {
                        'filename': att['filename'],
                        'size': att['size'],
                        'content_type': att['content_type'],
                        'hash': att['hash']
                    }
                    for att in email_data.get('attachments', [])
                ],
                'age_days': email_data.get('age_days'),
                'processing_state': processing_state,
                'saved_at': datetime.now().isoformat(),
            }
            
            # Add classification if present
            if 'classification' in email_data:
                metadata['classification'] = email_data['classification']
            
            # Save to metadata file - REMOVED in favor of CSV
            # metadata_file = self.metadata_dir / f"{email_hash}.json"
            # with open(metadata_file, 'w') as f:
            #     json.dump(metadata, f, indent=2)
            
            logger.debug(f"[{self.agent_name}] Saved email {email_id} (hash: {email_hash})")
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to save email {email_data.get('id')}: {e}")
    
    def load_email(self, email_hash: str) -> Optional[Dict[str, Any]]:
        """
        Load email metadata from storage
        
        Args:
            email_hash: Email hash
        
        Returns:
            Email metadata or None if not found
        """
        try:
            metadata_file = self.metadata_dir / f"{email_hash}.json"
            
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            return metadata
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to load email {email_hash}: {e}")
            return None
    
    def email_exists(self, email_hash: str) -> bool:
        """
        Check if email has been processed recently
        
        Args:
            email_hash: Email hash
        
        Returns:
            True if email is in recent history
        """
        # Check recent hashes first
        if email_hash in self.get_recent_hashes():
            return True
            
        # Fallback to latest email check
        latest = self.get_latest_email_info()
        return latest.get('hash') == email_hash

    def get_latest_email_info(self) -> Dict[str, Any]:
        """
        Get info about the most recently processed email from state file
        
        Returns:
            Dictionary with 'hash' and 'date_parsed' (datetime) or empty dict
        """
        try:
            if not self.state_file.exists():
                return {}
            
            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
                    logger.warning(f"[{self.agent_name}] Corrupted state file detected, resetting: {e}")
                    state = {}
            else:
                state = {}
            
            latest = state.get('latest_email', {})
            if not latest:
                return {}
            
            # Convert date string back to datetime
            if 'date' in latest:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(latest['date'])
                latest['date_parsed'] = ensure_aware(dt)
            
            return latest
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to get latest email info: {e}")
            return {}

    def get_recent_hashes(self) -> List[str]:
        """
        Get list of recently processed email hashes
        
        Returns:
            List of email hashes
        """
        try:
            if not self.state_file.exists():
                return []
            
            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
                    logger.warning(f"[{self.agent_name}] Corrupted state file detected in get_recent_hashes: {e}")
                    state = {}
            else:
                state = {}
            
            return state.get('recent_hashes', [])
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to get recent hashes: {e}")
            return []

    def update_watermark(self, email_data: Dict[str, Any]):
        """
        Update the latest email info (watermark) in storage.
        This should be called after an email has been successfully processed.
        
        Args:
            email_data: Email data dictionary
        """
        self._update_latest_email(email_data)

    def _update_latest_email(self, metadata: Dict[str, Any]):
        """Update the latest email info and recent hashes in processing_state.json"""
        try:
            # Load current state first
            state = {}
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    try:
                        state = json.load(f)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        logger.warning(f"[{self.agent_name}] Failed to decode state file, starting with empty state")
                        state = {}
            
            # Check if we should update "latest_email" (watermark)
            current_latest = self.get_latest_email_info()
            new_date_str = metadata.get('date')
            
            should_update_latest = False
            if new_date_str:
                from email.utils import parsedate_to_datetime
                new_dt = parsedate_to_datetime(new_date_str)
                
                if not current_latest:
                    should_update_latest = True
                else:
                    current_dt = current_latest.get('date_parsed')
                    if current_dt is None or ensure_aware(new_dt) > ensure_aware(current_dt):
                        should_update_latest = True
            
            if should_update_latest:
                state['latest_email'] = {
                    'hash': metadata.get('hash'),
                    'date': new_date_str,
                    'subject': metadata.get('subject')
                }
            
            # Update recent_hashes
            recent_hashes = state.get('recent_hashes', [])
            new_hash = metadata.get('hash')
            if new_hash and new_hash not in recent_hashes:
                recent_hashes.append(new_hash)
                # Keep last 200 hashes
                if len(recent_hashes) > 200:
                    recent_hashes = recent_hashes[-200:]
                state['recent_hashes'] = recent_hashes
            
            state['updated_at'] = datetime.now().isoformat()
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            if should_update_latest:
                logger.debug(f"[{self.agent_name}] Updated latest email state: {metadata.get('subject')}")
                
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to update latest email state: {e}")
    
    def update_processing_state(self, email_hash: str, state: str):
        """
        Update processing state for an email (Not supported in minimum storage mode)
        """
        pass
    
    def update_classification(self, email_hash: str, classification: Dict[str, Any], email_data: Optional[Dict[str, Any]] = None):
        """
        Update classification for an email and append to CSV
        
        Args:
            email_hash: Email hash
            classification: Classification data
            email_data: Full email data (required for CSV logging)
        """
        try:
            # Append to CSV if full data is provided
            if email_data:
                # Ensure classification is in email_data
                email_data['classification'] = classification
                email_data['processing_state'] = 'classified'
                self._append_to_csv(email_data)
                logger.debug(f"[{self.agent_name}] Appended classified email {email_hash} to CSV")
            else:
                logger.warning(f"[{self.agent_name}] No email data provided for CSV logging for {email_hash}")
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to update classification for {email_hash}: {e}")
    
    def get_all_emails(self) -> List[Dict[str, Any]]:
        """
        Get all cached emails (Not supported in minimum storage mode)
        
        Returns:
            Empty list
        """
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get email cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'total_emails': 'N/A (Minimum Storage)',
            'by_state': {},
            'total_size': 0,
            'with_attachments': 0,
        }
    
    def cleanup_old_emails(self, days: int = 90):
        """
        Clean up emails older than specified days
        
        Args:
            days: Age threshold in days
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            index = self._load_index()
            removed_count = 0
            
            for email_hash, email_info in list(index.items()):
                email_data = self.load_email(email_hash)
                
                if email_data:
                    saved_at = datetime.fromisoformat(email_data.get('saved_at', ''))
                    
                    if saved_at < cutoff_date:
                        # Remove metadata file
                        metadata_file = self.metadata_dir / f"{email_hash}.json"
                        metadata_file.unlink()
                        
                        # Remove from index
                        del index[email_hash]
                        removed_count += 1
            
            # Save updated index
            self._save_index(index)
            
            logger.info(f"[{self.agent_name}] Cleaned up {removed_count} old emails")
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to cleanup old emails: {e}")


if __name__ == "__main__":
    # Test email storage
    import sys
    from datetime import timedelta
    
    logging.basicConfig(level=logging.INFO)
    
    # Create test storage
    test_dir = Path(__file__).parent.parent.parent / 'data' / 'test_storage'
    storage = EmailStorage(test_dir, "test")
    
    print("\n[Test] Creating test email...")
    test_email = {
        'id': '12345',
        'hash': 'abc123',
        'message_id': '<test@example.com>',
        'subject': 'Test Email',
        'from': 'Test <test@example.com>',
        'from_email': 'test@example.com',
        'from_name': 'Test',
        'to': 'recipient@test.com',
        'date': str(datetime.now()),
        'date_parsed': datetime.now(),
        'size': 1024,
        'body_text': 'Test body',
        'body_html': '<p>Test body</p>',
        'has_attachments': False,
        'attachment_count': 0,
        'attachments': [],
        'age_days': 5,
    }
    
    print("[Test] Saving email...")
    storage.save_email(test_email, "new")
    print("✓ Email saved")
    
    print("\n[Test] Loading email...")
    loaded = storage.load_email('abc123')
    print(f"✓ Email loaded: {loaded['subject']}")
    
    print("\n[Test] Updating processing state...")
    storage.update_processing_state('abc123', 'classified')
    print("✓ State updated")
    
    print("\n[Test] Getting stats...")
    stats = storage.get_stats()
    print(f"✓ Stats: {stats}")
    
    print("\n[Test] Getting emails by state...")
    emails = storage.get_emails_by_state('classified')
    print(f"✓ Found {len(emails)} classified emails")
    
    print("\n✓ All tests passed!")
