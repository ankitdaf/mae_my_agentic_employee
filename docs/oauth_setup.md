# OAuth Credentials Setup for MAE

This guide explains how to set up Google OAuth 2.0 credentials for Gmail and Google Calendar access on your headless server.

## Required Files

Place these files in `config/secrets/`:

1. **`gmail_credentials.json`** - OAuth credentials for Gmail access
2. **`gcal_credentials.json`** - OAuth credentials for Google Calendar access

### How to obtain these files?

You have two options:

#### Option A: Use the pre-configured MAE App (Easiest)
If you don't want to create your own Google Cloud project, you can request access to the pre-configured MAE application.
- **Action**: Send an email to **<user-email>** requesting the `gmail_credentials.json` file for MAE.
- **Benefit**: Skip Steps 1-4 below. You will still need to perform the one-time authorization (Step 6) to grant the app access to your specific Gmail account.

#### Option B: Create your own Google Cloud App
Follow the step-by-step instructions below to create your own project and credentials.

## Step-by-Step Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Name it something like "MAE Email Agent"

### Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for and enable:
   - **Gmail API**
   - **Google Calendar API** (if using calendar features)

### Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose **External** (unless you have a Google Workspace)
   - Fill in app name: "MAE Email Agent"
   - Add your email as a test user
   - Add scopes:
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://mail.google.com/`
     - `https://www.googleapis.com/auth/calendar` (if using calendar)
4. For Application type, choose **Desktop app**
5. Name it "MAE Desktop Client"
6. Click **Create**

### Step 4: Download and Install Credentials

1. After creating, click the **Download** button (⬇️) next to your OAuth client
2. This downloads a JSON file (usually named `client_secret_*.json`)
3. Copy it to your server and place in the secrets directory:

   **On your local machine:**
   ```bash
   scp ~/Downloads/client_secret_*.json your-server:~/mae-credentials.json
   ```

   **On your server:**
   ```bash
   cd /path/to/mae
   mv ~/mae-credentials.json config/secrets/gmail_credentials.json
   
   # If using calendar, copy it again
   cp config/secrets/gmail_credentials.json config/secrets/gcal_credentials.json
   
   # Set restrictive permissions
   chmod 600 config/secrets/*.json
   ```

## First-Time Authorization (Headless Mode)

When you run MAE for the first time, it will use **console-based OAuth flow**:

1. **The agent will print a URL** like:
   ```
   Please visit this URL to authorize this application:
   https://accounts.google.com/o/oauth2/auth?client_id=...
   ```

2. **Copy the URL** and open it in a browser **on any machine** (your laptop, desktop, etc.)

3. **Sign in** with your Google account (the one you want to use for email)

4. **Grant permissions** to the app:
   - You may see a warning that the app isn't verified
   - Click "Advanced" > "Go to MAE Email Agent (unsafe)"
   - Click "Allow" to grant permissions

5. **Copy the authorization code** that appears in the browser

6. **Paste the code** back into the terminal where MAE is running

7. **Done!** The tokens will be saved in `data/<agent_name>/oauth_tokens.json`

## Example Authorization Flow

```bash
# Run the orchestrator
(venv) $ python -m src.orchestrator.orchestrator --once

# You'll see output like:
[personal] Starting OAuth authorization flow...
[personal] Running in headless mode - please authorize via URL

Please visit this URL to authorize this application:
https://accounts.google.com/o/oauth2/auth?client_id=123456...

Enter the authorization code: █

# Open the URL in your browser, authorize, copy the code, paste it here
# Then press Enter
```

## Token Management

- **Tokens are saved** in `data/<agent_name>/oauth_tokens.json`
- **Tokens auto-refresh** - you won't need to re-authorize unless:
  - You revoke access in your Google account
  - The refresh token expires (rare)
  - You delete the token file

## Security Best Practices

- ✅ **Never commit credentials to git** (already in `.gitignore`)
- ✅ **Use restrictive permissions**: `chmod 600 config/secrets/*.json`
- ✅ **Keep tokens secure**: Token files are also protected
- ✅ **Use test users**: Add your email as a test user in OAuth consent screen

## Troubleshooting

### "OAuth credentials not found" error

**Problem:** The credentials file doesn't exist or isn't in the right location.

**Solution:**
```bash
ls -la config/secrets/gmail_credentials.json
# If missing, follow Step 4 above
```

### "Access blocked: This app's request is invalid"

**Problem:** You haven't added your email as a test user.

**Solution:**
1. Go to Google Cloud Console > OAuth consent screen
2. Scroll to "Test users"
3. Click "Add Users"
4. Add your Gmail address
5. Save and try again

### "Invalid grant" or "Token expired" errors

**Problem:** The saved token is invalid or expired.

**Solution:**
```bash
# Delete the token file
rm data/personal/oauth_tokens.json

# Re-run the agent to re-authorize
python -m src.orchestrator.orchestrator --once
```

### "could not locate runnable browser"

**Problem:** The OAuth flow is trying to open a browser (old code).

**Solution:** This should be fixed now. If you still see this, make sure you've pulled the latest code changes.

## What's Next?

Once you've authorized successfully:

1. The agent will connect to Gmail via IMAP
2. It will fetch and process your emails
3. Tokens will auto-refresh - no manual intervention needed
4. You can run the agent on a schedule (cron, systemd, etc.)

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API Scopes](https://developers.google.com/gmail/api/auth/scopes)
- [Google Calendar API Scopes](https://developers.google.com/calendar/api/auth)
