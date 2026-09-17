// offscreen.js – Runs inside the Offscreen Document (has full DOM / AudioContext access).
// Receives a tabCapture streamId from the Service Worker, attaches AudioContext,
// and forwards raw float32 PCM chunks to the local desktop server.

let audioCtx = null;
let sourceNode = null;
let scriptNode = null;
let mediaStream = null;
let isCapturing = false;
let desktopToken = "";
let captureSessionId = null;
let currentGeneration = 0;

// Sequential bounded upload queue
let isUploading = false;
const uploadQueue = [];
const MAX_QUEUE_SIZE = 10;

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "START_OFFSCREEN_CAPTURE") {
    const { streamId, token, captureSession, generation } = message;
    desktopToken = token || "";
    captureSessionId = captureSession || null;
    const reqGen = typeof generation === "number" ? generation : ++currentGeneration;
    startCapture(streamId, reqGen)
      .then(() => sendResponse({ status: "capturing" }))
      .catch((err) => sendResponse({ status: "error", error: err.message }));
    return true; // async response
  }

  if (message.action === "STOP_OFFSCREEN_CAPTURE") {
    stopCapture();
    sendResponse({ status: "stopped" });
  }
});

async function startCapture(streamId, gen) {
  stopCapture();
  currentGeneration = gen;

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

  if (gen !== currentGeneration) {
    try {
      stream.getTracks().forEach((track) => track.stop());
    } catch (_) {}
    return;
  }

  mediaStream = stream;
  audioCtx = new AudioContext({ sampleRate: 48000 });
  sourceNode = audioCtx.createMediaStreamSource(stream);

  // ScriptProcessorNode – chunk size 4096 frames at 48kHz = ~85ms latency
  const CHUNK_FRAMES = 4096;
  const CHANNELS = 2;
  scriptNode = audioCtx.createScriptProcessor(CHUNK_FRAMES, CHANNELS, CHANNELS);

  scriptNode.onaudioprocess = (event) => {
    if (!isCapturing || gen !== currentGeneration) return;
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

    queuePcmChunk(interleaved, CHANNELS, audioCtx ? audioCtx.sampleRate : 48000);
  };

  // Connect graph:
  // 1. sourceNode -> scriptNode for capturing PCM chunks
  // 2. sourceNode -> audioCtx.destination so captured tab audio remains audible
  // 3. scriptNode -> audioCtx.destination to keep the ScriptProcessor running
  sourceNode.connect(scriptNode);
  sourceNode.connect(audioCtx.destination);
  scriptNode.connect(audioCtx.destination);

  isCapturing = true;
}

function stopCapture() {
  currentGeneration++;
  isCapturing = false;

  uploadQueue.length = 0;
  isUploading = false;

  if (mediaStream) {
    try {
      mediaStream.getTracks().forEach((track) => track.stop());
    } catch (_) {}
    mediaStream = null;
  }

  try { if (scriptNode) { scriptNode.disconnect(); scriptNode = null; } } catch (_) {}
  try { if (sourceNode) { sourceNode.disconnect(); sourceNode = null; } } catch (_) {}
  try { if (audioCtx) { audioCtx.close(); audioCtx = null; } } catch (_) {}
}

function queuePcmChunk(float32Array, channels, sampleRate) {
  if (uploadQueue.length >= MAX_QUEUE_SIZE) {
    // Drop oldest to bound memory while preserving recent order
    uploadQueue.shift();
  }
  uploadQueue.push({ float32Array, channels, sampleRate });
  processUploadQueue();
}

async function processUploadQueue() {
  if (isUploading || uploadQueue.length === 0 || !isCapturing) {
    return;
  }

  isUploading = true;
  const chunk = uploadQueue.shift();

  try {
    await sendPcmChunk(chunk.float32Array, chunk.channels, chunk.sampleRate);
  } finally {
    isUploading = false;
    if (uploadQueue.length > 0 && isCapturing) {
      processUploadQueue();
    }
  }
}

async function sendPcmChunk(float32Array, channels, sampleRate) {
  try {
    const uint8 = new Uint8Array(float32Array.buffer, float32Array.byteOffset, float32Array.byteLength);
    let binary = "";
    const len = uint8.byteLength;
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

