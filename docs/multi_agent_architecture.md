# Multi-Agent Architecture for MAE

MAE uses a multi-agent architecture to manage multiple email accounts concurrently.

## Current Architecture (Implemented)

The system uses a centralized orchestrator to manage multiple independent agents.

```
MAE Orchestrator
├── Token Manager (Resource Locking)
├── Agent 1 (Personal)
│   ├── Gmail Client
│   ├── Classifier
│   └── Action Executor
├── Agent 2 (Work)
│   ├── Gmail Client
│   ├── Classifier
│   └── Action Executor
└── ...
```

### Key Components

#### 1. Orchestrator (`src/orchestrator/main.py`)
- Loads agent configurations from `config/agents/*.yaml`.
- Schedules agent execution based on `schedule_interval_minutes`.
- Manages agent lifecycles (start, stop, reload).
- Provides a management server (Web UI) for monitoring.

#### 2. Token Manager (`src/orchestrator/token_manager.py`)
- Prevents resource contention between agents.
- Uses file-based locking (`fcntl.flock()`) for:
    - **NPU**: Only one agent can use the NPU for inference at a time.
    - **IMAP**: Serializes access to email providers if needed.
    - **Calendar**: Manages access to the Google Calendar API.

#### 3. Agent Isolation
- Each agent has its own data directory in `data/{agent_name}/`.
- Isolated logs, OAuth tokens, and email caches.
- Independent configuration for topics, whitelists, and actions.

## Resource Planning (2GB RAM)

MAE is optimized for low-resource hardware like the RK3566.

- **Orchestrator + 1 Agent**: ~250MB RAM.
- **Additional Agents**: ~150MB RAM each (shared Python runtime and model overhead).
- **Recommended Limit**: 3-4 agents on a 2GB system to leave room for the OS.

## Future Possibilities

### Multi-Threading
While currently multi-process for isolation, a multi-threaded approach could further reduce memory overhead by sharing the AI model in memory.

### Distributed Agents
Running agents across multiple devices (e.g., a cluster of Radxa Zero 3s) with a shared task queue.
