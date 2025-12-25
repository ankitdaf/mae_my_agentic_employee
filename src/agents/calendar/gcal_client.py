"""
Google Calendar Client for MAE

Manages Google Calendar API integration for creating events.
Uses OAuth 2.0 authentication.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class GCalAuthError(Exception):
    """Raised when Google Calendar authentication fails"""
    pass


class GCalAPIError(Exception):
    """Raised when Google Calendar API call fails"""
    pass


class GCalClient:
    """Google Calendar API client"""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
    
    def __init__(self, credentials_path: Path, token_path: Path,
                 agent_name: str = "unknown"):
        """
        Initialize Google Calendar client
        
        Args:
            credentials_path: Path to OAuth client credentials JSON
            token_path: Path to store user tokens
            agent_name: Agent name for logging
        """
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.agent_name = agent_name
        self.credentials = None
        self.service = None
        
        logger.info(f"[{agent_name}] Google Calendar client initialized")
    
    def authenticate(self):
        """
        Authenticate with Google Calendar using OAuth 2.0
        
        Raises:
            GCalAuthError: If authentication fails
        """
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            creds = None
            
            # Load existing tokens
            if self.token_path.exists():
                try:
                    logger.info(f"[{self.agent_name}] Loading existing Calendar tokens...")
                    with open(self.token_path, 'r') as token_file:
                        token_data = json.load(token_file)
                        creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                except Exception as e:
                    logger.warning(f"[{self.agent_name}] Failed to load tokens: {e}")
                    creds = None
            
            # Refresh or obtain new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info(f"[{self.agent_name}] Refreshing Calendar tokens...")
                    creds.refresh(Request())
                else:
                    logger.info(f"[{self.agent_name}] Starting OAuth flow...")
                    if not self.credentials_path.exists():
                        raise GCalAuthError(
                            f"Credentials file not found: {self.credentials_path}"
                        )
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path),
                        self.SCOPES
                    )
                    
                    # Manual OAuth flow for headless servers
                    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    
                    print("\n" + "="*70)
                    print("GOOGLE CALENDAR OAUTH AUTHORIZATION REQUIRED")
                    print("="*70)
                    print("\nPlease visit this URL to authorize Calendar access:")
                    print(f"\n{auth_url}\n")
                    print("After authorizing, you will receive an authorization code.")
                    print("="*70 + "\n")
                    
                    auth_code = input("Enter the authorization code: ").strip()
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                
                # Save tokens
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, 'w') as token_file:
                    token_file.write(creds.to_json())
                
                # Set restrictive permissions
                self.token_path.chmod(0o600)
                logger.info(f"[{self.agent_name}] Calendar tokens saved")
            
            self.credentials = creds
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info(f"[{self.agent_name}] Calendar API authenticated")
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Calendar authentication failed: {e}")
            raise GCalAuthError(f"Authentication failed: {e}")
    
    def create_event(self, event_data: Dict[str, Any],
                     calendar_id: str = 'primary') -> Optional[str]:
        """
        Create calendar event
        
        Args:
            event_data: Event data with title, start_time, end_time, etc.
            calendar_id: Calendar ID (default: 'primary')
        
        Returns:
            Event ID if created, None otherwise
        
        Raises:
            GCalAPIError: If event creation fails
        """
        if not self.service:
            raise GCalAPIError("Not authenticated. Call authenticate() first.")
        
        try:
            # Build event body
            event = {
                'summary': event_data.get('title', 'Untitled Event'),
                'description': event_data.get('description', ''),
                'start': {
                    'dateTime': event_data['start_time'].isoformat(),
                    'timeZone': 'UTC',  # TODO: Make configurable
                },
                'end': {
                    'dateTime': event_data['end_time'].isoformat(),
                    'timeZone': 'UTC',
                }
            }
            
            # Add location if provided
            if event_data.get('location'):
                event['location'] = event_data['location']
            
            # Create event
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            event_id = created_event['id']
            logger.info(
                f"[{self.agent_name}] Created calendar event: {event_data.get('title')} "
                f"(ID: {event_id})"
            )
            
            return event_id
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to create event: {e}")
            raise GCalAPIError(f"Event creation failed: {e}")
    
    def event_exists(self, event_data: Dict[str, Any],
                     calendar_id: str = 'primary') -> bool:
        """
        Check if similar event already exists (deduplication)
        
        Args:
            event_data: Event data to check
            calendar_id: Calendar ID
        
        Returns:
            True if similar event exists
        """
        if not self.service:
            return False
        
        try:
            # Search for events around the same time
            start_time = event_data['start_time']
            end_time = event_data['end_time']
            
            # Query events in a window around the event
            time_min = (start_time).isoformat() + 'Z'
            time_max = (end_time).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Check for similar events (same title or almost same time)
            title = event_data.get('title', '').lower()
            for event in events:
                existing_title = event.get('summary', '').lower()
                if title in existing_title or existing_title in title:
                    logger.info(
                        f"[{self.agent_name}] Similar event already exists: {existing_title}"
                    )
                    return True
            
            return False
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to check for existing events: {e}")
            return False  # Assume doesn't exist on error
    
    def __enter__(self):
        """Context manager entry"""
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # Nothing to cleanup for Calendar API
        pass


if __name__ == "__main__":
    # Manual test (requires OAuth credentials)
    import sys
    from datetime import timedelta
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*50)
    print("Google Calendar Client - Manual Test")
    print("="*50)
    print("\nNOTE: This test requires OAuth credentials.")
    print("Please ensure you have:")
    print("1. Created OAuth credentials (see docs/google_calendar_setup.md)")
    print("2. Placed credentials in config/secrets/google_calendar_credentials.json")
    print("\nThis test will open a browser for authorization.\n")
    
    credentials_path = Path("config/secrets/google_calendar_credentials.json")
    token_path = Path("data/test/calendar_tokens.json")
    
    if not credentials_path.exists():
        print(f"❌ Credentials not found at: {credentials_path}")
        print("Please follow docs/google_calendar_setup.md to obtain credentials.")
        sys.exit(1)
    
    try:
        # Create client
        client = GCalClient(credentials_path, token_path, "test")
        
        # Test event
        test_event = {
            'title': 'MAE Test Event',
            'description': 'This is a test event created by MAE',
            'start_time': datetime.now() + timedelta(days=1),
            'end_time': datetime.now() + timedelta(days=1, hours=1),
            'location': 'Test Location'
        }
        
        print("[Test] Authenticating...")
        with client:
            print("✓ Authentication successful\n")
            
            print("[Test] Checking for existing event...")
            exists = client.event_exists(test_event)
            print(f"  Event exists: {exists}\n")
            
            if not exists:
                print("[Test] Creating event...")
                event_id = client.create_event(test_event)
                print(f"✓ Event created with ID: {event_id}\n")
            else:
                print("  Skipping creation (event already exists)\n")
        
        print("✓ All tests passed!")
        print("\nNOTE: Check your Google Calendar to verify the event was created.")
    
    except GCalAuthError as e:
        print(f"❌ Authentication error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
