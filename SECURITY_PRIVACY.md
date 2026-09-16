# Security and Privacy Statement

## Overview

er-audio-tool is designed with privacy and security as core principles. This document describes the application's security model, data handling practices, and privacy guarantees.

**Last Updated:** 2026-09-17

---

## Core Privacy Principles

### 1. Local-First Architecture

**All processing happens on your device.**

- Audio recording, conversion, analysis, and transcription occur entirely on your local machine
- No audio data is transmitted to external servers
- No cloud processing or storage
- No internet connection required (except optional FFmpeg download)

### 2. Zero Telemetry

**We collect nothing.**

- No analytics or usage tracking
- No crash reports sent to external services
- No user identification or fingerprinting
- No "phone home" behavior

### 3. No External Data Transmission

**Your data stays with you.**

- Recorded audio never leaves your device
- Browser tab titles used only for local display
- No upload features or cloud sync
- All storage is local filesystem only

---

## Security Architecture

### Browser Extension Security

#### Loopback-Only Communication

The browser companion extension communicates exclusively with the desktop application via localhost (127.0.0.1).

**Security guarantees:**
- Extension rejects non-loopback connections
- Desktop server binds only to 127.0.0.1 (not 0.0.0.0)
- No public network exposure
- Firewall traversal not required

#### High-Entropy Authentication Tokens

Desktop and extension authenticate using cryptographic tokens.

**Token specifications:**
- 192-bit random tokens (24 bytes hexadecimal)
- Generated using Python `secrets` module (cryptographically secure)
- Constant-time comparison prevents timing attacks (`secrets.compare_digest`)
- User can regenerate tokens at any time

**Token security:**
- Stored locally in browser extension storage (encrypted by browser)
- Transmitted only to 127.0.0.1 (localhost)
- Never transmitted over internet
- Never logged or written to disk by desktop app

#### Extension Permissions

The browser extension requests minimal permissions:

**Granted permissions:**
- `tabCapture`: Capture audio from tabs you explicitly select
- `storage`: Store pairing token locally in browser

**NOT requested:**
- `browsingData`: No access to history, cookies, or cache
- `webRequest`: No network request interception
- `<all_urls>`: No access to page content
- `webNavigation`: No tracking of navigation

#### Explicit User Consent

Recording requires multiple explicit user actions:

1. User installs extension (Developer Mode)
2. User authenticates extension with token
3. User selects specific tab to record
4. User starts recording in desktop app
5. Browser grants audio capture permission (browser UI)

**No hidden or background recording.**

---

## Data Handling

### What Data is Collected

**er-audio-tool does NOT collect:**
- ❌ Personal information (name, email, IP address)
- ❌ Browsing history or URLs
- ❌ Audio content from recordings
- ❌ Usage statistics or analytics
- ❌ Crash reports
- ❌ Device fingerprints

**er-audio-tool DOES access (locally only):**
- ✅ Audio device list (for device selection)
- ✅ Browser tab titles (for tab selection display)
- ✅ Audio streams (for recording - stays local)
- ✅ Local filesystem (for reading/writing recordings)

### Data Storage

**All data is stored locally on your device:**

- **Recordings:** Saved to user-selected output directory
- **Settings:** Stored in local application config file
- **Logs:** Stored in local `logs/` directory
- **Browser token:** Stored in browser extension storage (browser-encrypted)
- **FFmpeg (optional):** Downloaded to local temporary or application directory

**No cloud storage or synchronization.**

### Log Files

**What's in logs:**
- Application startup and shutdown events
- Audio backend initialization
- Recording start/stop events
- Error messages and warnings
- Device enumeration results

**What's NOT in logs:**
- ❌ Authentication tokens (redacted)
- ❌ Audio data or samples
- ❌ Complete file paths (sanitized)
- ❌ Browser tab URLs (only titles for display)
- ❌ User credentials

**Log access:**
- Logs are stored locally in `logs/` directory
- User can delete logs at any time
- Logs rotate automatically (limited size)

---

## Network Activity

### When Network Access is Used

er-audio-tool connects to the internet ONLY for:

1. **Optional FFmpeg Download** (user-initiated)
   - Source: https://github.com/BtbN/FFmpeg-Builds
   - Purpose: Download audio codec binaries
   - Frequency: Once, or when user requests update
   - Data sent: HTTP GET request only (no user data)

**No other network connections are made.**

### Browser Extension Network Activity

The browser extension makes:
- ❌ **Zero external network requests**
- ✅ **Only localhost (127.0.0.1) connections to desktop app**

Extension does NOT:
- Access external APIs
- Phone home to developers
- Check for updates over network
- Send telemetry or analytics

---

## Threat Model

### What er-audio-tool Protects Against

**Unauthorized remote access:**
- Loopback-only server prevents external connections
- Token authentication prevents unauthorized local applications

**Eavesdropping:**
- All communication stays on localhost (never leaves device)
- No network transmission of audio data

**Unauthorized recording:**
- Explicit user consent required for each recording
- Visible recording indicators
- No background or hidden recording

### What er-audio-tool Does NOT Protect Against

**Local system compromise:**
- If your device is compromised (malware, physical access), attacker may access recordings
- er-audio-tool does not encrypt recordings on disk
- User should use full-disk encryption (BitLocker, LUKS) for data protection

**Browser extension compromise:**
- If browser is compromised, attacker could potentially access extension storage (token)
- User should keep browser updated

**Physical access:**
- Someone with physical access to your device can access recordings
- Lock your device when unattended

**Malicious local applications:**
- Other applications running with your user privileges can access recordings
- Keep system clean of malware

---

## Responsible Use

### Legal Considerations

**Recording consent laws vary by jurisdiction.**

- **One-party consent:** Some regions allow recording with consent of one party (you)
- **Two-party consent:** Other regions require consent of ALL parties being recorded
- **Workplace recording:** May have specific regulations

**User responsibilities:**

⚠️ **You are responsible for complying with local laws regarding audio recording.**

- Obtain necessary consents before recording conversations
- Inform participants they are being recorded where required
- Respect privacy and confidentiality
- Do not use for illegal surveillance or wiretapping

**er-audio-tool is intended for:**
- ✅ Personal recording with consent
- ✅ Capturing your own content (e.g., streaming media you're watching)
- ✅ Recording system audio for archival purposes
- ✅ Music production and analysis
- ✅ Accessibility and transcription

**er-audio-tool is NOT intended for:**
- ❌ Secret or unauthorized recording
- ❌ Wiretapping or surveillance
- ❌ Circumventing DRM or copy protection
- ❌ Recording copyrighted content for redistribution

### Ethical Guidelines

**Be transparent:**
- Inform people when recording conversations
- Respect "do not record" requests

**Respect privacy:**
- Don't record private conversations without consent
- Don't share recordings without permission

**Follow the law:**
- Understand recording laws in your jurisdiction
- Comply with wiretapping and surveillance regulations

---

## Security Best Practices

### For Users

**Protect your recordings:**
- Store recordings in protected directory (not public folders)
- Use full-disk encryption (BitLocker, FileVault, LUKS)
- Delete recordings you no longer need
- Backup important recordings securely

**Protect your system:**
- Keep operating system updated
- Use antivirus/anti-malware software
- Don't run untrusted applications
- Lock device when unattended

**Browser extension security:**
- Only install extension from trusted source (application directory)
- Regenerate token if you suspect compromise
- Remove extension when not in use (optional)

**Token security:**
- Don't share your pairing token
- Regenerate token periodically (optional)
- Token gives local applications access to browser audio

---

## Vulnerability Reporting

**If you discover a security vulnerability:**

1. **Do NOT disclose publicly** until fix is available
2. **Report privately** to: andreas@eidolf.de
3. **Include:**
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

**We will:**
- Acknowledge report within 48 hours
- Investigate and develop fix
- Release patched version
- Credit reporter (if desired)

**Responsible disclosure timeline:**
- Fix developed: Within 2 weeks for critical issues
- Patch released: Within 30 days
- Public disclosure: After patch is widely available

---

## Data Protection Compliance

### GDPR Compliance (European Union)

**Personal data processing:**

er-audio-tool does NOT process personal data as defined by GDPR because:
- No data is collected from users
- No data is transmitted to controllers or processors
- All processing happens locally on user's device
- No user identification or profiling

**User rights:**

Since no data is collected, GDPR rights (access, rectification, erasure, etc.) are not applicable. Users have complete control over all local data.

### CCPA Compliance (California)

er-audio-tool does NOT "sell" personal information because:
- No personal information is collected
- No data sharing with third parties
- All processing is local

---

## Third-Party Dependencies

### Open Source Libraries

er-audio-tool uses open-source libraries. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for complete list.

**Security considerations:**
- Dependencies regularly updated for security patches
- No known vulnerabilities in current versions
- User should keep application updated

### FFmpeg (Optional Download)

**Source:** https://github.com/BtbN/FFmpeg-Builds

**Security considerations:**
- Downloaded via HTTPS
- Downloaded from trusted source (official FFmpeg builds)
- ⚠️ Checksum verification not yet implemented (planned)

**Recommendation:** Verify checksums manually if concerned (checksums available at download source).

---

## Security Audit

**Last audit:** 2026-09-17

**Findings:**
- Core architecture follows security best practices
- Loopback-only design prevents external access
- Token authentication properly implemented
- No telemetry or tracking present
- Improvement needed: FFmpeg checksum verification

**Next audit:** Recommended annually or after major releases

---

## Changes to This Statement

This security and privacy statement may be updated to reflect:
- Changes in application features
- New security measures
- Clarifications based on user feedback

**Users will be notified of significant changes via:**
- Release notes
- README updates
- Security advisories (for critical changes)

**History:**
- 2026-09-17: Initial security and privacy statement

---

## Contact

**Security inquiries:** andreas@eidolf.de  
**General support:** https://github.com/Eidolf/ER-Audio-Tool/issues

---

## Summary

✅ **All processing is local** - Your data never leaves your device  
✅ **Zero telemetry** - We collect nothing  
✅ **Open source** - You can verify our claims by reviewing the code  
✅ **Minimal permissions** - Browser extension requests only necessary permissions  
✅ **Strong authentication** - 192-bit cryptographic tokens  
✅ **Explicit consent** - Recording requires multiple user actions  
✅ **Transparent** - This document describes exactly what we do (and don't do)

**Your privacy is not our product. Your audio is yours alone.**
