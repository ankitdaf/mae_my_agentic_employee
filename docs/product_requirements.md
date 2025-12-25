# Product Requirements - MAE (My Agentic Employee)

MAE is an intelligent, lightweight agentic system designed to run on edge hardware (like RK3566) to manage digital life, starting with email.

## Core Requirements

### 1. Multi-Agent Orchestration
- Support for multiple independent agents running concurrently.
- Resource management (NPU, IMAP, Calendar) using a token-based locking system.
- Agent-specific configurations and data isolation.

### 2. Email Processing
- **Provider Support**: Gmail integration via OAuth 2.0.
- **Incremental Fetching**: Efficiently fetch only new emails since the last processed watermark.
- **Deduplication**: Prevent reprocessing of emails using hash-based tracking.

### 3. AI Classification
- **Categories**: Classify emails into four distinct categories:
    - **Transactions**: Bills, payments, receipts, stock trades.
    - **Feed**: Newsletters, tutorials, announcements.
    - **Promotions**: Sales, offers, marketing emails.
    - **Inbox**: Personal or work-related emails.
- **Model Support**: Optimized for MobileBERT running on RK3566 NPU (RKNN).
- **Fallback**: Rule-based classification when the AI model is unavailable.

### 4. Intelligent Filtering
- **Topic Matching**: Filter emails based on user-defined topics of interest.
- **Sender Management**: Whitelist and blacklist support with wildcard patterns.
- **Smart Deletion**: Automatically move promotional emails to trash or apply labels based on rules and topic matches.

### 5. Integration & Actions
- **Calendar**: Extract events from emails and add them to Google Calendar.
- **Logging**: Comprehensive per-agent logging and run statistics.
- **Management UI**: Web-based dashboard to monitor agents and manage configurations.

## Hardware Constraints
- Target Hardware: RK3566 (e.g., Radxa Zero 3) with 2GB RAM.
- Focus on efficiency and low resource usage.
