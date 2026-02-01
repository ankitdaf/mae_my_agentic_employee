# MAE - My Agentic Employee (Email Processing)

An intelligent, lightweight email processing agent designed for the RK3566 single-board computer. MAE automatically fetches, classifies, and manages your emails using AI-powered classification and smart rules.

## Features

- **Gmail Integration**: Support for both **App Passwords** (recommended) and OAuth 2.0 authentication.
- **AI Classification**: Categorize emails as Transactions, Feed, Promotions, or Inbox (with NPU-accelerated MobileBERT support)
- **Smart Deletion**: Automatically manage promotional emails with configurable actions (Move to Trash or Apply Label)
- **Topic Matching**: Preserve promotional emails that match your specific interests
- **Sender Management**: Whitelist/blacklist with wildcard pattern support
- **Attachment Handling**: Save important attachments with deduplication
- **Calendar Integration**: Extract events from emails and add to Google Calendar
- **Web UI Dashboard**: Manage agents, update configurations, and securely store credentials via a web interface
- **Historical Processing**: Bulk process and label older emails based on AI classification
- **Resource Management**: File-based token system prevents resource contention on RK3566
- **Dry-Run Mode**: Test classification and actions before making any changes

## Architecture

MAE uses a **multi-process architecture** managed by an orchestrator, with a web-based management dashboard:

```
MAE System
├── Orchestrator (Main Loop)
│   ├── Email Agent (fetches, classifies, acts on emails)
│   ├── Calendar Agent (future)
│   └── OneDrive Agent (future)
└── Web UI Dashboard (FastAPI + Vanilla JS)
```

Resource tokens (NPU, IMAP, CALENDAR) prevent concurrent access to shared resources.

## Quick Start

### Prerequisites

1. **RK3566 Device** (or development machine for testing)
2. **Python 3.8+**
3. **Gmail Account** with an App Password or OAuth credentials (see **[App Password Guide](docs/gmail_app_password_setup.md)** for the easiest method)
4. **Google Calendar** (optional, for calendar integration)

### Installation

```bash
# Clone repository
git clone \u003cyour-repo-url\u003e
cd my-agentic-employee-mae

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs data config/secrets
```

### Configuration

1. **Setup Authentication**:
   - **Option 1 (Easiest)**: Follow the **[App Password Setup Guide](docs/gmail_app_password_setup.md)** to generate a password and enter it via the Web UI.
   - **Option 2 (Advanced)**: Follow the **[OAuth Setup Guide](docs/oauth_setup.md)** to create a Google Cloud project and get a `gmail_credentials.json` file.

2. **Create Agent Config**:
   ```bash
   cp config/agents/personal.yaml.example config/agents/personal.yaml
   ```

3. **Edit Configuration**:
   ```yaml
   # config/agents/personal.yaml
   agent_name: "personal"
   enabled: true
   
   email:
     address: "your.email@gmail.com"
     credentials_path: "config/secrets/google_calendar_credentials.json"
     fetch_limit: 100
     unread_only: true
     since_days: 7
   
   classification:
     topics_i_care_about:
       - "machine learning"
       - "family"
     whitelisted_senders:
       - "important@example.com"
       - "*@mycompany.com"
     blacklisted_senders:
       - "*@spam.com"
   
   deletion:
     action_on_deletion: "move_to_trash"  # Options: "move_to_trash" or "apply_label"
     delete_promotional: true
     dry_run: true  # IMPORTANT: Test first!
   
   attachments:
     enabled: true
     allowed_extensions: ["pdf", "docx", "xlsx"]
     max_size_mb: 10
   
   calendar:
     enabled: false  # Enable for calendar integration
     credentials_path: "config/secrets/google_calendar_credentials.json"
   ```

### First Run

```bash
# Run once (will open browser for OAuth)
python3 main.py --once

# Check logs
tail -f logs/mae.log
```

### Continuous Mode

```bash
# Run continuously (checks every hour by default)
# This also starts the Web UI on http://localhost:8000
python3 main.py
```

For production environments, it is recommended to run MAE as a **system service**. See **[Service Setup Guide](docs/service_setup.md)** for instructions on setting up a `systemd` service.

### Web UI Dashboard

Access the management dashboard at `http://<your-device-ip>:8000` to:
- Monitor agent status and logs
- Update agent configurations in real-time
- Initiate OAuth authentication flows
- View run statistics

### Testing with Dry-Run

```bash
# Enable deletion in config with dry_run: true
# Run once to see what would be deleted
python3 main.py --once

# Review logs to verify behavior
grep "DRY-RUN" logs/mae.log
```

## Usage

### Command Line Options

```bash
python3 main.py --help

Options:
  --config-dir PATH    Agent config directory (default: config/agents)
  --once               Run once and exit (default: continuous loop)
  --no-server          Disable the Web UI dashboard
  --start-date DATE    Start date for historical processing (YYYY-MM-DD)
  --end-date DATE      End date for historical processing (YYYY-MM-DD)
  --target-labels LBLS Comma-separated target categories for historical processing
```

### Historical Processing

You can process older emails in bulk using the historical processing mode:

```bash
python3 main.py --once --start-date 2024-01-01 --end-date 2024-12-01 --target-labels promotions
```

### Email Classification

Emails are classified into four categories:

| Category | Description | Actions |
|----------|-------------|---------|
| **Inbox** | Personal or work emails, direct communication | Keep in inbox, save attachments |
| **Transactions** | Bills, receipts, bank alerts, order updates | Mark as read, archive (All Mail), save attachments |
| **Feed** | Newsletters, blog updates, tutorials | Mark as read, archive (All Mail) |
| **Promotional** | Marketing, sales, unsolicited offers | Delete or label (unless matches topics or whitelisted) |

### Deletion Logic

**Only promotional emails are targeted for deletion**. Inbox, Transactions, and Feed emails are NEVER deleted.

Priority order for Promotional emails:
1. Whitelisted senders → **Keep**
2. Matches topics of interest → **Keep**
3. Blacklisted senders → **Delete/Label**
4. Other Promotional → **Delete/Label**

### Topic Matching

Promotional emails matching your topics are preserved:

```yaml
classification:
  topics_i_care_about:
    - "machine learning"
    - "kubernetes"
    - "python programming"
```

Example: A promotional email about "50% off ML course" would be kept because it matches "machine learning".

### Sender Management

**Whitelist** (never delete):
```yaml
whitelisted_senders:
  - "boss@company.com"       # Exact match
  - "*@company.com"          # All from domain
  - "*newsletter.com"        # Wildcard
```

**Blacklist** (always delete if old):
```yaml
blacklisted_senders:
  - "spam@marketing.com"
  - "*@spammers.com"
```

### Calendar Integration

MAE extracts calendar events from emails using regex patterns:

Supported formats:
- "Meeting on Monday, Dec 25 at 3:00 PM"
- "Tomorrow at 2:00 PM"
- "Next Monday at 10:00 AM"
- "December 25, 2024 at 3:00 PM"

Extracted events are automatically added to Google Calendar with deduplication.

## Project Structure

```
my-agentic-employee-mae/
├── main.py                    # Entry point
├── requirements.txt
├── config/
│   ├── agents/
│   │   ├── personal.yaml      # Your config
│   │   └── personal.yaml.example
│   └── secrets/              # OAuth credentials (gitignored)
├── src/
│   ├── core/                 # Config loading
│   ├── orchestrator/         # Scheduling & token management
│   └── agents/
│       ├── email/            # Gmail client, parser, storage
│       ├── classifier/       # AI classification, topics, senders
│       ├── actions/          # Deletion, attachment saving
│       ├── calendar/         # Event extraction, Google Calendar
│       └── email_agent.py    # Main email agent
├── data/                     # Agent data (gitignored)
│   ├── locks/               # Resource tokens
│   └── {agent}/
│       ├── oauth_tokens.json
│       └── emails/
├── logs/                     # Log files
└── docs/                     # Documentation
    ├── implementation_plan.md
    ├── google_calendar_setup.md
    ├── module1_implementation.md
    ├── module2_implementation.md
    └── module3_implementation.md
```

## Security

- **OAuth Tokens**: Stored with `chmod 600` in `data/{agent}/`
- **Gitignored Paths**: All secrets, tokens, and user data excluded
- **Local Processing**: All AI inference runs locally on NPU
- **No Cloud Dependencies**: Works completely offline (except OAuth & Gmail API)

## Performance

Optimized for RK3566 constraints:

- **Memory**: ~50-100MB per agent
- **NPU**: ~100-200ms per email classification
- **Storage**: ~5-10KB per email metadata
- **IMAP**: Batched fetching (default: 100 emails)

## Troubleshooting

### OAuth Issues

```bash
# Delete existing tokens and re-auth
rm data/*/oauth_tokens.json
python3 main.py --once
```

### Stale Locks

```bash
# Clean up stale locks
rm data/locks/*.lock
```

### Check Logs

```bash
# View recent activity
tail -n 100 logs/mae.log

# Search for errors
grep ERROR logs/mae.log
```

## Development

### Running Tests

```bash
# Test individual modules
python3 src/core/config_loader.py
python3 src/agents/email/email_parser.py
python3 src/agents/classifier/classifier.py
python3 src/agents/actions/email_deleter.py
```

### Adding New Agents

1. Create config: `config/agents/your_agent.yaml`
2. Set `agent_name`, `email.address`, and credentials
3. Run: `python3 main.py --once`

## Documentation

- **[App Password Setup](docs/gmail_app_password_setup.md)**: Simplest authentication guide (Recommended)
- **[OAuth Setup Guide](docs/oauth_setup.md)**: Alternative Google Cloud authentication guide
- **[Google Calendar Setup](docs/google_calendar_setup.md)**: Calendar-specific credentials guide
- **[Future Scope](docs/future_scope.md)**: Planned features

## Roadmap

**Completed** (Modules 1-7):
- ✅ Core infrastructure & Orchestrator
- ✅ Gmail integration (OAuth 2.0)
- ✅ AI classification (MobileBERT + RKNN/ONNX)
- ✅ Smart email management (Delete/Archive/Label)
- ✅ Attachment saving & deduplication
- ✅ Calendar event extraction & integration
- ✅ Web UI Management Dashboard
- ✅ Historical bulk processing

**Future** (Module 8+):
- ⏳ OneDrive/Cloud storage integration
- ⏳ Additional email providers (Outlook, generic IMAP)
- ⏳ Enhanced AI models (Summarization, Action extraction)
- ⏳ Multi-user support

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Support

For issues or questions:
1. Check [docs/](docs/) for detailed documentation
2. Review logs in `logs/mae.log`
3. Open an issue on GitHub

---

**MAE**: Making email management effortless with AI 🚀
