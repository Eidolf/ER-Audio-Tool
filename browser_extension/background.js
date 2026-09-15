// Background service worker for er-audio-tool Chrome extension
chrome.runtime.onInstalled.addListener(() => {
  console.log("er-audio-tool companion extension installed");
});

let isRecording = false;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "START_CAPTURE") {
    isRecording = true;
    chrome.action.setBadgeText({ text: "REC" });
    chrome.action.setBadgeBackgroundColor({ color: "#e53935" });
    sendResponse({ status: "started" });
  } else if (message.action === "STOP_CAPTURE") {
    isRecording = false;
    chrome.action.setBadgeText({ text: "" });
    sendResponse({ status: "stopped" });
  } else if (message.action === "GET_STATE") {
    sendResponse({ isRecording });
  }
  return true;
});
