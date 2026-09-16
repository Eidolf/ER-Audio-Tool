// Background service worker for er-audio-tool Chrome extension
// Manages authentication and tab selection sync with local loopback server

chrome.runtime.onInstalled.addListener(() => {
  console.log("er-audio-tool companion extension installed");
});

let isRecording = false;
let activeTabInfo = null;

// Communicates events to loopback TCP/WebSocket or native server
async function sendToDesktopServer(payload, token) {
  try {
    const resp = await fetch("http://127.0.0.1:58291/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, token })
    });
    return await resp.json();
  } catch (err) {
    // Port might be raw stream or HTTP
    return null;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "START_CAPTURE") {
    isRecording = true;
    activeTabInfo = message.tabInfo || null;
    chrome.action.setBadgeText({ text: "REC" });
    chrome.action.setBadgeBackgroundColor({ color: "#e53935" });
    sendResponse({ status: "started" });
  } else if (message.action === "STOP_CAPTURE") {
    isRecording = false;
    activeTabInfo = null;
    chrome.action.setBadgeText({ text: "" });
    sendResponse({ status: "stopped" });
  } else if (message.action === "GET_STATE") {
    sendResponse({ isRecording, activeTabInfo });
  } else if (message.action === "TAB_SELECTED") {
    activeTabInfo = message.tabInfo;
    sendResponse({ status: "ok" });
  }
  return true;
});
