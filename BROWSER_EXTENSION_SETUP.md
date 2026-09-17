# Browser Extension Setup Guide

This guide walks you through setting up the er-audio-tool browser companion extension for Chrome, Edge, Brave, or other Chromium-based browsers.

---

## Overview

The browser extension enables er-audio-tool to record audio from specific browser tabs with explicit user consent. The extension communicates exclusively with your local desktop application via a secure loopback connection (127.0.0.1).

**Privacy Note:** The extension only captures audio from tabs you explicitly select. No browsing data, URLs, or audio is sent to external servers.

---

## Prerequisites

- er-audio-tool desktop application installed and running
- Chrome, Edge, Brave, or another Chromium-based browser
- Browser Developer Mode enabled (for loading unpacked extensions)

---

## Installation Steps

### Step 1: Locate the Browser Extension Directory

The extension files are bundled with er-audio-tool in the `browser_extension/` folder.

**To find the extension directory:**

1. Launch er-audio-tool desktop application
2. Navigate to **Settings > Browser Integration** or **Devices > Browser Connection**
3. Look for the "Extension Installation Directory" field
4. Click **Copy Path** or **Open Folder** to access the directory

**Alternative:** If running from source, the extension is located at:
```
<er-audio-tool-installation>/browser_extension/
```

**Important:** Do NOT use a temporary `_MEI...` path. The extension directory must be permanent. If you see a temporary path, report this as a bug.

### Step 2: Open Browser Extensions Page

**Chrome / Brave:**
1. Open your browser
2. Navigate to: `chrome://extensions`
3. Or: Menu (⋮) → **Extensions** → **Manage Extensions**

**Edge:**
1. Open Edge
2. Navigate to: `edge://extensions`
3. Or: Menu (⋯) → **Extensions** → **Manage Extensions**

### Step 3: Enable Developer Mode

1. In the top-right corner of the extensions page, find the **Developer mode** toggle
2. Enable **Developer mode** (switch to ON)

This allows you to load extensions that aren't from the Chrome Web Store.

### Step 4: Load the Extension

1. Click the **Load unpacked** button (appears after enabling Developer Mode)
2. Navigate to the `browser_extension/` directory you located in Step 1
3. Select the folder and click **Select Folder** (or **Open**)

The extension should now appear in your list of installed extensions.

### Step 5: Pin the Extension (Optional but Recommended)

1. Click the puzzle piece icon (🧩) in your browser toolbar (extensions menu)
2. Find "er-audio-tool Companion" in the list
3. Click the pin icon (📌) to pin it to your toolbar

This makes it easy to access the extension when you want to record.

---

## Authentication and Pairing

### Step 6: Get Your Pairing Token

1. In the er-audio-tool desktop application, go to **Settings > Browser Integration** or **Devices > Browser Connection**
2. You'll see a **Pairing Token** field with a long hexadecimal string
3. Click **Copy Token** to copy it to your clipboard

**Security Note:** This token authenticates the browser extension with your local desktop application. Keep it private. You can regenerate it at any time by clicking **Regenerate Token**.

### Step 7: Authenticate the Extension

1. Click the extension icon in your browser toolbar
2. In the extension popup, you'll see a **Pairing Token** input field
3. Paste your token (Ctrl+V or Cmd+V)
4. Click **Authenticate** or **Connect**

**If authentication succeeds:**
- The extension popup will show "Connected ✓" or "Authenticated"
- The desktop application will show "Extension Verified & Connected"

**If authentication fails:**
- Double-check you copied the correct token
- Ensure the desktop application is running
- Try clicking **Test Connection** in the desktop app
- See Troubleshooting section below

---

## Recording from a Browser Tab

### Step 8: Select a Tab to Record

1. Click the extension icon to open the popup
2. You'll see a list of your open tabs (audible tabs are highlighted)
3. Click on the tab you want to record
4. The tab will be highlighted in the list
5. The desktop application will show "Tab Selected: [Tab Title]"

**Note:** Some browser restrictions may prevent capturing certain tabs (e.g., chrome:// pages, browser settings).

### Step 9: Start Recording in Desktop App

1. In er-audio-tool, navigate to **Record > Browser Tab** (or **New Recording > Browser Tab**)
2. Verify the correct tab is displayed
3. Click **Start Recording**
4. Audio from the selected tab will now be captured

**The tab will continue playing normally** - the extension captures audio without muting or interfering with playback.

### Step 10: Stop Recording

1. In er-audio-tool, click **Stop** or **Stop and Save**
2. Your recording will be saved to the configured output directory
3. The file will be validated automatically

---

## Connection Health

### Checking Connection Status

**In the Desktop App:**
- Navigate to **Devices > Browser Connection** or **Settings > Browser Integration**
- Look for connection status indicators:
  - 🟢 **Connected & Authenticated** - Ready to record
  - 🟡 **Connected (Not Authenticated)** - Token needed
  - 🔴 **Disconnected** - Extension not connected

**In the Browser Extension:**
- Click the extension icon
- Status appears at the top:
  - **Connected ✓** - Ready
  - **Connecting...** - In progress
  - **Not Connected** - Check desktop app

### Heartbeat

The extension sends periodic "heartbeat" signals to maintain the connection. If the desktop app doesn't receive heartbeats for 5 minutes, the connection is considered expired.

**If connection expires:**
- Reopen the extension popup
- Connection should restore automatically
- If not, click **Reconnect** or re-authenticate

---

## Troubleshooting

### Extension Won't Load

**Problem:** "Manifest file is missing or unreadable"

**Solution:**
- Ensure you selected the correct `browser_extension/` folder
- Check that `manifest.json` exists in the folder
- Verify file permissions (folder must be readable)

---

### Authentication Fails

**Problem:** "Invalid token" or "Authentication failed"

**Possible causes and solutions:**

1. **Wrong token**
   - Copy the token again from the desktop app
   - Ensure no extra spaces before/after the token

2. **Desktop app not running**
   - Start er-audio-tool first
   - Wait for "Server listening" status

3. **Desktop app on different port**
   - Default port is 58291
   - If changed, extension needs manual configuration (advanced)

4. **Firewall blocking loopback**
   - Unlikely, but check firewall settings
   - Allow er-audio-tool loopback connections on 127.0.0.1

---

### "Not Connected" After Authentication

**Problem:** Extension shows "Authenticated" but desktop app shows "Not Connected"

**Solution:**
- These are separate states - this is expected
- Connection is established when extension communicates
- Try selecting a tab in the extension
- Check **Test Connection** in desktop app

---

### Tab Not Appearing in List

**Problem:** Open tab doesn't appear in extension popup

**Possible causes:**
- Tab is a browser internal page (chrome://, edge://)
- Tab has no audio permission (some sites block audio)
- Browser restrictions on extension APIs

**Solution:**
- Try a different tab (e.g., YouTube video)
- Refresh the tab and reopen extension popup
- Check browser console for errors (F12 → Console)

---

### Recording Produces Empty File

**Problem:** Recording completes but file contains no audio or is very small

**Possible causes:**

1. **Wrong tab selected**
   - Verify selected tab in desktop app matches playing tab

2. **Tab wasn't playing audio**
   - Start playing audio before recording
   - Extension captures silence if tab is silent

3. **Browser audio permission denied**
   - Some sites require explicit audio permission
   - Check site permissions in browser

4. **Extension lost connection mid-recording**
   - Check connection status during recording
   - Ensure desktop app stays running

**Solution:**
- Stop recording
- Reselect the tab in extension
- Start playing audio
- Start a new recording
- Verify live level meters show activity in desktop app

---

### Extension Disappeared After Browser Update

**Problem:** Extension gone after browser update

**Solution:**
- Browser updates sometimes disable unpacked extensions
- Go back to `chrome://extensions` or `edge://extensions`
- Re-enable the extension
- If still missing, reload it (Step 4)

---

### Multiple Tabs Playing Audio

**Problem:** Want to record specific tab but multiple tabs have audio

**Solution:**
- The extension captures only the selected tab
- Other tabs will continue playing but won't be recorded
- You can mute other tabs manually if desired

---

### Can't Record Browser System Audio

**Problem:** Want to record all browser audio, not just one tab

**Solution:**
- Use **Record > System Output** mode instead
- This captures all audio from your speakers/headphones
- Includes browser audio plus all other applications

---

## Advanced Configuration

### Custom Port (Advanced Users)

If you changed the default server port (58291) in er-audio-tool:

1. Open `browser_extension/background.js` in a text editor
2. Find the line: `const DESKTOP_PORT = 58291;`
3. Change to your custom port
4. Save the file
5. Reload the extension in browser (`chrome://extensions` → Reload button)

**Note:** Not recommended unless you have port conflicts.

---

## Updating the Extension

When you update er-audio-tool to a new version:

1. The `browser_extension/` files will be updated automatically
2. In your browser, go to `chrome://extensions` or `edge://extensions`
3. Find "er-audio-tool Companion"
4. Click the **Reload** button (🔄)

**If extension path changed:**
- Remove the old extension
- Re-add the new extension directory (Steps 4-7)

---

## Privacy and Security

### What the Extension Can Access

**The extension CAN:**
- See your open tab titles (for selection list)
- Capture audio from tabs you explicitly select
- Communicate with er-audio-tool on localhost (127.0.0.1)

**The extension CANNOT:**
- Access your browsing history
- Read page content or forms
- Capture video or screenshots
- Send data to external servers
- Record without your explicit action

### Data Transmission

- **All communication is local** (127.0.0.1 only)
- **No internet connection** used by extension
- **Tab titles** are sent to desktop app (for display only)
- **Audio data** streams to desktop app for recording
- **No analytics or telemetry**

### Token Security

- Token is stored locally in browser extension storage
- Token is transmitted only to localhost (127.0.0.1:58291)
- Token can be regenerated anytime (invalidates old token)
- Closing browser does not clear token (persists)

To revoke extension access:
1. Click **Regenerate Token** in desktop app
2. Extension will show "Not Authenticated"
3. Re-authenticate with new token if desired

---

## Uninstalling the Extension

To remove the extension:

1. Go to `chrome://extensions` or `edge://extensions`
2. Find "er-audio-tool Companion"
3. Click **Remove**
4. Confirm removal

The desktop application will continue working for non-browser recording modes.

---

## Support

**If you encounter issues not covered here:**

1. Check the desktop app's **Diagnostics** page
2. Look for error messages in:
   - Desktop app status bar
   - Extension popup messages
   - Browser console (F12 → Console tab)
3. Report issues at: https://github.com/Eidolf/ER-Audio-Tool/issues

Include:
- Operating system and version
- Browser and version
- Extension status
- Desktop app status
- Error messages (if any)

---

## Summary Checklist

- [ ] Located `browser_extension/` directory
- [ ] Opened `chrome://extensions` or `edge://extensions`
- [ ] Enabled Developer Mode
- [ ] Loaded unpacked extension
- [ ] Copied pairing token from desktop app
- [ ] Pasted token in extension popup
- [ ] Authenticated successfully
- [ ] Selected a tab
- [ ] Started recording in desktop app
- [ ] Verified audio is being captured (level meters)
- [ ] Stopped recording and checked output file

You're now ready to record browser tab audio with er-audio-tool! 🎉
