"""
Email Parser for MAE

Parses raw email data into structured format.
Extracts body text and metadata.
"""

import email
import re
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import hashlib
import base64
from src.utils.datetime_utils import ensure_aware

logger = logging.getLogger(__name__)


class EmailParser:
    """Parse and extract information from raw emails"""
    
    def __init__(self, agent_name: str = "unknown"):
        """
        Initialize email parser
        
        Args:
            agent_name: Agent name for logging
        """
        self.agent_name = agent_name
        self.parser = BytesParser(policy=policy.default)
    
    def parse(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw email data into structured format
        
        Args:
            email_data: Raw email data from Gmail client
        
        Returns:
            Parsed email dictionary with additional fields
        """
        try:
            # Parse raw email
            msg = self.parser.parsebytes(email_data['raw'])
            
            # Extract parsed data
            parsed = {
                # Keep original metadata
                'id': email_data['id'],
                'message_id': email_data['message_id'],
                'subject': email_data['subject'],
                'from': email_data['from'],
                'from_email': self._extract_email_address(email_data['from']),
                'from_name': self._extract_name(email_data['from']),
                'to': email_data['to'],
                'date': email_data['date'],
                'size': email_data['size'],
                
            # Add parsed fields
                'date_parsed': self._parse_date(email_data['date']),
                'body_text': self._extract_text_body(msg),
                'body_html': self._extract_html_body(msg),
                
                # Metadata for processing
                'age_days': None,
                'hash': self._compute_hash(email_data['message_id']),
            }
            
            # Fallback: If body_text is empty, try to convert HTML to text
            if not parsed['body_text'] and parsed['body_html']:
                logger.info(f"[{self.agent_name}] No text/plain found, converting HTML to text for email {email_data['id']}")
                parsed['body_text'] = self.html_to_text(parsed['body_html'])
            
            # Debug logging for empty fields (using repr to see whitespace)
            if not parsed['from_email'] or not parsed['from_email'].strip():
                logger.warning(f"[{self.agent_name}] Empty from_email extracted from: {repr(email_data['from'])}")
                # Log raw From header from message object
                raw_from = msg.get('From', 'N/A')
                logger.warning(f"[{self.agent_name}] Raw From header in msg: {repr(raw_from)}")
                # Log start of raw email to check headers
                try:
                    raw_snippet = email_data['raw'][:200]
                    logger.warning(f"[{self.agent_name}] Raw email snippet: {repr(raw_snippet)}")
                except Exception:
                    pass

            if not parsed['body_text'] or not parsed['body_text'].strip():
                logger.warning(f"[{self.agent_name}] Empty body_text extracted for email {email_data['id']}")
                logger.debug(f"[{self.agent_name}] Raw email structure: {msg.get_content_type()}")
                if msg.is_multipart():
                    for part in msg.walk():
                        logger.debug(f"[{self.agent_name}]   Part: {part.get_content_type()}")
            

            
            # Calculate email age
            if parsed['date_parsed']:
                now_aware = ensure_aware(datetime.now())
                age = now_aware - parsed['date_parsed']
                parsed['age_days'] = age.days
            
            return parsed
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to parse email {email_data.get('id')}: {e}")
            # Return minimal parsed data
            return {
                **email_data,
                'body_text': '',
                'body_html': '',
                'parse_error': str(e)
            }
    
    def _extract_text_body(self, msg) -> str:
        """
        Extract plain text body from email
        
        Args:
            msg: Email message object
        
        Returns:
            Plain text body
        """
        try:
            # Try to get plain text part
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        return payload.decode(charset, errors='replace').strip()
            else:
                if msg.get_content_type() == 'text/plain':
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace').strip()
            
            return ""
        
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to extract text body: {e}")
            return ""
    
    def _extract_html_body(self, msg) -> str:
        """
        Extract HTML body from email
        
        Args:
            msg: Email message object
        
        Returns:
            HTML body
        """
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        return payload.decode(charset, errors='replace').strip()
            else:
                if msg.get_content_type() == 'text/html':
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace').strip()
            
            return ""
        
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to extract HTML body: {e}")
            return ""
    

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse email date string to datetime
        
        Args:
            date_str: Email date string
        
        Returns:
            Datetime object or None
        """
        try:
            dt = parsedate_to_datetime(date_str)
            return ensure_aware(dt)
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to parse date '{date_str}': {e}")
            return None
    
    def _extract_email_address(self, from_str: str) -> str:
        """
        Extract email address from 'From' header
        
        Examples:
            "John Doe <john@example.com>" -> "john@example.com"
            "john@example.com" -> "john@example.com"
        
        Args:
            from_str: From header string
        
        Returns:
            Email address
        """
        try:
            # Try to extract email from angle brackets
            match = re.search(r'<([^>]+)>', from_str)
            if match:
                return match.group(1).strip().lower()
            
            # If no brackets, assume entire string is email
            # Remove any quotes
            email_addr = from_str.strip().replace('"', '').replace("'", '')
            
            # Validate it looks like an email
            if '@' in email_addr:
                return email_addr.lower()
            
            return from_str.lower()
        
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to extract email from '{from_str}': {e}")
            return from_str.lower()
    
    def _extract_name(self, from_str: str) -> str:
        """
        Extract sender name from 'From' header
        
        Examples:
            "John Doe <john@example.com>" -> "John Doe"
            "john@example.com" -> "john@example.com"
        
        Args:
            from_str: From header string
        
        Returns:
            Sender name
        """
        try:
            # Try to extract name before angle brackets
            match = re.match(r'(.+?)\s*<', from_str)
            if match:
                name = match.group(1).strip()
                # Remove quotes
                name = name.replace('"', '').replace("'", '')
                return name
            
            # No name found, return email address
            return self._extract_email_address(from_str)
        
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to extract name from '{from_str}': {e}")
            return from_str
    
    def _compute_hash(self, message_id: str) -> str:
        """
        Compute hash of message ID for deduplication
        
        Args:
            message_id: Email message ID
        
        Returns:
            MD5 hash
        """
        return hashlib.md5(message_id.encode()).hexdigest()
    
    def html_to_text(self, html: str) -> str:
        """
        Convert HTML to plain text (simple version)
        
        Args:
            html: HTML content
        
        Returns:
            Plain text
        """
        if not html:
            return ""
        
        try:
            # Remove script and style tags
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            
            # Replace br and p tags with newlines
            text = re.sub(r'<br\s*/?>',  '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
            
            # Remove all other HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            
            # Decode HTML entities
            import html as html_lib
            text = html_lib.unescape(text)
            
            # Clean up whitespace
            lines = [line.strip() for line in text.split('\n')]
            text = '\n'.join(line for line in lines if line)
            
            return text.strip()
        
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Failed to convert HTML to text: {e}")
            return html
    
    def get_email_domain(self, email_address: str) -> str:
        """
        Extract domain from email address
        
        Args:
            email_address: Email address
        
        Returns:
            Domain (e.g., "example.com")
        """
        try:
            if '@' in email_address:
                return email_address.split('@')[1].lower()
            return email_address.lower()
        except Exception:
            return email_address.lower()


if __name__ == "__main__":
    # Test email parser
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Test data
    test_email_raw = b'''From: John Doe <john.doe@example.com>
To: recipient@test.com
Subject: Test Email
Date: Mon, 20 Nov 2023 10:00:00 +0000
Message-ID: <test123@example.com>

This is a test email body.
It has multiple lines.
'''
    
    test_email_data = {
        'id': '12345',
        'message_id': '<test123@example.com>',
        'subject': 'Test Email',
        'from': 'John Doe <john.doe@example.com>',
        'to': 'recipient@test.com',
        'date': 'Mon, 20 Nov 2023 10:00:00 +0000',
        'size': len(test_email_raw),
        'raw': test_email_raw
    }
    
    parser = EmailParser("test")
    
    print("\n[Test] Parsing email...")
    parsed = parser.parse(test_email_data)
    
    print("\n✓ Email parsed successfully:")
    print(f"  Subject: {parsed['subject']}")
    print(f"  From Name: {parsed['from_name']}")
    print(f"  From Email: {parsed['from_email']}")
    print(f"  Domain: {parser.get_email_domain(parsed['from_email'])}")
    print(f"  Date: {parsed['date_parsed']}")
    print(f"  Age (days): {parsed['age_days']}")
    print(f"  Body: {parsed['body_text'][:100]}...")
    print(f"  Hash: {parsed['hash']}")
    
    print("\n✓ All tests passed!")
