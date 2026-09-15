// Popup controller for er-audio-tool tab capture
document.addEventListener("DOMContentLoaded", async () => {
  const btnToggle = document.getElementById("btnToggle");
  const tokenInput = document.getElementById("tokenInput");
  const statusBadge = document.getElementById("statusBadge");

  // Load stored token
  const stored = await chrome.storage.local.get(["sessionToken"]);
  if (stored.sessionToken) {
    tokenInput.value = stored.sessionToken;
  }

  // Check state
  chrome.runtime.sendMessage({ action: "GET_STATE" }, (response) => {
    if (response && response.isRecording) {
      setRecordingUI(true);
    }
  });

  btnToggle.addEventListener("click", async () => {
    const token = tokenInput.value.trim();
    if (!token) {
      alert("Please paste the Session Auth Token from er-audio-tool Settings/Browser tab.");
      return;
    }
    await chrome.storage.local.set({ sessionToken: token });

    chrome.runtime.sendMessage({ action: "GET_STATE" }, (res) => {
      if (res && res.isRecording) {
        chrome.runtime.sendMessage({ action: "STOP_CAPTURE" }, () => setRecordingUI(false));
      } else {
        chrome.runtime.sendMessage({ action: "START_CAPTURE" }, () => setRecordingUI(true));
      }
    });
  });

  function setRecordingUI(recording) {
    if (recording) {
      btnToggle.textContent = "Stop Tab Capture";
      btnToggle.className = "btn-stop";
      btnToggle.style.display = "block";
      statusBadge.textContent = "Status: Recording Tab Audio";
      statusBadge.className = "badge badge-rec";
    } else {
      btnToggle.textContent = "Record Active Tab";
      btnToggle.className = "btn-start";
      statusBadge.textContent = "Status: Idle";
      statusBadge.className = "badge badge-idle";
    }
  }
});
