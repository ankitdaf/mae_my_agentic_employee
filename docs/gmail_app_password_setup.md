# Gmail App Password Setup Guide

This guide explains how to set up Gmail authentication using an **App Password**. This is the recommended method for most users as it is much simpler to set up than OAuth 2.0 and works reliably on headless devices like the RK3566.

## Why use an App Password?

- **Simplicity**: No need to create a Google Cloud Project or deal with JSON credential files.
- **Headless Friendly**: Does not require a web browser on the device to complete the authentication flow.
- **Reliable**: Works even if your Google account has 2-Step Verification enabled.

## Prerequisites

- A Gmail account with **2-Step Verification** enabled. (Google requires 2FA to be active before you can create an App Password).

## Step-by-Step Instructions

### 1. Enable 2-Step Verification
If you haven't already:
1. Go to your [Google Account](https://myaccount.google.com/).
2. Select **Security** in the left navigation panel.
3. Under "How you sign in to Google," make sure **2-Step Verification** is turned on.

### 2. Create an App Password
1. Go directly to the [App Passwords page](https://myaccount.google.com/apppasswords).
2. You may be asked to sign in again.
3. In the "App" dropdown, select **Mail**.
4. In the "Device" dropdown, select **Other (Custom name)** and enter a name like `MAE-Agent`.
5. Click **Generate**.
6. Google will display a **16-character password** in a yellow box (e.g., `abcd efgh ijkl mnop`). **Copy this password immediately.**

### 3. Configure MAE via Web UI
Once you have your App Password:
1. Open the MAE Dashboard (usually at `http://<your-device-ip>:8000`).
2. Select the agent you want to configure from the sidebar.
3. Look for the **Authentication Status** bar at the top and click **Setup App Password**.
4. Enter your **Gmail Address** and paste the **16-character App Password**.
   - Note: Spaces and dashes are automatically handled; you don't need to remove them.
5. Click **Test Connection** to verify it works.
6. Click **Save**.

### 4. Manual Configuration (Optional)
If you prefer not to use the Web UI, you can store the credentials manually using the MAE CLI (internal utility):

```bash
# This is currently managed via the CredentialManager class.
# Future updates will include a CLI tool for this.
```

## Troubleshooting

- **Invalid Password**: Ensure you haven't included any extra spaces at the beginning or end.
- **IMAP Disabled**: Ensure IMAP is enabled in your Gmail settings:
  1. Open Gmail on your computer.
  2. Click **Settings** (gear icon) > **See all settings**.
  3. Click the **Forwarding and POP/IMAP** tab.
  4. In the "IMAP access" section, select **Enable IMAP**.
  5. Click **Save Changes**.

## Security Notes

- App Passwords grant full access to your Gmail account.
- MAE stores these credentials securely using the system keyring or an AES-256 encrypted file on your device.
- If you ever lose your device or want to revoke access, you can delete the App Password from your Google Account settings.
