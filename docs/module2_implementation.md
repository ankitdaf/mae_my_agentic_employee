# Module 2: Gmail Client and Email Parsing - Implementation Notes

## Overview
Module 2 implements email fetching, parsing, and storage capabilities for Gmail accounts using OAuth 2.0 authentication.

## Components Implemented

### 1. Gmail Client (`src/agents/email/gmail_client.py`)

**Purpose**: Handle Gmail authentication and IMAP operations

**Key Features**:
- OAuth 2.0 authentication with token refresh
- IMAP4_SSL connection to Gmail
- Email fetching with filters (unread, date range, limit)
- Email operations (mark as read, delete)
- Context manager support for automatic connection cleanup

**Design Choices**:
- **OAuth 2.0**: Required by Gmail (app passwords being deprecated)
- **Local token storage**: Per-agent tokens in `data/{agent}/oauth_tokens.json`
- **XOAUTH2 for IMAP**: Modern authentication method
- **Browser-based auth flow**: Uses `run_local_server` for initial authorization
- **Automatic token refresh**: Handles expired tokens transparently

**Authentication Flow**:
1. Check if token exists (`oauth_tokens.json`)
2. If exists and valid, use it
3. If expired, refresh using refresh token
4. If no token or refresh fails, start OAuth flow:
   - Opens browser for user authorization
   - Runs local server on port 8080 for callback
   - Saves tokens with restrictive permissions (chmod 600)

**Usage**:
```python
from src.agents.email import GmailClient

client = GmailClient(
    email_address="user@gmail.com",
    token_path=Path("data/personal/oauth_tokens.json"),
    credentials_path=Path("config/secrets/google_calendar_credentials.json"),
    agent_name="personal"
)

# Context manager (recommended)
with client:
    emails = client.fetch_emails(limit=10, unread_only=True)
    for email in emails:
        print(email['subject'])
```

**Validation**: Requires OAuth credentials to fully test. Structure validated.

---

### 2. Email Parser (`src/agents/email/email_parser.py`)

**Purpose**: Parse raw email data into structured format

**Key Features**:
- Extract plain text and HTML bodies
- Parse attachments with metadata
- Extract sender email and name
- Calculate email age in days
- HTML to text conversion
- Email deduplication (MD5 hash of message ID)

**Design Choices**:
- **BytesParser with policy.default**: Modern email parsing (Python 3.6+)
- **Graceful degradation**: Returns partial data on parse errors
- **Age calculation**: Timezone-aware datetime comparison
- **No attachment data in metadata**: Only metadata (filename, size, hash) stored
- **Domain extraction**: For sender/domain filtering

**Extracted Fields**:
- Basic: id, subject, from, to, date
- Parsed: from_email, from_name, date_parsed, age_days
- Content: body_text, body_html
- Attachments: count, metadata array
- Metadata: hash (for deduplication)

**HTML Processing**:
- Simple regex-based cleaning (removes scripts, styles)
- Converts `<br>` and `<p>` to newlines
- HTML entity decoding
- More advanced parsing can be added later with BeautifulSoup if needed

**Usage**:
```python
from src.agents.email import EmailParser

parser = EmailParser("personal")
raw_email = gmail_client._fetch_email_by_id(email_id)
parsed = parser.parse(raw_email)

print(f"From: {parsed['from_name']} <{parsed['from_email']}>")
print(f"Age: {parsed['age_days']} days")
print(f"Body: {parsed['body_text'][:200]}")
```

**Validation**: ✓ Tested with sample email data

```
Subject: Test Email
From Name: John Doe
From Email: john.doe@example.com  
Domain: example.com
Age (days): 731
Attachments: 0
```

---

### 3. Email Storage (`src/agents/email/email_storage.py`)

**Purpose**: File-based cache for email metadata and processing state

**Key Features**:
- JSON-based metadata storage
- Processing state tracking (new → classified → actioned)
- Email index for fast lookups
- Statistics and reporting
- Deduplication support

**Design Choices**:
- **File per email**: `data/{agent}/emails/metadata/{hash}.json`
- **Separate index**: Fast lookups without loading all emails
- **Exclude raw data**: Only metadata stored (not raw bytes)
- **State machine**: new → classified → actioned → deleted
- **Minimal index**: Only essential fields for quick filtering

**Directory Structure**:
```
data/personal/emails/
├── metadata/
│   ├── abc123.json
│   ├── def456.json
│   └── ...
├── email_index.json
└── processing_state.json
```

**Processing States**:
- `new`: Email fetched but not classified
- `classified`: AI classification complete
- `actioned`: Actions performed (deleted/saved/calendared)
- `deleted`: Email deleted from server

**Usage**:
```python
from src.agents.email import EmailStorage

storage = EmailStorage(
    cache_dir=Path("data/personal/emails"),
    agent_name="personal"
)

# Save email
storage.save_email(parsed_email, "new")

# Update classification
storage.update_classification(email_hash, {
    'category': 'promotional',
    'confidence': 0.95
})

# Get stats
stats = storage.get_stats()
print(f"Total: {stats['total_emails']}")
print(f"By state: {stats['by_state']}")
```

**Validation**: ✓ All tests passed

```
Stats: {
  'total_emails': 1,
  'by_state': {'classified': 1},
  'total_size': 1024,
  'with_attachments': 0
}
```

---

## Integration Example

Putting it all together:

```python
from src.core import load_config
from src.agents.email import GmailClient, EmailParser, EmailStorage
from pathlib import Path

# Load config
config = load_config("config/agents/personal.yaml")

# Initialize components
client = GmailClient(
    email_address=config.get('email', 'address'),
    token_path=config.oauth_token_path,
    credentials_path=Path("config/secrets/google_calendar_credentials.json"),
    agent_name=config.get_agent_name()
)

parser = EmailParser(config.get_agent_name())
storage = EmailStorage(config.email_cache_dir, config.get_agent_name())

# Fetch and process emails
with client:
    # Fetch unread emails from last 7 days
    raw_emails = client.fetch_emails(
        unread_only=True,
        since_days=7,
        limit=50
    )
    
    for raw_email in raw_emails:
        # Parse email
        parsed = parser.parse(raw_email)
        
        # Check if already processed
        if storage.email_exists(parsed['hash']):
            continue
        
        # Save to cache
        storage.save_email(parsed, "new")
        
        print(f"New email: {parsed['subject']}")
```

---

## OAuth 2.0 Setup Required

Before using Gmail client, users need to:

1. Follow `docs/google_calendar_setup.md` to get OAuth credentials
2. Place `gmail_credentials.json` in `config/secrets/`
3. Run agent for first time - browser will open for authorization
4. Tokens saved automatically to `data/{agent}/oauth_tokens.json`

---

## Security Enhancements

**Token Protection**:
- Tokens stored with chmod 600 (read/write for owner only)
- Gitignored via `.gitignore` rules
- Per-agent isolation

**Credentials Protection**:
- OAuth credentials in `config/secrets/` (gitignored)
- Never logged or displayed (except in error messages)

---

## Testing Results

### Email Parser
```bash
$ python3 src/agents/email/email_parser.py
✓ Email parsed successfully
✓ All tests passed!
```

### Email Storage
```bash
$ python3 src/agents/email/email_storage.py
✓ Email saved
✓ Email loaded
✓ State updated
✓ Stats generated
✓ All tests passed!
```

### Gmail Client
Requires actual OAuth credentials. Module structure validated, ready for integration testing with real Gmail account.

---

## Performance Considerations

**IMAP Optimization**:
- Fetch emails in batches (default: 100)
- Use date filters to limit results
- Unread-only flag reduces data transfer

**Storage Optimization**:
- Raw email bytes not stored (only metadata)
- Index file prevents loading all emails for lookups
- Attachment metadata stored, but file saving is a planned feature

**Memory Usage**:
- Estimated per email: ~5-10KB (metadata only)
- 1000 emails ≈ 5-10MB metadata

---

## Known Limitations

1. **Gmail Only**: Other providers (Outlook, IMAP) in future scope
2. **Simple HTML Parsing**: Uses regex, not full HTML parser
3. **No Attachment Saving Yet**: Metadata is parsed, but saving files is in future scope
4. **Manual OAuth**: Requires browser for first-time auth (no headless option yet)

---

## Next Steps

Module 2 is complete! Ready for Module 3 (AI Classification).

**Module 3 Goals**:
1. MobileBERT RKNN model integration
2. Email classification (Important/Promotional/Normal)
3. Topic-based filtering
4. Sender/domain whitelist/blacklist

---

## Files Created

- `src/agents/email/gmail_client.py` - OAuth 2.0 + IMAP client
- `src/agents/email/email_parser.py` - Email parsing utilities
- `src/agents/email/email_storage.py` - File-based email cache
- `src/agents/email/__init__.py` - Module exports
