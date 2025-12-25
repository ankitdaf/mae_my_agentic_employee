
import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.getcwd())

from src.agents.email.gmail_client import GmailClient
from src.core.config_loader import ConfigLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_uid_client():
    try:
        # Default to personal.yaml if not specified
        config_path = "config/agents/personal.yaml"
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
            
        print(f"Loading config from {config_path}...")
        config = ConfigLoader(config_path)
        
        email_address = config.get('email', 'address')
        token_path = config.oauth_token_path
        
        # Try to find credentials in standard locations
        creds_path = Path('config/secrets/gmail_credentials.json')
        if not creds_path.exists():
             creds_path = Path('config/secrets/google_calendar_credentials.json')
             
        print(f"Initializing GmailClient for {email_address}...")
        client = GmailClient(email_address, token_path, creds_path, "test_verifier")
        client.connect()
        print("✓ Connected.")
        
        print("\nFetching headers (limit=5)...")
        headers = client.fetch_headers(limit=5)
        print(f"✓ Fetched {len(headers)} headers.")
        
        if not headers:
            print("No emails found to test.")
            return

        for h in headers:
            print(f"  ID: {h['id']} | Subject: {h['subject'][:30]}...")
            
        # Test fetching full email by ID (which is now UID)
        test_id = headers[0]['id']
        print(f"\nFetching full email for ID: {test_id}...")
        full_email = client.fetch_full_email(test_id)
        
        if full_email:
            print(f"✓ Successfully fetched full email.")
            print(f"  Subject: {full_email['subject']}")
            print(f"  Size: {full_email['size']}")
        else:
            print(f"✗ Failed to fetch full email.")
            
        client.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_uid_client()
