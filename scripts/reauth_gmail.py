#!/usr/bin/env python3
"""
Re-authenticate Gmail and generate new tokens.
Run this locally or on a machine where you can open a browser.
"""

import os
import sys
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Define scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://mail.google.com/'
]

def reauthenticate(email_address, credentials_path, output_path):
    print(f"Re-authenticating for {email_address}...")
    
    if not Path(credentials_path).exists():
        print(f"Error: Credentials file not found at {credentials_path}")
        return

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path,
            SCOPES
        )
        
        # Use out-of-band flow for headless/remote support
        flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        
        # Force consent to ensure we get a refresh token
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        print("\n" + "="*70)
        print("AUTHORIZATION REQUIRED")
        print("="*70)
        print("\nPlease visit this URL to authorize this application:")
        print(f"\n{auth_url}\n")
        print("After authorizing, you will receive an authorization code.")
        print("="*70 + "\n")
        
        auth_code = input("Enter the authorization code: ").strip()
        
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        
        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(creds.to_json())
            
        print(f"\n✓ Success! Tokens saved to {output_path}")
        print("\nNow copy this file to your remote machine:")
        print(f"scp {output_path} <user>@<ip-address>:/path/to/mae/data/test_agent/oauth_tokens.json")
        
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/reauth_gmail.py <email_address> [credentials_path] [output_path]")
        print("Defaults:")
        print("  credentials_path: config/secrets/gmail_credentials.json")
        print("  output_path: data/test_agent/oauth_tokens.json")
        sys.exit(1)
        
    email = sys.argv[1]
    
    # Default paths
    base_dir = Path(__file__).parent.parent
    creds_path = sys.argv[2] if len(sys.argv) > 2 else str(base_dir / 'config/secrets/gmail_credentials.json')
    out_path = sys.argv[3] if len(sys.argv) > 3 else str(base_dir / 'data/test_agent/oauth_tokens.json')
    
    reauthenticate(email, creds_path, out_path)
