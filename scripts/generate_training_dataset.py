#!/usr/bin/env python3
"""
Generate Training Dataset for Email Classification

Fetches emails from Gmail and generates a training dataset with rule-based labels.
Fetches from three sources:
- 3000 from Inbox
- 3000 from All Mail (excluding Inbox)
- 3000 from Trash

Usage:
    python scripts/generate_training_dataset.py [--dry-run] [--limit N]
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import ConfigLoader
from src.agents.email import GmailClient, EmailParser
from src.agents.classifier import EmailClassifier
from src.utils.text_utils import sanitize_text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatasetGenerator:
    """Generate training dataset from Gmail emails"""
    
    def __init__(self, config_path: Path, dry_run: bool = False):
        """
        Initialize dataset generator
        
        Args:
            config_path: Path to agent config file
            dry_run: If True, only fetch a small sample
        """
        self.dry_run = dry_run
        
        # Load config
        logger.info("Loading configuration...")
        self.config = ConfigLoader(config_path)
        
        # Initialize components
        gmail_creds = self.config.get('email', 'credentials_path')
        gmail_creds_path = Path(gmail_creds) if gmail_creds else Path('config/secrets/gmail_credentials.json')
        
        self.gmail_client = GmailClient(
            email_address=self.config.get('email', 'address'),
            token_path=self.config.oauth_token_path,
            credentials_path=gmail_creds_path,
            agent_name="dataset_generator"
        )
        
        self.email_parser = EmailParser("dataset_generator")
        
        # Initialize classifier for rule-based labeling
        self.classifier = EmailClassifier(
            model_path=None,
            use_model=False,  # Use rule-based classification
            agent_name="dataset_generator"
        )
        
        logger.info("✓ Initialized dataset generator")
    
    def list_available_folders(self) -> List[str]:
        """
        List all available IMAP folders
        
        Returns:
            List of folder names
        """
        folders = []
        try:
            with self.gmail_client as client:
                status, folder_list = client.imap.list()
                if status == 'OK':
                    for folder_data in folder_list:
                        # Parse folder name from IMAP response
                        # Format: (\\HasNoChildren) "/" "INBOX"
                        folder_str = folder_data.decode() if isinstance(folder_data, bytes) else folder_data
                        # Extract folder name (last quoted part)
                        parts = folder_str.split('"')
                        if len(parts) >= 3:
                            folder_name = parts[-2]
                            folders.append(folder_name)
                    
                    logger.info(f"Available folders: {folders}")
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
        
        return folders
    
    def fetch_from_folder(self, folder: str, limit: int, exclude_inbox: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch emails from a specific folder
        
        Args:
            folder: IMAP folder name
            limit: Maximum number of emails to fetch
            exclude_inbox: If True, exclude emails that are in Inbox
        
        Returns:
            List of parsed email dictionaries
        """
        logger.info(f"Fetching up to {limit} emails from {folder}...")
        
        emails = []
        
        try:
            with self.gmail_client as client:
                # Select folder (use readonly mode)
                status, _ = client.imap.select(folder, readonly=True)
                
                if status != 'OK':
                    logger.error(f"Failed to select folder: {folder}")
                    return emails
                
                # Search for all emails
                search_query = 'ALL'
                status, email_ids = client.imap.search(None, search_query)
                
                if status != 'OK':
                    logger.error(f"Search failed in folder: {folder}")
                    return emails
                
                # Get list of email IDs
                id_list = email_ids[0].split()
                
                if not id_list:
                    logger.warning(f"No emails found in {folder}")
                    return emails
                
                # Take most recent emails (reverse order)
                id_list = id_list[-limit:] if len(id_list) > limit else id_list
                id_list = list(reversed(id_list))  # Most recent first
                
                logger.info(f"Found {len(id_list)} emails in {folder}, fetching...")
                
                # Track inbox email IDs if we need to exclude them later
                inbox_ids = set()
                if exclude_inbox:
                    # We'll track emails we've already fetched from inbox
                    # This is simpler than checking IMAP flags
                    pass
                
                # Fetch emails
                for i, email_id in enumerate(id_list, 1):
                    try:
                        # Fetch email data
                        email_data = client._fetch_email_by_id(email_id)
                        
                        if not email_data:
                            continue
                        
                        # Parse email
                        parsed = self.email_parser.parse(email_data)
                        
                        # Add source folder
                        parsed['source_folder'] = folder
                        
                        emails.append(parsed)
                        
                        if i % 100 == 0:
                            logger.info(f"  Fetched {i}/{len(id_list)} emails from {folder}")
                    
                    except Exception as e:
                        logger.error(f"Failed to fetch email {email_id}: {e}")
                        continue
                
                logger.info(f"✓ Fetched {len(emails)} emails from {folder}")
        
        except Exception as e:
            logger.error(f"Error fetching from {folder}: {e}")
        
        return emails
    
    def generate_dataset(self, output_dir: Path, limit_per_folder: int = 3000) -> Dict[str, Any]:
        """
        Generate training dataset and save to CSV incrementally
        
        Args:
            output_dir: Directory to save output files
            limit_per_folder: Maximum emails to fetch per folder
        
        Returns:
            Dataset dictionary with emails and metadata
        """
        # Initialize CSV file
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = output_dir / f"email_dataset_{timestamp}.csv"
        
        import csv
        csv_headers = [
            'id', 'date', 'sender_email', 'sender_name', 'subject', 
            'body_text', 'label', 'confidence', 'source_folder'
        ]
        
        # Open CSV file for writing (will keep open or reopen in loop? keeping open is better but complex if logic is split)
        # We'll open and close for now or use a context manager if we can wrap the whole logic.
        # Simpler: Open file, write header, then append in loop.
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_headers)
            writer.writeheader()
        
        logger.info(f"Initialized CSV output at {csv_file}")

        # First, list available folders to help with debugging
        logger.info("\n" + "="*60)
        logger.info("Listing available Gmail folders...")
        logger.info("="*60)
        available_folders = self.list_available_folders()
        
        all_emails = []
        inbox_message_ids = set()  # Track inbox message IDs
        
        # Fetch from Inbox
        logger.info("\n" + "="*60)
        logger.info("Fetching from INBOX")
        logger.info("="*60)
        inbox_emails = self.fetch_from_folder('INBOX', limit_per_folder)
        all_emails.extend(inbox_emails)
        
        # Track message IDs from inbox
        for email in inbox_emails:
            if 'message_id' in email:
                inbox_message_ids.add(email['message_id'])
        
        logger.info(f"Tracked {len(inbox_message_ids)} inbox message IDs for exclusion")
        
        # Fetch from All Mail (excluding Inbox)
        # Gmail uses "[Gmail]/All Mail" but in IMAP it's often just "All Mail" or needs escaping
        logger.info("\n" + "="*60)
        logger.info("Fetching from All Mail (excluding Inbox)")
        logger.info("="*60)
        
        # Try different folder name variations for All Mail
        allmail_emails = []
        for folder_name in ['[Gmail]/All Mail', '"[Gmail]/All Mail"', 'All Mail']:
            try:
                all_fetched = self.fetch_from_folder(folder_name, limit_per_folder * 2, exclude_inbox=False)
                # Filter out emails that are in inbox
                allmail_emails = [
                    email for email in all_fetched 
                    if email.get('message_id') not in inbox_message_ids
                ][:limit_per_folder]  # Limit after filtering
                
                if allmail_emails:
                    logger.info(f"✓ Successfully fetched {len(allmail_emails)} emails from {folder_name} (after excluding inbox)")
                    break
            except Exception as e:
                logger.debug(f"Failed to fetch from {folder_name}: {e}")
                continue
        
        if not allmail_emails:
            logger.warning("Could not fetch from All Mail folder - trying alternative approach")
        
        all_emails.extend(allmail_emails)
        
        # Fetch from Trash
        logger.info("\n" + "="*60)
        logger.info("Fetching from Trash")
        logger.info("="*60)
        
        # Try different folder name variations for Trash
        trash_emails = []
        for folder_name in ['[Gmail]/Trash', '"[Gmail]/Trash"', 'Trash']:
            try:
                trash_emails = self.fetch_from_folder(folder_name, limit_per_folder)
                if trash_emails:
                    logger.info(f"✓ Successfully fetched from {folder_name}")
                    break
            except Exception as e:
                logger.debug(f"Failed to fetch from {folder_name}: {e}")
                continue
        
        if not trash_emails:
            logger.warning("Could not fetch from Trash folder")
        
        all_emails.extend(trash_emails)
        
        # Label emails using rule-based classifier
        logger.info("\n" + "="*60)
        logger.info(f"Labeling {len(all_emails)} emails using rule-based classifier")
        logger.info("="*60)
        
        labeled_emails = []
        label_counts = {'transactions': 0, 'feed': 0, 'promotions': 0, 'inbox': 0}
        
        # Open CSV for appending
        csv_f = open(csv_file, 'a', newline='', encoding='utf-8')
        csv_writer = csv.DictWriter(csv_f, fieldnames=csv_headers)
        
        try:
            for i, email in enumerate(all_emails, 1):
                try:
                    # Classify email
                    classification = self.classifier.classify(email)
                    
                    # Prepare dataset entry
                    entry = {
                        'id': email.get('id', ''),
                        'subject': email.get('subject', ''),
                        'sender_name': email.get('from_name', ''),
                        'sender_email': email.get('from_email', ''),
                        'body_text': email.get('body_text', '')[:2000],  # Limit body length
                        'label': classification['category'],
                        'source_folder': email.get('source_folder', 'unknown'),
                        'confidence': classification['confidence'],
                        'date': email.get('date', '')
                    }
                    
                    # Prepare CSV row (matching headers)
                    csv_row = {
                        'id': entry['id'],
                        'date': entry['date'],
                        'sender_email': sanitize_text(entry['sender_email']),
                        'sender_name': sanitize_text(entry['sender_name']),
                        'subject': sanitize_text(entry['subject']),
                        'body_text': sanitize_text(entry['body_text'][:5000]),
                        'label': sanitize_text(entry['label']),
                        'confidence': entry['confidence'],
                        'source_folder': sanitize_text(entry['source_folder'])
                    }
                    
                    # Write to CSV immediately
                    csv_writer.writerow(csv_row)
                    csv_f.flush() # Ensure it's written to disk
                    
                    labeled_emails.append(entry)
                    label_counts[classification['category']] += 1
                    
                    if i % 100 == 0:
                        logger.info(f"  Labeled {i}/{len(all_emails)} emails")
                
                except Exception as e:
                    logger.error(f"Failed to label email {i}: {e}")
                    continue
        finally:
            csv_f.close()
        
        logger.info(f"✓ Labeled {len(labeled_emails)} emails")
        logger.info(f"✓ CSV saved incrementally to {csv_file}")
        
        # Create dataset
        dataset = {
            'emails': labeled_emails,
            'metadata': {
                'total_emails': len(labeled_emails),
                'by_folder': {
                    'INBOX': len(inbox_emails),
                    'All Mail': len(allmail_emails),
                    'Trash': len(trash_emails)
                },
                'by_label': label_counts,
                'generated_at': datetime.now().isoformat(),
                'generator': 'rule_based_classifier'
            }
        }
        
        return dataset
    
    def save_dataset(self, dataset: Dict[str, Any], output_dir: Path):
        """
        Save dataset to JSON file
        
        Args:
            dataset: Dataset dictionary
            output_dir: Output directory
        """
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"email_dataset_{timestamp}.json"
        
        # Save to file
        logger.info(f"\nSaving dataset to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Dataset saved to {output_file}")
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("DATASET SUMMARY")
        logger.info("="*60)
        logger.info(f"Total emails: {dataset['metadata']['total_emails']}")
        logger.info(f"\nBy folder:")
        for folder, count in dataset['metadata']['by_folder'].items():
            logger.info(f"  {folder}: {count}")
        logger.info(f"\nBy label:")
        for label, count in dataset['metadata']['by_label'].items():
            logger.info(f"  {label}: {count}")
        logger.info("="*60)
        logger.info(f"\n✓ Dataset ready for training!")
        logger.info(f"  File: {output_file}")
        logger.info(f"\nNext steps:")
        logger.info(f"  1. Review and correct labels manually")
        logger.info(f"  2. Transfer to laptop: scp {output_file} laptop:~/data/")
        logger.info(f"  3. Train model: python scripts/train_email_classifier.py")


def main():
    parser = argparse.ArgumentParser(description='Generate email classification training dataset')
    parser.add_argument(
        '--config',
        type=Path,
        default=Path('config/agents/personal.yaml'),
        help='Path to agent config file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/training'),
        help='Output directory for dataset'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=3000,
        help='Maximum emails to fetch per folder'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Fetch only 10 emails per folder for testing'
    )
    
    args = parser.parse_args()
    
    # Adjust limit for dry run
    if args.dry_run:
        logger.info("DRY RUN MODE: Fetching only 10 emails per folder")
        limit = 10
    else:
        limit = args.limit
    
    try:
        # Generate dataset (saves CSV incrementally)
        generator = DatasetGenerator(args.config, dry_run=args.dry_run)
        dataset = generator.generate_dataset(output_dir=args.output, limit_per_folder=limit)
        
        # Save dataset (JSON summary)
        generator.save_dataset(dataset, args.output)
        
        logger.info("\n✓ Dataset generation complete!")
    
    except KeyboardInterrupt:
        logger.info("\n\nDataset generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Dataset generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
