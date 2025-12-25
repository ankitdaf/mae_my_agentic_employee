# MAE Email Processing - Implementation Plan

## Overview

Building an intelligent email processing system for RK3566 SBC that automatically manages Gmail accounts using local AI classification, with smart promotional email deletion, attachment management, and calendar integration.

## Architecture Decisions

### Smart Promotional Detection Strategy
A hybrid approach for promotional email management:
1. **AI Classification**: Use MobileBERT to identify promotional emails
2. **Topic Matching**: Extract topics from email content and match against user-defined "topics I care about"
3. **Sender/Domain Lists**: Maintain whitelists (never delete) and blacklists (always delete if old)
4. **Rule**: Delete promotional emails >30 days old UNLESS:
   - Sender/domain is whitelisted
   - Contains topics from user's "care about" list

### OAuth 2.0 for Gmail
Gmail requires OAuth 2.0 for IMAP access (app passwords being deprecated). OAuth flow with local token storage. Each account needs authorization once via browser.

### Orchestrator Design
The orchestrator will:
- Wake agents one at a time based on schedule (configurable interval per agent)
- Use file-based locks for resource tokens
- Wait for agent completion before starting next scheduled agent
- Keep agents as separate processes (not threads)

## Project Structure

```
my-agentic-employee-mae/
├── src/
│   ├── orchestrator/
│   │   ├── orchestrator.py      # Central process manager
│   │   └── token_manager.py     # Resource token management
│   ├── core/
│   │   ├── config_loader.py     # Configuration management
│   │   └── logger.py            # Logging utilities
│   ├── agents/
│   │   ├── email_agent.py       # Main agent process
│   │   ├── email/
│   │   │   ├── gmail_client.py  # Gmail OAuth + IMAP
│   │   │   ├── email_parser.py  # Email parsing
│   │   │   └── email_storage.py # File-based caching
│   │   ├── classifier/
│   │   │   ├── classifier.py    # MobileBERT RKNN
│   │   │   ├── topic_matcher.py # Topic filtering
│   │   │   └── sender_manager.py# Sender/domain lists
│   │   └── actions/
│   │       ├── email_deleter.py # Smart deletion
│   │       ├── attachment_saver.py
│   │       ├── calendar_extractor.py
│   │       └── gcal_client.py   # Google Calendar API
│   └── web/
│       ├── backend/             # FastAPI server
│       └── frontend/            # React + Tailwind
├── config/
│   ├── agents/                  # Agent configs (*.yaml)
│   └── secrets/                 # OAuth credentials (gitignored)
├── data/
│   ├── locks/                   # Resource tokens
│   ├── models/                  # RKNN models
│   └── {agent_name}/           # Per-agent data
│       ├── emails/
│       ├── attachments/
│       ├── oauth_tokens.json
│       └── gcal_tokens.json
└── logs/                        # Agent logs
```

## Module Implementation Plan

### Module 1: Core Infrastructure
**Goal**: Set up configuration management and resource token system

**Components**:
- `src/core/config_loader.py` - Load and validate YAML configs
- `src/orchestrator/token_manager.py` - File-based resource locks
- `config/agents/*.yaml.example` - Example configurations
- `.gitignore` - Exclude secrets and tokens

**Verification**: Load test config, acquire/release tokens

---

### Module 2: Gmail Client + Email Parsing
**Goal**: Fetch and parse emails from Gmail

**Components**:
- `src/agents/email/gmail_client.py` - OAuth 2.0 + IMAP
- `src/agents/email/email_parser.py` - Parse email content
- `src/agents/email/email_storage.py` - Cache emails locally

**Verification**: Fetch test emails, verify parsing and storage

---

### Module 3: AI Classifier + Topic Matcher
**Goal**: Classify emails with MobileBERT and apply topic filtering

**Components**:
- `src/agents/classifier/classifier.py` - RKNN model inference
- `src/agents/classifier/topic_matcher.py` - Keyword matching
- `src/agents/classifier/sender_manager.py` - Whitelist/blacklist

**Verification**: Classify test emails, verify topic/sender filtering

---

### Module 4: Email Deletion Logic
**Goal**: Implement smart deletion with dry-run mode

**Components**:
- `src/agents/actions/email_deleter.py` - Delete old promotional emails

**Verification**: Run dry-run on test account, verify deletion logic

---

### Module 5: Attachment Saver
**Goal**: Save important attachments with deduplication

**Components**:
- `src/agents/actions/attachment_saver.py` - Save files locally

**Verification**: Process emails with attachments, verify saving

---

### Module 6: Calendar Integration
**Goal**: Extract calendar events and sync to Google Calendar

**Components**:
- `src/agents/actions/calendar_extractor.py` - Regex-based extraction
- `src/agents/actions/gcal_client.py` - Google Calendar API

**Verification**: Extract events from test emails, verify GCal sync

---

### Module 7: Complete Orchestrator
**Goal**: Implement agent scheduling and lifecycle management

**Components**:
- `src/orchestrator/orchestrator.py` - Schedule and spawn agents
- `src/agents/email_agent.py` - Main agent entry point

**Verification**: Run multiple agents on schedule, verify execution order

---

### Module 8: Web UI Dashboard
**Goal**: Build React dashboard for management

**Components**:
- `src/web/backend/` - FastAPI REST API
- `src/web/frontend/` - React + Tailwind UI
  - Agent management
  - Configuration editor
  - Email viewer
  - System dashboard

**Verification**: Access UI, test all features

## Configuration Structure

### Agent Configuration Example
```yaml
# config/agents/personal.yaml.example
agent:
  name: "personal"
  schedule_interval_minutes: 15
  enabled: true

email:
  provider: "gmail"
  address: "personal@gmail.com"
  # OAuth tokens stored in: data/personal/oauth_tokens.json (not in git)

classification:
  topics_i_care_about:
    - "machine learning"
    - "kubernetes"
    - "family"
  
  whitelisted_senders:
    - "important-person@example.com"
    - "*@company.com"
  
  blacklisted_senders:
    - "spam@promotions.com"

deletion:
  enabled: true
  age_threshold_days: 30
  delete_promotional: true
  delete_normal: false
  delete_important: false
  dry_run: false

attachments:
  save_important: true
  save_path: "data/personal/attachments"
  max_size_mb: 10
  allowed_extensions: [".pdf", ".doc", ".docx", ".xlsx"]

calendar:
  enabled: true
  # OAuth tokens stored in: data/personal/gcal_tokens.json (not in git)

logging:
  level: "INFO"
  file: "logs/personal.log"
```

## Security Considerations

1. **No Secrets in Git**: All credentials in `config/secrets/` and `data/*/oauth_tokens.json` are gitignored
2. **OAuth Tokens**: Stored locally per agent, not shared
3. **File Permissions**: Token files should be readable only by user (chmod 600)
4. **Environment Variables**: Optional support for sensitive configs via env vars

## Future Scope

Items to implement later:
- **Email Providers**: Outlook, generic IMAP support
- **Cloud Storage**: OneDrive integration for attachments
- **Email Summarization**: ML-based email summaries
- **Multi-language**: Support non-English emails
- **Advanced Topics**: ML-based topic learning instead of keyword matching
- **Mobile App**: React Native companion app
- **Notifications**: Push notifications for important emails

## Performance Targets

- **Memory per Agent**: <220MB
- **NPU Inference**: <2s per email
- **Orchestrator Overhead**: <50MB
- **Max Agents**: 3-4 on 2GB RAM system
- **Email Processing**: ~10 emails/minute per agent

## Development Process

After each module:
1. ✅ Implement code
2. ✅ Document implementation choices
3. ✅ Update architecture docs
4. ✅ Provide test commands
5. ✅ Commit to git (excluding secrets)
6. ✅ Verify on RK3566 hardware

## Getting Started

See [google_calendar_setup.md](google_calendar_setup.md) for Google Calendar API credentials.
See [README.md](../README.md) for installation and usage instructions.
