// Background service worker for er-audio-tool Chrome extension
// Manages authentication, tab selection sync, and audio stream transport with local loopback server

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

// Periodic interval fallback
setInterval(() => {
  performHeartbeat();
}, 20000);

async function performHeartbeat() {
  chrome.storage.local.get(["sessionToken", "selectedTabId"], async (stored) => {
    const token = stored.sessionToken;
    if (!token) return;
    await sendToDesktopServer("/api/heartbeat", { extension_id: "chrome-companion" }, token);
  });
}

let isRecording = false;
let activeTabInfo = null;
let activeStream = null;
let mediaRecorder = null;
let captureSessionId = null;

// Communicates events to loopback HTTP server
async function sendToDesktopServer(endpoint, payload, token) {
  try {
    const resp = await fetch(`http://127.0.0.1:58291${endpoint}`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-Session-Token": token || ""
      },
      body: JSON.stringify({ ...payload, token })
    });
    return await resp.json();
  } catch (err) {
    return null;
  }
}

// Sends binary/PCM audio chunk to loopback desktop server
async function sendAudioChunk(float32Array, channels, sampleRate, token) {
  try {
    // Convert Float32Array to base64
    const uint8 = new Uint8Array(float32Array.buffer, float32Array.byteOffset, float32Array.byteLength);
    let binary = "";
    const len = uint8.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(uint8[i]);
    }
    const b64 = btoa(binary);

    await fetch("http://127.0.0.1:58291/api/audio_chunk", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Token": token || "",
        "X-Capture-Session-ID": captureSessionId || ""
      },
      body: JSON.stringify({
        token: token || "",
        capture_session_id: captureSessionId,
        channels: channels || 2,
        sample_rate: sampleRate || 48000,
        sample_format: "float32",
        data: b64
      })
    });
  } catch (err) {
    // Non-blocking error handling
  }
}

function stopTabAudioCapture() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try {
      mediaRecorder.stop();
    } catch (e) {}
    mediaRecorder = null;
  }
  if (activeStream) {
    try {
      activeStream.getTracks().forEach(t => t.stop());
    } catch (e) {}
    activeStream = null;
  }
  isRecording = false;
  activeTabInfo = null;
  captureSessionId = null;
  chrome.action.setBadgeText({ text: "" });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "START_CAPTURE") {
    isRecording = true;
    activeTabInfo = message.tabInfo || null;
    chrome.action.setBadgeText({ text: "REC" });
    chrome.action.setBadgeBackgroundColor({ color: "#e53935" });

    chrome.storage.local.get(["sessionToken"], (stored) => {
      const token = stored.sessionToken;
      sendToDesktopServer("/api/tab_selected", { tabInfo: activeTabInfo }, token);

      // Start actual tab audio capture if tabCapture is available
      if (chrome.tabCapture && typeof chrome.tabCapture.capture === "function") {
        try {
          chrome.tabCapture.capture({ audio: true, video: false }, (stream) => {
            if (chrome.runtime.lastError || !stream) {
              console.warn("tabCapture failed:", chrome.runtime.lastError);
              return;
            }
            activeStream = stream;
            // Web Audio API or MediaRecorder to capture chunks
            try {
              const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
              const source = audioCtx.createMediaStreamSource(stream);
              // Maintain local audio playback so tab audio remains audible to user
              source.connect(audioCtx.destination);

              // Capture PCM audio using ScriptProcessor/AudioWorklet
              const scriptNode = audioCtx.createScriptProcessor(4096, 2, 2);
              scriptNode.onaudioprocess = (audioProcessingEvent) => {
                if (!isRecording) return;
                const inputBuffer = audioProcessingEvent.inputBuffer;
                const ch0 = inputBuffer.getChannelData(0);
                const ch1 = inputBuffer.numberOfChannels > 1 ? inputBuffer.getChannelData(1) : ch0;
                const frames = inputBuffer.length;
                const interleaved = new Float32Array(frames * 2);
                for (let i = 0; i < frames; i++) {
                  interleaved[i * 2] = ch0[i];
                  interleaved[i * 2 + 1] = ch1[i];
                }
                sendAudioChunk(interleaved, 2, audioCtx.sampleRate, token);
              };
              source.connect(scriptNode);
              scriptNode.connect(audioCtx.destination);
            } catch (ctxErr) {
              // Fallback to MediaRecorder if AudioContext is unavailable in worker context
              try {
                mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
                mediaRecorder.ondataavailable = async (e) => {
                  if (e.data && e.data.size > 0 && isRecording) {
                    // Send chunk
                    const buf = await e.data.arrayBuffer();
                    const uint8 = new Uint8Array(buf);
                    let binary = "";
                    for (let i = 0; i < uint8.byteLength; i++) {
                      binary += String.fromCharCode(uint8[i]);
                    }
                    fetch("http://127.0.0.1:58291/api/audio_chunk", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/octet-stream",
                        "X-Session-Token": token || ""
                      },
                      body: buf
                    }).catch(() => {});
                  }
                };
                mediaRecorder.start(250);
              } catch (recErr) {}
            }
          });
        } catch (e) {
          console.warn("Exception invoking tabCapture:", e);
        }
      }
    });
    sendResponse({ status: "started" });
  } else if (message.action === "STOP_CAPTURE") {
    stopTabAudioCapture();
    sendResponse({ status: "stopped" });
  } else if (message.action === "GET_STATE") {
    sendResponse({ isRecording, activeTabInfo });
  } else if (message.action === "TAB_SELECTED") {
    activeTabInfo = message.tabInfo;
    chrome.storage.local.get(["sessionToken"], (stored) => {
      sendToDesktopServer("/api/tab_selected", { tabInfo: activeTabInfo }, stored.sessionToken);
    });
    sendResponse({ status: "ok" });
  }
  return true;
});
