# Email Processing Agent

The Email Agent is the primary agent in MAE, responsible for fetching, classifying, and taking actions on emails.

## Scope
This agent processes emails periodically and performs automated actions based on AI classification and user-defined rules.

### Classification Categories
- **Transactions**: Bills, payments, receipts, stock trades.
- **Feed**: Newsletters, tutorials, announcements.
- **Promotions**: Sales, offers, marketing emails.
- **Inbox**: Personal/work emails (default).

### Automated Actions
- **Promotions**: Moved to Trash or labeled (configurable via `action_on_deletion`).
- **Transactions & Feed**: Marked as read and archived to "All Mail".
- **Inbox**: Stays in the inbox for manual review.

### Filtering Rules
- **Whitelisted Senders**: Emails from these senders are always kept in the inbox.
- **Blacklisted Senders**: Emails from these senders are always targeted for deletion.
- **Topics of Interest**: Promotional emails matching these topics are preserved in the inbox.

## Planned Features
- **Email Summarization**: ML-based summaries for important emails.
- **Attachment Management**: Automatically saving and filing important attachments to local or cloud storage.
- **Multi-Provider Support**: Integration with Outlook and generic IMAP providers.