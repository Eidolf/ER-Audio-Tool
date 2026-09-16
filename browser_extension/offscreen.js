// offscreen.js – Runs inside the Offscreen Document (has full DOM / AudioContext access).
// Receives a tabCapture streamId from the Service Worker, attaches AudioContext,
// and forwards raw float32 PCM chunks to the local desktop server.

let audioCtx = null;
let sourceNode = null;
let scriptNode = null;
let isCapturing = false;
let desktopToken = "";
let captureSessionId = null;

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "START_OFFSCREEN_CAPTURE") {
    const { streamId, token, captureSession } = message;
    desktopToken = token || "";
    captureSessionId = captureSession || null;
    startCapture(streamId)
      .then(() => sendResponse({ status: "capturing" }))
      .catch((err) => sendResponse({ status: "error", error: err.message }));
    return true; // async response
  }

  if (message.action === "STOP_OFFSCREEN_CAPTURE") {
    stopCapture();
    sendResponse({ status: "stopped" });
  }
});

async function startCapture(streamId) {
  if (isCapturing) {
    stopCapture();
  }

  // getUserMedia with chromeMediaSource 'tab' to attach to the captured tab stream
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: "tab",
          chromeMediaSourceId: streamId,
        },
      },
      video: false,
    });
  } catch (err) {
    throw new Error(`getUserMedia failed for streamId ${streamId}: ${err.message}`);
  }

  audioCtx = new AudioContext({ sampleRate: 48000 });
  sourceNode = audioCtx.createMediaStreamSource(stream);

  // ScriptProcessorNode – deprecated but works in Offscreen documents (has DOM)
  // Chunk size 4096 frames at 48kHz = ~85ms latency per HTTP POST
  const CHUNK_FRAMES = 4096;
  const CHANNELS = 2;
  scriptNode = audioCtx.createScriptProcessor(CHUNK_FRAMES, CHANNELS, CHANNELS);

  scriptNode.onaudioprocess = (event) => {
    if (!isCapturing) return;
    const inputBuffer = event.inputBuffer;
    const ch0 = inputBuffer.getChannelData(0);
    const ch1 = inputBuffer.numberOfChannels > 1
      ? inputBuffer.getChannelData(1)
      : ch0;

    // Interleave L/R into a single Float32Array
    const frames = inputBuffer.length;
    const interleaved = new Float32Array(frames * CHANNELS);
    for (let i = 0; i < frames; i++) {
      interleaved[i * 2]     = ch0[i];
      interleaved[i * 2 + 1] = ch1[i];
    }

    sendPcmChunk(interleaved, CHANNELS, audioCtx.sampleRate);
  };

  // Connect graph: source → scriptProcessor → destination (keeps audio alive)
  sourceNode.connect(scriptNode);
  scriptNode.connect(audioCtx.destination);

  isCapturing = true;
}

function stopCapture() {
  isCapturing = false;
  try { if (scriptNode) { scriptNode.disconnect(); scriptNode = null; } } catch (_) {}
  try { if (sourceNode) { sourceNode.disconnect(); sourceNode = null; } } catch (_) {}
  try { if (audioCtx) { audioCtx.close(); audioCtx = null; } } catch (_) {}
}

async function sendPcmChunk(float32Array, channels, sampleRate) {
  try {
    // Encode Float32Array as base64 for JSON transport
    const uint8 = new Uint8Array(float32Array.buffer, float32Array.byteOffset, float32Array.byteLength);
    let binary = "";
    const len = uint8.byteLength;
    // Build base64 in 8 KB segments to avoid stack overflow on large chunks
    for (let i = 0; i < len; i += 8192) {
      binary += String.fromCharCode(...uint8.subarray(i, Math.min(i + 8192, len)));
    }
    const b64 = btoa(binary);

    await fetch("http://127.0.0.1:58291/api/audio_chunk", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Token": desktopToken,
        "X-Capture-Session-ID": captureSessionId || "",
      },
      body: JSON.stringify({
        token: desktopToken,
        capture_session_id: captureSessionId,
        channels: channels,
        sample_rate: sampleRate,
        sample_format: "float32",
        data: b64,
      }),
    });
  } catch (_) {
    // Non-blocking: drop chunk on network error
  }
}
