# Google Calendar API Setup Guide

This guide walks you through obtaining Google Calendar API credentials for MAE.

## Prerequisites

- A Google account
- Access to Google Cloud Console

## Step-by-Step Instructions

> [!TIP]
> **Fast Track**: If you need help setting up your own Google Cloud project you can email **ankitdaf@gmail.com** for help.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click **"New Project"**
4. Enter project details:
   - **Project name**: `MAE Email Processing` (or your preferred name)
   - **Organization**: Leave as default or select your organization
5. Click **"Create"**
6. Wait for the project to be created (you'll see a notification)

### Step 2: Enable Google Calendar API

1. In the Google Cloud Console, ensure your new project is selected
2. Navigate to **"APIs & Services"** > **"Library"** (from the left sidebar)
3. Search for **"Google Calendar API"**
4. Click on **"Google Calendar API"** in the results
5. Click **"Enable"**
6. Wait for the API to be enabled

### Step 3: Configure OAuth Consent Screen

1. Navigate to **"APIs & Services"** > **"OAuth consent screen"**
2. Select **"External"** user type (unless you have a Google Workspace account)
3. Click **"Create"**
4. Fill in the required fields:
   - **App name**: `MAE Email Agent`
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click **"Save and Continue"**
6. On the **Scopes** page, click **"Add or Remove Scopes"**
7. Search for and select:
   - `https://www.googleapis.com/auth/calendar` (Manage your calendars)
   - `https://www.googleapis.com/auth/calendar.events` (View and edit events)
8. Click **"Update"** then **"Save and Continue"**
9. On the **Test users** page, click **"Add Users"**
10. Add your Gmail address (the one you'll process emails for)
11. Click **"Save and Continue"**
12. Review and click **"Back to Dashboard"**

### Step 4: Create OAuth 2.0 Credentials

1. Navigate to **"APIs & Services"** > **"Credentials"**
2. Click **"+ Create Credentials"** at the top
3. Select **"OAuth client ID"**
4. Fill in the details:
   - **Application type**: Select **"Desktop app"**
   - **Name**: `MAE Desktop Client`
5. Click **"Create"**
6. A dialog appears with your credentials - click **"Download JSON"**
7. Save the file as `google_calendar_credentials.json`

### Step 5: Install the Credentials

1. On your RK3566 device, create the secrets directory:
   ```bash
   mkdir -p /path/to/mae/config/secrets
   ```

2. Copy the downloaded JSON file to the secrets directory:
   ```bash
   # If transferring from your PC:
   scp google_calendar_credentials.json <user>@<ip-address>:/path/to/mae/config/secrets/
   ```

3. Verify the file exists:
   ```bash
   ls -l /path/to/mae/config/secrets/google_calendar_credentials.json
   ```

### Step 6: First-Time Authorization

When you run MAE for the first time with calendar integration enabled, it will:

1. Detect that no OAuth token exists
2. Generate an authorization URL
3. Display the URL in the console/logs
4. Prompt you to visit the URL in a browser

**Authorization steps**:
1. Copy the authorization URL from the console
2. Paste it into a browser (can be on any device)
3. Sign in with the Google account you want to use
4. Grant the requested permissions
5. You'll be redirected to a URL like `http://localhost:8080/?code=...`
6. Copy the **entire URL** from your browser
7. Paste it back into the MAE console when prompted
8. MAE will exchange the code for tokens and save them

The tokens will be saved to `data/{agent_name}/gcal_tokens.json` and will be automatically refreshed when needed.

## Gmail API Setup (Similar Process)

For Gmail IMAP access, follow similar steps but enable the **Gmail API** instead:

1. In Google Cloud Console (same project), go to **"APIs & Services"** > **"Library"**
2. Search for **"Gmail API"**
3. Click **"Enable"**
4. The same OAuth consent screen configuration applies
5. Add scope: `https://www.googleapis.com/auth/gmail.modify`
6. Use the same OAuth client credentials downloaded in Step 4

## Security Best Practices

### Protect Your Credentials

The `google_calendar_credentials.json` file contains sensitive information. Ensure it's protected:

```bash
# Set restrictive permissions
chmod 600 /path/to/mae/config/secrets/google_calendar_credentials.json
```

### Token Storage

OAuth tokens are stored per agent in:
- `data/{agent_name}/gcal_tokens.json` - Google Calendar tokens
- `data/{agent_name}/oauth_tokens.json` - Gmail tokens

These files are automatically excluded from git (via `.gitignore`).

### Revoke Access

If you need to revoke MAE's access to your Google account:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Click **"Third-party apps with account access"**
3. Find **"MAE Email Agent"**
4. Click **"Remove Access"**

To re-authorize, delete the token files and restart MAE:
```bash
rm data/{agent_name}/gcal_tokens.json
rm data/{agent_name}/oauth_tokens.json
```

## Troubleshooting

### "Access blocked: This app's request is invalid"

This usually means the OAuth consent screen is not properly configured.

**Solution**:
1. Go to OAuth consent screen settings
2. Ensure the status is **"Testing"** or **"Published"**
3. Add your email to **"Test users"**
4. Try authorization again

### "The OAuth client was not found"

The credentials file is incorrect or corrupted.

**Solution**:
1. Re-download credentials from Google Cloud Console
2. Ensure the file is valid JSON
3. Check file permissions

### "Token has been expired or revoked"

The saved token is no longer valid.

**Solution**:
```bash
# Delete the token file
rm data/{agent_name}/gcal_tokens.json

# Restart MAE to trigger re-authorization
python src/main.py --config config/agents/your_agent.yaml
```

### "redirect_uri_mismatch"

The OAuth client type is incorrect.

**Solution**:
1. Ensure you selected **"Desktop app"** as the application type
2. If you selected "Web application", create a new OAuth client

## Testing Your Setup

After obtaining credentials, test the connection:

```bash
# Navigate to project directory
cd /path/to/mae

# Run the calendar test script (to be created in Module 6)
python tests/test_gcal_connection.py
```

## Multiple Accounts

Each agent (email account) needs separate authorization:

1. Use the **same** `google_calendar_credentials.json` for all agents
2. Each agent will generate its own token file in `data/{agent_name}/gcal_tokens.json`
3. Authorize each agent separately when first run

## Rate Limits

Google Calendar API has these limits:
- **Queries per day**: 1,000,000
- **Queries per 100 seconds per user**: 50,000

MAE's usage is well within these limits (~1 calendar event per email, processed every 15 minutes).

## Next Steps

Once you have credentials, proceed to:
1. Configure your agent YAML file with `calendar.enabled: true`
2. Run the agent for the first time
3. Complete the authorization flow
4. Verify calendar events are being created

---

**Note**: Keep your `google_calendar_credentials.json` file secure and never commit it to version control!
