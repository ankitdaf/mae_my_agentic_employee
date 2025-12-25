# Module 1: Core Infrastructure - Implementation Notes

## Overview
Module 1 establishes the foundation for MAE with configuration management and resource token system.

## Components Implemented

### 1. Configuration Loader (`src/core/config_loader.py`)

**Purpose**: Load and validate YAML agent configurations with sensible defaults

**Key Features**:
- YAML parsing with `pyyaml`
- Required field validation
- Default value injection for optional settings
- Path resolution (relative → absolute)
- Agent-specific data directory creation
- Support for multiple agents

**Design Choices**:
- **File-based configs**: Each agent has its own YAML file in `config/agents/`
- **Separation of concerns**: Secrets (OAuth tokens) stored separately in `data/{agent}/` (not in git)
- **Defensive defaults**: Safe defaults like `dry_run: true` to prevent accidental deletions
- **Path flexibility**: Supports both relative and absolute paths

**Usage**:
```python
from src.core import load_config

config = load_config("config/agents/personal.yaml")
agent_name = config.get_agent_name()
enabled = config.is_enabled()
email = config.get('email', 'address')
```

**Validation**: Tests with `test_agent.yaml` show proper loading and path resolution

---

### 2. Token Manager (`src/orchestrator/token_manager.py`)

**Purpose**: Prevent resource contention between multiple agent processes

**Key Features**:
- File-based locking using `fcntl.flock()`
- Multiple token types: NPU, IMAP, CALENDAR, GENERAL
- Timeout support with blocking acquisition
- Stale lock detection and cleanup
- Context manager support for automatic release
- Agent-aware logging

**Design Choices**:
- **File-based locks**: Simple, no external dependencies (Redis, etc.)
- **Exclusive locks**: Only one agent can hold a token at a time
- **Stale detection**: Locks older than 1 hour are considered stale and cleaned up
- **Lock metadata**: Stores agent name and timestamp in lock files
- **Graceful degradation**: Timeouts return False instead of raising exceptions

**Usage**:
```python
from src.orchestrator import TokenManager, TokenType

tm = TokenManager()

# Manual acquire/release
tm.acquire(TokenType.NPU, agent_name="personal")
# ... do work ...
tm.release(TokenType.NPU, agent_name="personal")

# Context manager (recommended)
with tm.token(TokenType.NPU, agent_name="personal"):
    # ... do work ...
    pass  # Auto-released on exit
```

**Validation**: Tests show successful acquisition, release, and context manager usage

---

### 3. Example Configuration (`config/agents/personal.yaml.example`)

**Purpose**: Template for creating new agent configurations

**Sections**:
- **agent**: Name, schedule, enabled status
- **email**: Provider and address
- **classification**: Topics, whitelisted/blacklisted senders
- **deletion**: Rules for deleting old promotional emails (`action_on_deletion`, `delete_promotional`, `dry_run`)
- **calendar**: Google Calendar integration toggle
- **logging**: Log level and file path

**Safety Features**:
- `dry_run: true` by default (prevents accidental deletions)
- `deletion.enabled: false` by default
- `calendar.enabled: false` by default
- Extensive inline comments explaining each setting

---

### 4. Project Structure

Created the following directory layout:
```
my-agentic-employee-mae/
├── src/
│   ├── orchestrator/          # Process and resource management
│   │   ├── __init__.py
│   │   └── token_manager.py
│   ├── core/                  # Core utilities
│   │   ├── __init__.py
│   │   └── config_loader.py
│   ├── agents/                # Agent implementations
│   │   ├── email/            # Email processing
│   │   ├── classifier/       # AI classification
│   │   └── actions/          # Email actions
│   └── web/                   # Web UI (future)
│       ├── backend/
│       └── frontend/
├── config/
│   ├── agents/               # Agent YAML configs
│   │   └── personal.yaml.example
│   └── secrets/              # OAuth credentials (gitignored)
├── data/
│   ├── locks/                # Resource token locks
│   ├── models/               # RKNN models
│   └── {agent_name}/        # Per-agent data
│       ├── emails/
│       ├── attachments/
│       ├── oauth_tokens.json
│       └── gcal_tokens.json
├── logs/                     # Agent logs
├── docs/                     # Documentation
├── requirements.txt          # Python dependencies
└── .gitignore               # Exclude secrets and data
```

---

### 5. Security Considerations

**Gitignore**:
- All files in `config/secrets/`
- All `*.json` files except package.json (excludes OAuth tokens)
- Agent data directories (`data/*/`)
- Logs

**File Permissions**: 
Token files should have restrictive permissions:
```bash
chmod 600 data/*/oauth_tokens.json
chmod 600 data/*/gcal_tokens.json
chmod 600 config/secrets/*
```

**No Hardcoded Secrets**: All sensitive data loaded from:
- `config/secrets/gmail_credentials.json` (OAuth app credentials)
- `data/{agent}/oauth_tokens.json` (per-agent OAuth tokens)

---

## Testing Results

### Configuration Loader Test
```bash
$ python3 src/core/config_loader.py config/agents/test_agent.yaml

✓ Configuration loaded successfully
Agent: test_agent
Enabled: True
Schedule: Every 15 minutes
Email: your-email@gmail.com
Data directory: /path/to/mae/data/test_agent
```

### Token Manager Test
```bash
$ python3 src/orchestrator/token_manager.py

[Test] Acquiring NPU token...
[test_agent] Acquired npu token (waited 0.00s)
[Test] Acquired! Holding for 3 seconds...
[Test] Releasing NPU token...
[test_agent] Released npu token

[Test] Testing context manager...
[test_agent] Acquired imap token (waited 0.00s)
[Test] Inside context manager, holding for 2 seconds...
[test_agent] Released imap token
[Test] Exited context manager, token auto-released

✓ All tests passed!
```

### Lock Status Check
```bash
$ python3 src/orchestrator/token_manager.py status

Lock Status:
  npu: available
  imap: available
  calendar: available
  general: available
```

---

## Architectural Decisions

### Why File-Based Locks?
- **Simplicity**: No external dependencies (Redis, RabbitMQ)
- **Lightweight**: Minimal memory overhead
- **Reliable**: POSIX locks are atomic and OS-managed
- **Suitable for RK3566**: Low resource usage

### Why Separate Config Files Per Agent?
- **Isolation**: Each agent independently configured
- **Flexibility**: Different schedules, settings per account
- **Easy Management**: Simple to enable/disable agents
- **Git-Friendly**: Can commit example configs, exclude secrets

### Why YAML Over JSON?
- **Human-Readable**: Comments, cleaner syntax
- **Standard**: Widely used for configuration
- **Validation**: Easy to add schema validation later

---

## Next Steps

Module 1 is complete! Ready to proceed with Module 2 (Gmail Client + Email Parsing).

**Module 2 Goals**:
1. Implement Gmail OAuth 2.0 authentication
2. IMAP email fetching
3. Email parsing (headers, body, attachments)
4. File-based email caching

---

## Dependencies Added

See `requirements.txt`:
- `pyyaml` - Configuration parsing
- `google-auth-*` - OAuth 2.0 and Google APIs
- `python-dateutil` - Date parsing
- `email-validator` - Email validation

**Note**: `rknn-toolkit-lite2` must be installed separately on RK3566 (see `docs/model_conversion.md`)
