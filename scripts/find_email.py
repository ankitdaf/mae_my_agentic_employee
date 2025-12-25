import imaplib
import email
from pathlib import Path
import sys
import argparse
from datetime import datetime

# Add src to path
sys.path.append('.')
from src.core import load_config
from src.orchestrator import TokenManager, TokenType
from src.agents.email import GmailClient

from email.header import decode_header

def decode_mime_header(header):
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
    return decoded_str

def run_search(args):
    config = load_config("config/agents/personal.yaml")
    token_manager = TokenManager()

    # Construct search query
    search_criteria = []
    if args.sender:
        search_criteria.append(f'FROM "{args.sender}"')
    if args.subject:
        search_criteria.append(f'SUBJECT "{args.subject}"')
    if args.from_date:
        try:
            d = datetime.strptime(args.from_date, "%Y-%m-%d").strftime("%d-%b-%Y")
            search_criteria.append(f'SINCE {d}')
        except ValueError:
            print(f"Error: Invalid from-date format. Use YYYY-MM-DD.")
            return
    if args.to_date:
        try:
            d = datetime.strptime(args.to_date, "%Y-%m-%d").strftime("%d-%b-%Y")
            search_criteria.append(f'BEFORE {d}')
        except ValueError:
            print(f"Error: Invalid to-date format. Use YYYY-MM-DD.")
            return

    search_query = f"({' '.join(search_criteria)})" if search_criteria else "ALL"
    
    print(f"Searching for emails with query: {search_query}")
    if args.folder:
        print(f"Target folder: {args.folder}")
    else:
        print("Searching across all folders...")

    # Use the proper TokenType enum
    with token_manager.token(TokenType.IMAP, "personal"):
        client = GmailClient(
            email_address=config.get('email', 'address'),
            token_path=config.oauth_token_path,
            credentials_path=Path(config.get('email', 'credentials_path', 'config/secrets/gmail_credentials.json')),
            agent_name="debug"
        )
        
        with client as c:
            if args.folder:
                folders = [args.folder]
            else:
                folders = c.list_folders()
                
            for folder in folders:
                try:
                    quoted_folder = f'"{folder}"' if ' ' in folder else folder
                    # Use readonly=True to avoid changing the state of the emails
                    status, _ = c.imap.select(quoted_folder, readonly=True)
                    if status != 'OK':
                        continue
                    
                    status, email_ids = c.imap.uid('search', None, search_query)
                    if status != 'OK':
                        continue
                        
                    ids = email_ids[0].split()
                    if not ids:
                        continue
                        
                    print(f"\nFolder: {folder} ({len(ids)} matches)")
                    
                    # Limit output if needed
                    for eid in ids[-args.limit:]:
                        status, data = c.imap.uid('fetch', eid, '(BODY.PEEK[HEADER] FLAGS)')
                        if status != 'OK' or not data or not data[0]:
                            continue
                            
                        msg = email.message_from_bytes(data[0][1])
                        # Extract flags more robustly
                        flags = ""
                        for part in data:
                            if isinstance(part, tuple) and b'FLAGS' in part[0]:
                                # Extract flags from the response string, e.g., (FLAGS (\Seen \Recent))
                                s = part[0].decode()
                                if 'FLAGS (' in s:
                                    flags = s.split('FLAGS (')[1].split(')')[0]
                                break
                        
                        subject = decode_mime_header(msg['Subject'])
                        sender = decode_mime_header(msg['From'])
                        print(f"  [MATCH]")
                        print(f"    UID: {eid.decode()}")
                        print(f"    Subject: {subject}")
                        print(f"    From: {sender}")
                        print(f"    Date: {msg['Date']}")
                        print(f"    Flags: {flags}")

                        if args.body:
                            # Fetch body if requested
                            status, body_data = c.imap.uid('fetch', eid, '(BODY[TEXT])')
                            if status == 'OK' and body_data[0]:
                                body = body_data[0][1].decode(errors='replace')
                                preview = body[:200].replace('\r', '').replace('\n', ' ')
                                print(f"    Body Preview: {preview}...")
                except Exception as e:
                    print(f"Error searching folder {folder}: {e}")
                    continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find emails for debugging")
    parser.add_argument("--subject", help="Search by subject")
    parser.add_argument("--sender", help="Search by sender (FROM)")
    parser.add_argument("--from-date", help="Search since date (YYYY-MM-DD)")
    parser.add_argument("--to-date", help="Search before date (YYYY-MM-DD)")
    parser.add_argument("--folder", help="Specific folder to search in (default: all)")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results per folder (default: 10)")
    parser.add_argument("--body", action="store_true", help="Show a preview of the email body")
    
    args = parser.parse_args()
    
    run_search(args)
    print("\nSearch complete.")