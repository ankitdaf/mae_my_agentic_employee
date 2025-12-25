"""
Gmail Client for MAE

Handles Gmail OAuth 2.0 authentication and IMAP operations.
Supports fetching, marking, and deleting emails.
"""

import os
import json
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)


class GmailAuthError(Exception):
    """Raised when Gmail authentication fails"""
    pass


class GmailConnectionError(Exception):
    """Raised when Gmail connection fails"""
    pass


class GmailClient:
    """Gmail IMAP client with OAuth 2.0 authentication"""
    
    # Gmail IMAP settings
    IMAP_SERVER = "imap.gmail.com"
    IMAP_PORT = 993
    
    # OAuth 2.0 scopes
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',  # Read, send, delete emails
        'https://mail.google.com/'  # Full mail access for IMAP
    ]
    
    def __init__(self, email_address: str, token_path: Path, 
                 credentials_path: Path, agent_name: str = "unknown"):
        """
        Initialize Gmail client
        
        Args:
            email_address: Gmail address
            token_path: Path to store OAuth tokens
            credentials_path: Path to OAuth credentials JSON
            agent_name: Agent name for logging
        """
        self.email_address = email_address
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.agent_name = agent_name
        self.imap = None
        self.credentials = None
        
        logger.info(f"[{agent_name}] Initialized Gmail client for {email_address}")
    
    def authenticate(self) -> Credentials:
        """
        Authenticate with Gmail using OAuth 2.0
        
        Returns:
            Google OAuth credentials
        
        Raises:
            GmailAuthError: If authentication fails
        """
        creds = None
        
        # Check if token file exists
        if self.token_path.exists():
            try:
                logger.info(f"[{self.agent_name}] Loading existing OAuth tokens...")
                with open(self.token_path, 'r') as token_file:
                    token_data = json.load(token_file)
                    creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Failed to load tokens: {e}")
                creds = None
        
        # Refresh or obtain new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info(f"[{self.agent_name}] Refreshing expired OAuth tokens...")
                    creds.refresh(Request())
                    logger.info(f"[{self.agent_name}] Tokens refreshed successfully")
                except Exception as e:
                    logger.error(f"[{self.agent_name}] Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                # Need new authorization
                if not self.credentials_path.exists():
                    raise GmailAuthError(
                        f"OAuth credentials not found: {self.credentials_path}\n"
                        f"See docs/google_calendar_setup.md for setup instructions"
                    )
                
                try:
                    logger.info(f"[{self.agent_name}] Starting OAuth authorization flow...")
                    logger.info(
                        f"[{self.agent_name}] Running in headless mode - please authorize via URL"
                    )
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path),
                        self.SCOPES
                    )
                    
                    # Manual OAuth flow for headless servers
                    # Generate authorization URL
                    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'  # Out-of-band mode
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    
                    # Print URL for user to visit
                    print("\n" + "="*70)
                    print("OAUTH AUTHORIZATION REQUIRED")
                    print("="*70)
                    print("\nPlease visit this URL to authorize this application:")
                    print(f"\n{auth_url}\n")
                    print("After authorizing, you will receive an authorization code.")
                    print("="*70 + "\n")
                    
                    # Prompt for authorization code
                    auth_code = input("Enter the authorization code: ").strip()
                    
                    # Exchange code for credentials
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    
                    logger.info(f"[{self.agent_name}] Authorization successful!")
                
                except Exception as e:
                    raise GmailAuthError(f"OAuth authorization failed: {e}")
            
            # Save credentials for future use
            try:
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, 'w') as token_file:
                    token_file.write(creds.to_json())
                logger.info(f"[{self.agent_name}] OAuth tokens saved to {self.token_path}")
                
                # Set restrictive permissions
                os.chmod(self.token_path, 0o600)
            
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Failed to save tokens: {e}")
        
        self.credentials = creds
        return creds
    
    def connect(self):
        """
        Connect to Gmail IMAP server
        
        Raises:
            GmailConnectionError: If connection fails
        """
        if not self.credentials:
            self.authenticate()
        
        try:
            logger.info(f"[{self.agent_name}] Connecting to Gmail IMAP...")
            self.imap = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
            
            # Authenticate with OAuth (XOAUTH2)
            auth_string = self._generate_oauth_string()
            try:
                self.imap.authenticate('XOAUTH2', lambda x: auth_string)
            except imaplib.IMAP4.error as e:
                # Check for authentication failure
                error_msg = str(e)
                if "Invalid credentials" in error_msg or "AUTHENTICATIONFAILED" in error_msg:
                    logger.warning(f"[{self.agent_name}] Authentication failed (token likely expired), forcing refresh...")
                    
                    # Close the failed connection
                    try:
                        self.imap.logout()
                    except:
                        pass
                    self.imap = None
                    
                    # Force refresh by marking credentials as expired
                    if self.credentials and self.credentials.refresh_token:
                        try:
                            self.credentials.refresh(Request())
                            logger.info(f"[{self.agent_name}] Tokens refreshed successfully")
                            
                            # Save new tokens
                            self._save_tokens()
                            
                            # Create NEW connection and retry authentication
                            logger.info(f"[{self.agent_name}] Creating new IMAP connection for retry...")
                            self.imap = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
                            auth_string = self._generate_oauth_string()
                            self.imap.authenticate('XOAUTH2', lambda x: auth_string)
                            logger.info(f"[{self.agent_name}] Re-authentication successful")
                            logger.info(f"[{self.agent_name}] Connected to Gmail IMAP successfully")
                            return
                        except Exception as refresh_error:
                            logger.error(f"[{self.agent_name}] Token refresh failed during reconnect: {refresh_error}")
                            raise GmailAuthError(f"Authentication failed and token refresh failed: {refresh_error}")
                
                # Re-raise if not handled
                raise
            
            logger.info(f"[{self.agent_name}] Connected to Gmail IMAP successfully")
        
        except Exception as e:
            raise GmailConnectionError(f"Failed to connect to Gmail: {e}")

    def _save_tokens(self):
        """Helper to save credentials to file"""
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as token_file:
                token_file.write(self.credentials.to_json())
            logger.info(f"[{self.agent_name}] OAuth tokens saved to {self.token_path}")
            os.chmod(self.token_path, 0o600)
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to save tokens: {e}")
    
    def _generate_oauth_string(self) -> bytes:
        """
        Generate OAuth 2.0 authentication string for IMAP
        
        Returns:
            Raw OAuth bytes (imaplib will base64-encode it)
        """
        # XOAUTH2 format: user=<email>\x01auth=Bearer <token>\x01\x01
        auth_string = f"user={self.email_address}\x01auth=Bearer {self.credentials.token}\x01\x01"
        return auth_string.encode('utf-8')
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.imap:
            try:
                self.imap.logout()
                logger.info(f"[{self.agent_name}] Disconnected from Gmail IMAP")
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Error during disconnect: {e}")
            finally:
                self.imap = None

    def _ensure_connection(self):
        """Ensure IMAP connection is active, reconnect if needed"""
        if self.imap is None:
            self.connect()
            return

        try:
            # Check connection status with NOOP
            status, _ = self.imap.noop()
            if status != 'OK':
                logger.warning(f"[{self.agent_name}] Connection lost (NOOP failed), reconnecting...")
                self.disconnect()
                self.connect()
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Connection check failed: {e}, reconnecting...")
            self.disconnect()
            self.connect()

    def list_folders(self) -> List[str]:
        """
        List all available IMAP folders
        
        Returns:
            List of folder names
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                
                status, folders = self.imap.list()
                if status != 'OK':
                    raise GmailConnectionError("Failed to list folders")
                    
                folder_names = []
                for folder in folders:
                    # Parse folder name from IMAP response
                    # Format: (\HasNoChildren) "/" "INBOX"
                    if not folder: continue
                    name = folder.decode().split(' "/" ')[-1].strip('"')
                    folder_names.append(name)
                    
                return folder_names
                
            except (GmailConnectionError, Exception) as e:
                logger.warning(f"[{self.agent_name}] list_folders failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise GmailConnectionError(f"Failed to list folders after {max_retries} attempts: {e}")
                self.disconnect()  # Force reconnect on next attempt
                import time
                time.sleep(2 * (attempt + 1))  # Exponential backoff

    def add_label(self, email_id: str, label_name: str):
        """
        Add a label to an email (Gmail treats labels as folders/flags)
        
        Args:
            email_id: Email UID
            label_name: Label to add
        """
        if not self.imap:
            self.connect()
            
        try:
            # In Gmail IMAP, adding a label is done by copying to the folder (label)
            # OR by using X-GM-LABELS extension if supported, but standard IMAP way is COPY
            # However, for "MarkedForDeletion", we might want to just set a flag or move it?
            # Actually, Gmail IMAP extensions allow STORE +X-GM-LABELS
            
            # Use UID STORE
            resp, _ = self.imap.uid('store', email_id.encode(), '+X-GM-LABELS', f'"{label_name}"')
            if resp != 'OK':
                logger.warning(f"[{self.agent_name}] Failed to add label {label_name} to {email_id}")
            else:
                logger.info(f"[{self.agent_name}] Added label {label_name} to {email_id}")
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error adding label: {e}")

    
    def fetch_headers(self, folder: str = "INBOX", limit: int = 100,
                      unread_only: bool = False, 
                      since_days: Optional[int] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch only email headers from Gmail
        
        Returns:
            List of email dictionaries with minimal metadata (id, date, subject, from, message_id)
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                quoted_folder = f'"{folder}"' if ' ' in folder else folder
                try:
                    status, _ = self.imap.select(quoted_folder)
                except Exception:
                    status, _ = self.imap.select(folder)
                    
                if status != 'OK':
                    logger.warning(f"[{self.agent_name}] Failed to select folder: {folder}")
                    return []
                
                search_criteria = []
                if unread_only:
                    search_criteria.append('UNSEEN')
                
                if start_date and end_date:
                    s_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%d-%b-%Y")
                    e_date = datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%b-%Y")
                    search_criteria.append(f'SINCE {s_date}')
                    search_criteria.append(f'BEFORE {e_date}')
                elif since_days:
                    since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
                    search_criteria.append(f'SINCE {since_date}')
                
                search_query = ' '.join(search_criteria) if search_criteria else 'ALL'
                logger.info(f"[{self.agent_name}] Searching emails in {folder}: {search_query}")
                
                # Use UID SEARCH
                status, email_ids = self.imap.uid('search', None, search_query)
                
                if status != 'OK':
                    raise GmailConnectionError(f"Email search failed")
                
                id_list = email_ids[0].split()
                if not id_list:
                    return []
                
                id_list = id_list[-limit:] if len(id_list) > limit else id_list
                logger.info(f"[{self.agent_name}] Fetching headers for {len(id_list)} emails...")
                
                headers = []
                for email_id in id_list:
                    try:
                        # Fetch only headers using UID FETCH
                        status, msg_data = self.imap.uid('fetch', email_id, '(BODY.PEEK[HEADER])')
                        if status != 'OK': continue
                        
                        # msg_data structure with UID fetch might be slightly different or same
                        # Usually it returns a list where one element is the tuple (seq_num (UID uid) body)
                        # But imaplib might just return the body if we are lucky, or we need to parse.
                        # Actually imaplib returns [(b'1 (UID 123 BODY[HEADER] {123}', b'Header...'), b')']
                        
                        raw_email = None
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                raw_email = response_part[1]
                                break
                        
                        if not raw_email:
                            continue

                        msg = email.message_from_bytes(raw_email)
                        
                        headers.append({
                            'id': email_id.decode(), # This is now the UID
                            'subject': self._decode_header(msg.get('Subject', 'No Subject')),
                            'from': self._decode_header(msg.get('From', 'Unknown')),
                            'to': self._decode_header(msg.get('To', '')),
                            'date': msg.get('Date', ''),
                            'message_id': msg.get('Message-ID', ''),
                            'size': int(msg.get('Content-Length', 0)) # Approximate
                        })
                    except Exception as e:
                        logger.error(f"[{self.agent_name}] Failed to fetch header for {email_id}: {e}")
                
                return headers
            except Exception as e:
                if attempt == max_retries - 1: raise
                self.disconnect()
                import time
                time.sleep(1)

    def fetch_full_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full email content by UID"""
        try:
            self._ensure_connection()
            return self._fetch_email_by_id(email_id.encode())
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to fetch full email {email_id}: {e}")
            return None

    def fetch_emails(self, folder: str = "INBOX", limit: int = 100,
                     unread_only: bool = False, 
                     since_days: Optional[int] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch emails from Gmail
        
        Args:
            folder: IMAP folder name (default: INBOX)
            limit: Maximum number of emails to fetch
            unread_only: Only fetch unread emails
            since_days: Only fetch emails from last N days
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            List of email dictionaries with metadata
        
        Raises:
            GmailConnectionError: If fetch fails
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
            
                # Select folder
                # Handle folder names with spaces
                quoted_folder = f'"{folder}"' if ' ' in folder else folder
                try:
                    status, messages = self.imap.select(quoted_folder)
                except Exception:
                    # Retry once with unquoted if failed
                    status, messages = self.imap.select(folder)
                    
                if status != 'OK':
                    logger.warning(f"[{self.agent_name}] Failed to select folder: {folder}")
                    return []
                
                # Build search criteria
                search_criteria = []
                
                if unread_only:
                    search_criteria.append('UNSEEN')
                
                if start_date and end_date:
                    # IMAP date format: DD-Mon-YYYY
                    s_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%d-%b-%Y")
                    e_date = datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%b-%Y")
                    search_criteria.append(f'SINCE {s_date}')
                    search_criteria.append(f'BEFORE {e_date}')
                elif since_days:
                    since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
                    search_criteria.append(f'SINCE {since_date}')
                
                search_query = ' '.join(search_criteria) if search_criteria else 'ALL'
                
                # Search for emails using UID SEARCH
                logger.info(f"[{self.agent_name}] Searching emails in {folder}: {search_query}")
                status, email_ids = self.imap.uid('search', None, search_query)
                
                if status != 'OK':
                    raise GmailConnectionError(f"Email search failed")
                
                # Get list of email IDs (UIDs)
                id_list = email_ids[0].split()
                
                if not id_list:
                    logger.info(f"[{self.agent_name}] No emails found matching criteria")
                    return []
                
                # Limit number of emails
                id_list = id_list[-limit:] if len(id_list) > limit else id_list
                
                logger.info(f"[{self.agent_name}] Fetching {len(id_list)} emails...")
                
                emails = []
                for email_id in id_list:
                    try:
                        email_data = self._fetch_email_by_id(email_id)
                        if email_data:
                            emails.append(email_data)
                    except Exception as e:
                        logger.error(f"[{self.agent_name}] Failed to fetch email {email_id}: {e}")
                
                logger.info(f"[{self.agent_name}] Successfully fetched {len(emails)} emails")
                return emails
            
            except (GmailConnectionError, Exception) as e:
                logger.warning(f"[{self.agent_name}] fetch_emails failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise GmailConnectionError(f"Failed to fetch emails after {max_retries} attempts: {e}")
                self.disconnect()
                import time
                time.sleep(2 * (attempt + 1))
    
    def _fetch_email_by_id(self, email_id: bytes) -> Optional[Dict[str, Any]]:
        """
        Fetch a single email by ID
        
        Args:
            email_id: Email ID (from IMAP search)
        
        Returns:
            Email metadata dictionary or None
        """
        try:
            # Fetch email data using UID FETCH
            status, msg_data = self.imap.uid('fetch', email_id, '(BODY.PEEK[])')
            
            if status != 'OK':
                return None
            
            # Parse email
            raw_email = None
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw_email = response_part[1]
                    break
            
            if not raw_email:
                return None

            msg = email.message_from_bytes(raw_email)
            
            # Extract metadata
            email_data = {
                'id': email_id.decode(),
                'message_id': msg.get('Message-ID', ''),
                'subject': self._decode_header(msg.get('Subject', '')),
                'from': self._decode_header(msg.get('From', '')),
                'to': self._decode_header(msg.get('To', '')),
                'date': msg.get('Date', ''),
                'size': len(raw_email),
                'raw': raw_email,  # Store raw bytes for later parsing
            }
            
            return email_data
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error parsing email {email_id}: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """
        Decode email header (handles encoding)
        
        Args:
            header: Email header string
        
        Returns:
            Decoded header string
        """
        if not header:
            return ""
        
        decoded_parts = decode_header(header)
        decoded_str = ""
        
        for content, encoding in decoded_parts:
            if isinstance(content, bytes):
                try:
                    decoded_str += content.decode(encoding or 'utf-8', errors='replace')
                except Exception:
                    decoded_str += content.decode('utf-8', errors='replace')
            else:
                decoded_str += str(content)
        
        return decoded_str.strip()
    
    def mark_as_read(self, email_ids: List[str], folder: str = "INBOX"):
        """
        Mark emails as read
        
        Args:
            email_ids: List of email UIDs to mark as read
            folder: Folder containing the emails
        """
        if not self.imap:
            self.connect()
        
        # Select the correct folder
        try:
            self.imap.select(folder)
        except Exception:
            # Fallback to INBOX if selection fails
            logger.warning(f"[{self.agent_name}] Failed to select folder {folder}, falling back to INBOX")
            self.imap.select('INBOX')
        
        for email_id in email_ids:
            try:
                # Use UID STORE
                self.imap.uid('store', email_id.encode(), '+FLAGS', '\\Seen')
                logger.debug(f"[{self.agent_name}] Marked email {email_id} as read in {folder}")
            except Exception as e:
                logger.error(f"[{self.agent_name}] Failed to mark email {email_id} as read: {e}")
                raise  # Re-raise to propagate the error
    
    
    def move_to_trash(self, email_id: str, folder: str = "INBOX"):
        """
        Move email to trash (Gmail's Trash folder)
        
        Args:
            email_id: Email UID to move to trash
            folder: Folder containing the email
        """
        if not self.imap:
            self.connect()
        
        try:
            self.imap.select(folder)
        except Exception:
            logger.warning(f"[{self.agent_name}] Failed to select folder {folder}, falling back to INBOX")
            self.imap.select('INBOX')
        
        try:
            # In Gmail IMAP, moving to trash requires adding the [Gmail]/Trash label
            # Using Gmail's X-GM-LABELS extension with UID STORE
            self.imap.uid('store', email_id.encode(), '+X-GM-LABELS', '\\Trash')
            
            # Also mark as Deleted to ensure it's removed from Inbox view
            self.imap.uid('store', email_id.encode(), '+FLAGS', '\\Deleted')
            
            # Mark as read when moving to trash
            self.imap.uid('store', email_id.encode(), '+FLAGS', '\\Seen')
            
            # Force expunge to update UI immediately
            self.imap.expunge()
            
            logger.info(f"[{self.agent_name}] Moved email {email_id} to trash from {folder}")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to move email {email_id} to trash: {e}")
            raise  # Re-raise to propagate the error
    
    def add_label(self, email_id: str, label_name: str):
        """
        Add a label to an email
        
        Args:
            email_id: Email UID
            label_name: Name of the label to add
        """
        try:
            self._ensure_connection()
            
            # Quote label name if it contains spaces
            quoted_label = f'"{label_name}"' if ' ' in label_name else label_name
            
            try:
                # Try to add label directly
                self.imap.uid('store', email_id.encode(), '+X-GM-LABELS', quoted_label)
                logger.info(f"[{self.agent_name}] Added label '{label_name}' to email {email_id}")
            except Exception:
                # If failed, it might be because the label doesn't exist
                logger.info(f"[{self.agent_name}] Failed to add label '{label_name}', trying to create it first")
                try:
                    self.imap.create(label_name)
                    # Retry adding label
                    self.imap.uid('store', email_id.encode(), '+X-GM-LABELS', quoted_label)
                    logger.info(f"[{self.agent_name}] Created label and added '{label_name}' to email {email_id}")
                except Exception as e:
                    logger.error(f"[{self.agent_name}] Failed to create/add label '{label_name}': {e}")
                    raise
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to add label '{label_name}' to email {email_id}: {e}")
            raise
    
    def move_to_all_mail(self, email_id: str, folder: str = "INBOX"):
        """
        Move email to All Mail (archive - remove from inbox)
        
        Args:
            email_id: Email UID to archive
            folder: Folder containing the email
        """
        if not self.imap:
            self.connect()
        
        try:
            self.imap.select(folder)
        except Exception:
            logger.warning(f"[{self.agent_name}] Failed to select folder {folder}, falling back to INBOX")
            self.imap.select('INBOX')
        
        try:
            # Robust Archiving: Copy to All Mail then Delete from current
            # This works even if X-GM-LABELS \Inbox is not visible/reported
            
            # 1. Copy to All Mail (Quote specifically for spaces) using UID COPY
            # Note: [Gmail]/All Mail is the standard folder name
            self.imap.uid('copy', email_id.encode(), '"[Gmail]/All Mail"')
            
            # 2. Mark as read using UID STORE
            self.imap.uid('store', email_id.encode(), '+FLAGS', '\\Seen')
            
            # 3. Mark as Deleted (removes from Inbox) using UID STORE
            self.imap.uid('store', email_id.encode(), '+FLAGS', '\\Deleted')
            
            # 4. Force expunge to update UI immediately
            self.imap.expunge()
            
            logger.info(f"[{self.agent_name}] Archived email {email_id} (moved to All Mail from {folder})")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to archive email {email_id}: {e}")
            raise  # Re-raise to propagate the error
    
    def delete_email(self, email_id: str):
        """
        Delete an email (move to trash)
        
        DEPRECATED: Use move_to_trash() instead for clarity
        
        Args:
            email_id: Email ID to delete
        """
        logger.warning(f"[{self.agent_name}] delete_email() is deprecated, use move_to_trash()")
        self.move_to_trash(email_id)
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


if __name__ == "__main__":
    # Test Gmail client
    import sys
    from pathlib import Path
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python gmail_client.py <email_address>")
        print("  Requires: config/secrets/google_calendar_credentials.json")
        sys.exit(1)
    
    email_addr = sys.argv[1]
    project_root = Path(__file__).parent.parent.parent
    token_path = project_root / 'data' / 'test' / 'oauth_tokens.json'
    creds_path = project_root / 'config' / 'secrets' / 'google_calendar_credentials.json'
    
    try:
        client = GmailClient(email_addr, token_path, creds_path, "test")
        
        print("\n[Test] Authenticating...")
        client.authenticate()
        print("✓ Authentication successful")
        
        print("\n[Test] Connecting to IMAP...")
        client.connect()
        print("✓ Connected")
        
        print("\n[Test] Fetching last 5 emails...")
        emails = client.fetch_emails(limit=5)
        print(f"✓ Fetched {len(emails)} emails")
        
        for i, email_data in enumerate(emails, 1):
            print(f"\n  Email {i}:")
            print(f"    Subject: {email_data['subject']}")
            print(f"    From: {email_data['from']}")
            print(f"    Date: {email_data['date']}")
        
        client.disconnect()
        print("\n✓ All tests passed!")
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
