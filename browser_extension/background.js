// Background service worker for er-audio-tool Chrome extension
// Manages authentication, tab selection sync, and audio stream transport.
//
// ARCHITECTURE (Manifest V3):
//   Service Worker (this file) – has no DOM, no AudioContext.
//   Offscreen Document (offscreen.html + offscreen.js) – has DOM + AudioContext.
//
// Audio capture flow:
//   1. SW calls chrome.tabCapture.getMediaStreamId() → streamId
//   2. SW creates/reuses Offscreen Document
//   3. SW sends streamId + token to Offscreen via chrome.runtime.sendMessage
//   4. Offscreen attaches getUserMedia(chromeMediaSourceId=streamId), runs
//      AudioContext + ScriptProcessorNode, sends float32 PCM chunks to desktop server.

chrome.runtime.onInstalled.addListener(() => {
  console.log("er-audio-tool companion extension installed");
  setupHeartbeatAlarm();
});

chrome.runtime.onStartup.addListener(() => {
  setupHeartbeatAlarm();
});

function setupHeartbeatAlarm() {
  if (chrome.alarms) {
    chrome.alarms.create("er_audio_heartbeat", { periodInMinutes: 0.5 });
  }
}

if (chrome.alarms) {
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "er_audio_heartbeat") {
      performHeartbeat();
    }
  });
}

// Periodic interval fallback (service worker may wake on alarms)
setInterval(() => {
  performHeartbeat();
}, 20000);

async function performHeartbeat() {
  chrome.storage.local.get(["sessionToken"], async (stored) => {
    const token = stored.sessionToken;
    if (!token) return;
    await sendToDesktopServer("/api/heartbeat", { extension_id: "chrome-companion" }, token);
  });
}

// ── State ──────────────────────────────────────────────────────────────────────
let isRecording = false;
let activeTabInfo = null;
let captureSessionId = null; // remains null – desktop server generates the real ID

// ── Desktop Server Communication ───────────────────────────────────────────────
async function sendToDesktopServer(endpoint, payload, token) {
  try {
    const resp = await fetch(`http://127.0.0.1:58291${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Token": token || "",
      },
      body: JSON.stringify({ ...payload, token }),
    });
    return await resp.json();
  } catch (_) {
    return null;
  }
}

// ── Offscreen Document Lifecycle ───────────────────────────────────────────────
async function ensureOffscreenDocument() {
  // chrome.offscreen API is available from Chrome 109+
  if (!chrome.offscreen) {
    throw new Error("chrome.offscreen API not available (Chrome 109+ required).");
  }
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
  });
  if (existingContexts.length > 0) {
    return; // already open
  }
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA"],
    justification: "Capture tab audio via AudioContext (not available in Service Worker)",
  });
}

async function closeOffscreenDocument() {
  if (!chrome.offscreen) return;
  try {
    await chrome.offscreen.closeDocument();
  } catch (_) {}
}

// ── Tab Audio Capture ──────────────────────────────────────────────────────────
async function startTabAudioCapture(tabInfo, token) {
  if (!chrome.tabCapture || typeof chrome.tabCapture.getMediaStreamId !== "function") {
    console.warn("chrome.tabCapture.getMediaStreamId not available");
    return;
  }

  let streamId;
  try {
    streamId = await new Promise((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId(
        { targetTabId: tabInfo.id },
        (id) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(id);
          }
        }
      );
    });
  } catch (err) {
    console.warn("tabCapture.getMediaStreamId failed:", err.message);
    return;
  }

  try {
    await ensureOffscreenDocument();
  } catch (err) {
    console.warn("Could not create offscreen document:", err.message);
    return;
  }

  // Forward streamId to Offscreen Document to start AudioContext capture
  try {
    await chrome.runtime.sendMessage({
      action: "START_OFFSCREEN_CAPTURE",
      streamId: streamId,
      token: token,
      captureSession: captureSessionId, // null – desktop server validates its own sessions
    });
  } catch (err) {
    console.warn("Offscreen message failed:", err.message);
  }
}

async function stopTabAudioCapture() {
  // Tell offscreen to stop
  try {
    await chrome.runtime.sendMessage({ action: "STOP_OFFSCREEN_CAPTURE" });
  } catch (_) {}
  await closeOffscreenDocument();

  isRecording = false;
  activeTabInfo = null;
  captureSessionId = null;
  try { chrome.action.setBadgeText({ text: "" }); } catch (_) {}
}

// ── Message Handler ────────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "START_CAPTURE") {
    isRecording = true;
    activeTabInfo = message.tabInfo || null;
    try {
      chrome.action.setBadgeText({ text: "REC" });
      chrome.action.setBadgeBackgroundColor({ color: "#e53935" });
    } catch (_) {}

    chrome.storage.local.get(["sessionToken"], async (stored) => {
      const token = stored.sessionToken;

      // Notify desktop server which tab was selected
      await sendToDesktopServer("/api/tab_selected", { tabInfo: activeTabInfo }, token);

      // Start audio capture through Offscreen Document
      if (activeTabInfo) {
        await startTabAudioCapture(activeTabInfo, token);
      }
    });

    sendResponse({ status: "started" });

  } else if (message.action === "STOP_CAPTURE") {
    stopTabAudioCapture().then(() => sendResponse({ status: "stopped" }));
    return true; // async

  } else if (message.action === "GET_STATE") {
    sendResponse({ isRecording, activeTabInfo });

  } else if (message.action === "TAB_SELECTED") {
    activeTabInfo = message.tabInfo;
    chrome.storage.local.get(["sessionToken"], (stored) => {
      sendToDesktopServer("/api/tab_selected", { tabInfo: activeTabInfo }, stored.sessionToken);
    });
    sendResponse({ status: "ok" });
  }

  return true; // keep message channel open for async responses
});
