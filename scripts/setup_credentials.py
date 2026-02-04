#!/usr/bin/env python3
"""
Secure Credential Setup for MAE
Allows storing app passwords in the system keyring or encrypted fallback.
"""

import sys
import logging
from pathlib import Path
import argparse
import getpass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.utils.credential_manager import CredentialManager

def main():
    parser = argparse.ArgumentParser(description="Securely store service credentials for MAE agents")
    parser.add_argument("--agent", required=True, help="Agent name (e.g., personal)")
    parser.add_argument("--service", default="gmail", help="Service type (default: gmail)")
    parser.add_argument("--email", help="Email address (for Gmail/IMAP)")
    parser.add_argument("--delete", action="store_true", help="Delete stored credentials")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    if args.delete:
        print(f"Deleting credentials for {args.agent}:{args.service}...")
        CredentialManager.delete_credential(args.agent, args.service)
        print("✓ Done")
        return

    print(f"\nSetting up secure credentials for agent '{args.agent}', service '{args.service}'")
    print("-" * 60)

    try:
        email = args.email
        if not email and args.service == "gmail":
            email = input("Enter Gmail address: ").strip()
            if not email:
                print("Error: Email address is required for Gmail service")
                sys.exit(1)
        
        password = getpass.getpass("Enter App Password: ").strip()
        if not password:
            print("Error: Password cannot be empty")
            sys.exit(1)
            
        # Validate password format for Gmail
        if args.service == "gmail":
            try:
                password = CredentialManager.validate_password(password)
            except ValueError as e:
                print(f"Warning: {e}")
                confirm = input("Store anyway? (y/n): ").lower()
                if confirm != 'y':
                    sys.exit(1)
        
        credential_data = {
            "password": password
        }
        if email:
            credential_data["email"] = email
            
        CredentialManager.store_credential(args.agent, args.service, credential_data)
        
        print("\n✓ Success! Credentials stored securely.")
        print("You can now remove 'app_password' from your YAML configuration file.")
        
    except KeyboardInterrupt:
        print("\nAborted.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
