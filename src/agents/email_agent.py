"""
Email Agent for MAE

Main email processing agent that ties together all email components.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.utils.datetime_utils import ensure_aware

logger = logging.getLogger(__name__)


class EmailAgent:
    """Main email processing agent"""
    
    def __init__(self, config, token_manager):
        """
        Initialize email agent
        
        Args:
            config: ConfigLoader instance
            token_manager: TokenManager instance
        """
        self.config = config
        self.token_manager = token_manager
        self.agent_name = config.get_agent_name()
        
        # Import components (lazy import to avoid import errors if dependencies missing)
        from src.agents.email import GmailClient, EmailParser, EmailStorage
        from src.agents.classifier import EmailClassifier, TopicMatcher, SenderManager
        from src.agents.actions import EmailDeleter
        from src.utils.credential_manager import CredentialManager
        
        # Get Gmail credentials path (default to config/secrets/gmail_credentials.json)
        gmail_creds = config.get('email', 'credentials_path')
        gmail_creds_path = Path(gmail_creds) if gmail_creds else Path('config/secrets/gmail_credentials.json')
        
        # Try to get app password from secure storage first
        service_creds = CredentialManager.get_credential(self.agent_name, 'gmail')
        app_password = None
        if service_creds and 'password' in service_creds:
            app_password = service_creds['password']
            logger.info(f"[{self.agent_name}] Using Gmail app password from secure storage")
        else:
            # Fallback to config
            app_password = config.get('email', 'app_password')
            if app_password:
                logger.warning(f"[{self.agent_name}] Using Gmail app password from plaintext config. Consider using scripts/setup_credentials.py for better security.")

        self.gmail_client = GmailClient(
            email_address=config.get('email', 'address'),
            agent_name=self.agent_name,
            app_password=app_password
        )
        
        self.email_parser = EmailParser(self.agent_name)
        self.email_storage = EmailStorage(config.email_cache_dir, self.agent_name)
        
        self.classifier = EmailClassifier(
            model_path=Path(self.config.get('classification', 'model_path', 'models/email_classifier.rknn')),
            tokenizer_path=Path(self.config.get('classification', 'tokenizer_path', 'models/tokenizer')),
            use_model=self.config.get('classification', 'use_ai_model', False),
            agent_name=self.agent_name,
            debug_log_path=config.agent_data_dir / 'classification_debug.csv'
        )
        
        self.topic_matcher = TopicMatcher(
            topics_of_interest=config.get('classification', 'topics_i_care_about', []),
            agent_name=self.agent_name
        )
        
        self.sender_manager = SenderManager(
            whitelisted=config.get('classification', 'whitelisted_senders', []),
            blacklisted=config.get('classification', 'blacklisted_senders', []),
            agent_name=self.agent_name
        )
        
        self.email_deleter = EmailDeleter(
            config=config.get('deletion'),
            agent_name=self.agent_name
        )
        
        # Dry-run mode (prevents actual email actions)
        self.dry_run = config.get('deletion', 'dry_run', True)
        
        logger.info(f"[{self.agent_name}] Email agent initialized (dry_run={self.dry_run})")
    
    def run(self):
        """Run the email processing agent"""
        from datetime import datetime
        import csv
        from pathlib import Path
        
        logger.info(f"[{self.agent_name}] Starting email agent run")
        
        # Track run statistics
        start_time = datetime.now()
        category_counts = {
            'transactions': 0,
            'feed': 0,
            'promotions': 0,
            'inbox': 0
        }
        
        try:
            # Acquire IMAP token and connect once for the entire run
            from src.orchestrator import TokenType
            with self.token_manager.token(TokenType.IMAP, self.agent_name):
                with self.gmail_client as client:
                    # Step 1: Fetch emails
                    emails = self._fetch_emails(client)
                    logger.info(f"[{self.agent_name}] Fetched {len(emails)} new emails")
                    
                    if not emails:
                        logger.info(f"[{self.agent_name}] No new emails to process")
                        # Log even if no emails processed
                        self._log_run_stats(start_time, datetime.now(), 0, category_counts)
                        return
                    
                    # Step 2: Process each email
                    for email_data in emails:
                        category = self._process_email(email_data, client)
                        if category:
                            category_counts[category] = category_counts.get(category, 0) + 1
                            # Update watermark only after successful processing
                            self.email_storage.update_watermark(email_data)
            
            # Step 3: Summary
            stats = self.email_storage.get_stats()
            logger.info(
                f"[{self.agent_name}] Run complete. "
                f"Total emails: {stats['total_emails']}, "
                f"By state: {stats['by_state']}"
            )
            
            # Log run statistics
            end_time = datetime.now()
            self._log_run_stats(start_time, end_time, len(emails), category_counts)
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Agent run failed: {e}", exc_info=True)
            raise
    
    def _log_run_stats(self, start_time, end_time, total_emails, category_counts):
        """Log run statistics to CSV file"""
        import csv
        from pathlib import Path
        
        stats_file = self.config.agent_data_dir / 'run_stats.csv'
        file_exists = stats_file.exists()
        
        try:
            with open(stats_file, 'a', newline='') as f:
                writer = csv.writer(f)
                
                # Write header if file is new
                if not file_exists:
                    writer.writerow([
                        'timestamp',
                        'duration_seconds',
                        'total_emails',
                        'transactions',
                        'feed',
                        'promotions',
                        'inbox'
                    ])
                
                # Write stats
                duration = (end_time - start_time).total_seconds()
                writer.writerow([
                    start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    f'{duration:.2f}',
                    total_emails,
                    category_counts.get('transactions', 0),
                    category_counts.get('feed', 0),
                    category_counts.get('promotions', 0),
                    category_counts.get('inbox', 0)
                ])
                
            logger.info(f"[{self.agent_name}] Run stats logged to {stats_file}")
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to log run stats: {e}")
    
    def _fetch_emails(self, client: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Fetch and parse new emails
        
        Args:
            client: Optional active GmailClient
            
        Returns:
            List of parsed email dictionaries
        """
        from datetime import datetime
        
        # Use provided client or create a temporary one
        if client:
            return self._fetch_emails_internal(client)
        
        from src.orchestrator import TokenType
        with self.token_manager.token(TokenType.IMAP, self.agent_name):
            with self.gmail_client as client:
                return self._fetch_emails_internal(client)

    def _fetch_emails_internal(self, client: Any) -> List[Dict[str, Any]]:
        """Internal implementation of _fetch_emails using an active client"""
        from datetime import datetime
        
        # Get fetch parameters from config
        limit = self.config.get('email', 'fetch_limit', 100)
        unread_only = self.config.get('email', 'unread_only', True)
        since_days = self.config.get('email', 'since_days', 7)
        
        # Get latest processed email info for incremental fetching
        latest_info = self.email_storage.get_latest_email_info()
        last_dt = latest_info.get('date_parsed')
        
        if last_dt:
            # Calculate since_days to cover at least until the last processed email
            # Add 1 day buffer to be safe
            days_since = (ensure_aware(datetime.now()) - ensure_aware(last_dt)).days + 1
            since_days = days_since
            logger.info(f"[{self.agent_name}] Incremental fetch: last processed email from {last_dt.strftime('%Y-%m-%d')}, using since_days={since_days}")
        
        # Fetch only headers first
        headers = client.fetch_headers(
            limit=limit,
            unread_only=unread_only,
            since_days=since_days
        )
        # Parse and filter emails
        
        parsed_emails = []
        skipped_count = 0
        already_processed_count = 0
        
        from email.utils import parsedate_to_datetime
        
        for header in headers:
            email_id = header['id']
            email_hash = self.email_parser._compute_hash(header['message_id'])
            
            # Parse date from header
            try:
                email_dt = parsedate_to_datetime(header['date'])
            except Exception:
                email_dt = None
            
            # Check if older than or same as last processed
            # Check if already processed (hash match)
            if self.email_storage.email_exists(email_hash):
                already_processed_count += 1
                logger.debug(f"[{self.agent_name}] Skipping already processed email (hash match): {header['subject']}")
                continue

            # Check if older than last processed (with buffer)
            if last_dt and email_dt:
                email_dt = ensure_aware(email_dt)
                last_dt = ensure_aware(last_dt)
                # Only skip if significantly older (e.g. > 2 days) to allow for out-of-order delivery
                if (last_dt - email_dt).days > 2:
                    skipped_count += 1
                    logger.debug(f"[{self.agent_name}] Skipping significantly older email (>2 days): {header['subject']} ({email_dt})")
                    continue
            
            # If we reach here, we need the full email
            logger.info(f"[{self.agent_name}] Fetching full content for: {header['subject']}")
            raw_email = client.fetch_full_email(email_id)
            if raw_email:
                parsed = self.email_parser.parse(raw_email)
                parsed_emails.append(parsed)
                # Save to storage (updates latest email info)
                self.email_storage.save_email(parsed, "new")
        
        if already_processed_count > 0 or skipped_count > 0:
            logger.info(f"[{self.agent_name}] Filtered {already_processed_count} already processed and {skipped_count} older emails")
        
        return parsed_emails
    
    def _process_email(self, email_data: Dict[str, Any], client: Optional[Any] = None) -> str:
        """
        Process a single email and return its category
        
        Args:
            email_data: Email data
            client: Optional active GmailClient
        """
        email_id = email_data.get('id')
        subject = email_data.get('subject', 'No Subject')
        
        logger.info(f"[{self.agent_name}] Processing: {subject}")
        
        try:
            # Step 1: Classify email
            import time
            start_time = time.time()
            classification = self.classifier.classify(email_data)
            inference_time_ms = (time.time() - start_time) * 1000
            
            logger.info(f"[{self.agent_name}]   Inference time: {inference_time_ms:.2f}ms")
            topic_match = self.topic_matcher.match(email_data)
            sender_status = self.sender_manager.get_status(email_data['from_email'])
            
            # Update storage with classification
            self.email_storage.update_classification(
                email_data['hash'],
                {
                    'category': classification['category'],
                    'confidence': classification['confidence'],
                    'method': classification['method'],
                    'topic_match': topic_match['matched'],
                    'topics': topic_match.get('topics', []),
                    'sender_status': sender_status
                },
                email_data # Pass full email data
            )
            
            logger.info(
                f"[{self.agent_name}]   Classification: {classification['category']} "
                f"(confidence: {classification['confidence']:.2f})"
            )
            logger.debug(f"[{self.agent_name}]   Input: {classification.get('input_text', 'N/A')}")
            
            
            # Step 2: Take actions based on category
            category = classification['category']
            
            # Check if action should be taken (respects config, whitelist, etc.)
            decision = self.email_deleter.should_act(
                email_data, classification, topic_match, sender_status
            )
            
            if decision['should_act']:
                action = decision['action']
                reason = decision['reason']
                
                if action == 'move_to_trash':
                    if self.dry_run:
                        logger.info(f"[{self.agent_name}]   Action: [DRY-RUN] Would move to trash. Reason: {reason}")
                    else:
                        logger.info(f"[{self.agent_name}]   Action: Moving to trash. Reason: {reason}")
                        try:
                            if client:
                                client.move_to_trash(email_data['id'])
                            else:
                                from src.orchestrator import TokenType
                                with self.token_manager.token(TokenType.IMAP, self.agent_name):
                                    with self.gmail_client as client_tmp:
                                        client_tmp.move_to_trash(email_data['id'])
                        except Exception as e:
                            logger.error(f"[{self.agent_name}]   Failed to move to trash: {e}")
                            
                elif action == 'apply_label':
                    label_name = 'MarkForDeletion'
                    if self.dry_run:
                        logger.info(f"[{self.agent_name}]   Action: [DRY-RUN] Would apply label '{label_name}'. Reason: {reason}")
                    else:
                        logger.info(f"[{self.agent_name}]   Action: Applying label '{label_name}'. Reason: {reason}")
                        try:
                            if client:
                                client.add_label(email_data['id'], label_name)
                            else:
                                from src.orchestrator import TokenType
                                with self.token_manager.token(TokenType.IMAP, self.agent_name):
                                    with self.gmail_client as client_tmp:
                                        client_tmp.add_label(email_data['id'], label_name)
                        except Exception as e:
                            logger.error(f"[{self.agent_name}]   Failed to apply label: {e}")
            
            elif category in ['transactions', 'feed']:
                # Mark as read and archive (move to All Mail)
                if self.dry_run:
                    logger.info(f"[{self.agent_name}]   Action: [DRY-RUN] Would mark read + archive ({category})")
                else:
                    logger.info(f"[{self.agent_name}]   Action: Mark read + archive ({category})")
                    try:
                        if client:
                            client.mark_as_read([email_data['id']])
                            client.move_to_all_mail(email_data['id'])
                        else:
                            # Fallback to temporary connection if no client provided
                            from src.orchestrator import TokenType
                            with self.token_manager.token(TokenType.IMAP, self.agent_name):
                                with self.gmail_client as client_tmp:
                                    client_tmp.mark_as_read([email_data['id']])
                                    client_tmp.move_to_all_mail(email_data['id'])
                    except Exception as e:
                        logger.error(f"[{self.agent_name}]   Failed to archive: {e}")
            
            elif category == 'promotions':
                # This means should_act was False for a promotions email
                reason = decision.get('reason', 'Unknown')
                logger.info(f"[{self.agent_name}]   Action: None (skipped promotional email. Reason: {reason})")
            
            elif category == 'inbox':
                # No action - stays in inbox
                logger.info(f"[{self.agent_name}]   Action: None (keeping in inbox)")
            
            # Update state to 'actioned'
            self.email_storage.update_processing_state(email_data['hash'], 'actioned')
            
            return category
        
        except Exception as e:
            logger.error(
                f"[{self.agent_name}] Failed to process email {email_id}: {e}",
                exc_info=True
            )
            return None
    

    def process_historical_emails(self, start_date: str, end_date: str, target_categories: List[str]):
        """
        Process historical emails within a date range
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            target_categories: List of categories to label (e.g. ['promotions'])
        """
        logger.info(f"[{self.agent_name}] Starting historical processing from {start_date} to {end_date}")
        logger.info(f"[{self.agent_name}] Target categories: {target_categories}")
        
        from src.orchestrator import TokenType
        
        with self.token_manager.token(TokenType.IMAP, self.agent_name):
            with self.gmail_client as client:
                # Get all folders
                folders = client.list_folders()
                logger.info(f"[{self.agent_name}] Found folders: {folders}")
                
                processed_count = 0
                labeled_count = 0
                
                for folder in folders:
                    # Skip Trash and Spam
                    if any(x in folder for x in ["Trash", "Spam", "Bin"]):
                        continue
                        
                    logger.info(f"[{self.agent_name}] Processing folder: {folder}")
                    
                    try:
                        # Fetch emails in range
                        emails = client.fetch_emails(
                            folder=folder,
                            limit=500,
                            unread_only=False,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        logger.info(f"[{self.agent_name}]   Fetched {len(emails)} emails in range")
                        
                        for raw_email_data in emails:
                            try:
                                # Parse email first
                                email_data = self.email_parser.parse(raw_email_data)
                                email_data['source_folder'] = folder
                                
                                # Classify
                                classification = self.classifier.classify(email_data)
                                category = classification['category']
                                
                                # Log to CSV
                                topic_match = self.topic_matcher.match(email_data)
                                sender_status = self.sender_manager.get_status(email_data['from_email'])
                                
                                self.email_storage.update_classification(
                                    email_data['hash'],
                                    {
                                        'category': category,
                                        'confidence': classification['confidence'],
                                        'method': classification['method'],
                                        'topic_match': topic_match['matched'],
                                        'topics': topic_match.get('topics', []),
                                        'sender_status': sender_status
                                    },
                                    email_data
                                )
                                
                                if category in target_categories:
                                    logger.info(
                                        f"[{self.agent_name}]   Marking as deletion candidate: {email_data['subject']} "
                                        f"({category}, conf: {classification.get('confidence', 0):.2f})"
                                    )
                                    logger.debug(f"[{self.agent_name}]   Input: {classification.get('input_text', 'N/A')}")
                                    
                                    if not self.dry_run:
                                        client.add_label(email_data['id'], "MarkedForDeletion")
                                        labeled_count += 1
                                    else:
                                        logger.info(f"[{self.agent_name}]   [DRY-RUN] Would add label 'MarkedForDeletion'")
                                        labeled_count += 1
                                        
                                processed_count += 1
                                
                            except Exception as e:
                                logger.error(f"[{self.agent_name}] Failed to process email {email_data['id']}: {e}")
                                
                    except Exception as e:
                        logger.error(f"[{self.agent_name}] Failed to process folder {folder}: {e}")
                        logger.info(f"[{self.agent_name}] Attempting to reconnect and continue with next folder...")
                        try:
                            client.disconnect()
                            client.connect()
                        except Exception as re:
                            logger.error(f"[{self.agent_name}] Reconnection failed: {re}")
                            
                logger.info(
                    f"[{self.agent_name}] Historical processing complete. "
                    f"Processed: {processed_count}, Labeled: {labeled_count}"
                )


if __name__ == "__main__":
    # Test email agent (requires full setup)
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("Email Agent - Integration Test")
    print("="*60)
    print("\nNOTE: This test requires:")
    print("1. OAuth credentials (Gmail + Calendar)")
    print("2. Agent configuration file")
    print("3. All dependencies installed")
    print("\nSkipping automated test. Use with real configuration.\n")
