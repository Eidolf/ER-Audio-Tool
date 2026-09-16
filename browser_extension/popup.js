// Popup controller for er-audio-tool tab capture & tab selection
document.addEventListener("DOMContentLoaded", async () => {
  const btnToggle = document.getElementById("btnToggle");
  const tokenInput = document.getElementById("tokenInput");
  const statusBadge = document.getElementById("statusBadge");
  const tabListContainer = document.getElementById("tabList");
  const btnRefreshTabs = document.getElementById("btnRefreshTabs");

  let selectedTabId = null;
  let availableTabs = [];

  // Load stored auth token
  const stored = await chrome.storage.local.get(["sessionToken", "selectedTabId"]);
  if (stored.sessionToken) {
    tokenInput.value = stored.sessionToken;
  }
  if (stored.selectedTabId) {
    selectedTabId = stored.selectedTabId;
  }

  // Load tabs list
  await refreshTabsList();

  btnRefreshTabs.addEventListener("click", refreshTabsList);

  // Send immediate heartbeat if token present and periodically while open
  if (stored.sessionToken) {
    fetch("http://127.0.0.1:58291/api/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Token": stored.sessionToken },
      body: JSON.stringify({ token: stored.sessionToken })
    }).catch(() => {});
  }
  setInterval(() => {
    const curTok = tokenInput.value.trim();
    if (curTok) {
      fetch("http://127.0.0.1:58291/api/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Session-Token": curTok },
        body: JSON.stringify({ token: curTok })
      }).catch(() => {});
    }
  }, 15000);

  // Check current recording state
  chrome.runtime.sendMessage({ action: "GET_STATE" }, (response) => {
    if (response && response.isRecording) {
      setRecordingUI(true);
      if (response.activeTabInfo) {
        selectTabInUI(response.activeTabInfo.id);
      }
    }
  });

  btnToggle.addEventListener("click", async () => {
    const token = tokenInput.value.trim();
    if (!token) {
      alert("Please paste the Session Auth Token from er-audio-tool Settings/Browser tab.");
      return;
    }
    await chrome.storage.local.set({ sessionToken: token });

    chrome.runtime.sendMessage({ action: "GET_STATE" }, async (res) => {
      if (res && res.isRecording) {
        chrome.runtime.sendMessage({ action: "STOP_CAPTURE" }, () => setRecordingUI(false));
      } else {
        if (!selectedTabId) {
          alert("Please select a browser tab to capture from the list.");
          return;
        }
        const targetTab = availableTabs.find(t => t.id === selectedTabId);
        
        // TabCapture API requires tab to be active or focused in some Chromium versions
        if (targetTab && !targetTab.active) {
          await chrome.tabs.update(selectedTabId, { active: true });
        }

        chrome.runtime.sendMessage({
          action: "START_CAPTURE",
          tabInfo: targetTab
        }, () => setRecordingUI(true));
      }
    });
  });

  async function refreshTabsList() {
    tabListContainer.innerHTML = '<div style="padding:15px; text-align:center; color:#78909c;">Scanning open tabs...</div>';
    
    try {
      const tabs = await chrome.tabs.query({});
      // Filter out internal system pages (chrome://, edge://, etc.)
      availableTabs = tabs.filter(t => {
        const url = t.url || "";
        return !url.startsWith("chrome://") && 
               !url.startsWith("edge://") && 
               !url.startsWith("chrome-extension://") && 
               !url.startsWith("devtools://") &&
               !url.startsWith("about:");
      });

      if (availableTabs.length === 0) {
        tabListContainer.innerHTML = '<div style="padding:15px; text-align:center; color:#78909c;">No capturable web tabs found.</div>';
        return;
      }

      tabListContainer.innerHTML = "";
      availableTabs.forEach(tab => {
        const item = document.createElement("div");
        item.className = "tab-item" + (tab.id === selectedTabId ? " selected" : "");
        item.dataset.tabId = tab.id;

        const titleDiv = document.createElement("div");
        titleDiv.className = "tab-title";
        titleDiv.textContent = tab.title || "Untitled Tab";

        const metaDiv = document.createElement("div");
        metaDiv.className = "tab-meta";
        const audibleTag = tab.audible ? '<span class="badge-audible">♪ Audible</span>' : '<span>Silent</span>';
        metaDiv.innerHTML = `<span>Window ${tab.windowId}</span> ${audibleTag}`;

        item.appendChild(titleDiv);
        item.appendChild(metaDiv);

        item.addEventListener("click", () => {
          selectTabInUI(tab.id);
        });

        tabListContainer.appendChild(item);
      });

      // If nothing selected yet, select current active tab
      if (!selectedTabId) {
        const activeTab = availableTabs.find(t => t.active);
        if (activeTab) {
          selectTabInUI(activeTab.id);
        }
      }
    } catch (err) {
      tabListContainer.innerHTML = `<div style="padding:15px; text-align:center; color:#ef5350;">Error loading tabs: ${err.message}</div>`;
    }
  }

  function selectTabInUI(tabId) {
    selectedTabId = tabId;
    chrome.storage.local.set({ selectedTabId: tabId });
    document.querySelectorAll(".tab-item").forEach(el => {
      if (parseInt(el.dataset.tabId, 10) === tabId) {
        el.classList.add("selected");
      } else {
        el.classList.remove("selected");
      }
    });

    const chosen = availableTabs.find(t => t.id === tabId);
    if (chosen) {
      chrome.runtime.sendMessage({ action: "TAB_SELECTED", tabInfo: chosen });
    }
  }

  function setRecordingUI(recording) {
    if (recording) {
      btnToggle.textContent = "Stop Tab Capture";
      btnToggle.className = "btn-stop";
      statusBadge.textContent = "Status: Capturing Tab Audio";
      statusBadge.className = "badge badge-rec";
    } else {
      btnToggle.textContent = "Record Selected Tab";
      btnToggle.className = "btn-start";
      statusBadge.textContent = "Status: Ready";
      statusBadge.className = "badge badge-idle";
    }
  }

  // --- Verbindung testen (Connection Diagnostic Test) ---
  const btnTestConnection = document.getElementById("btnTestConnection");
  const diagContainer = document.getElementById("diagContainer");
  const diagStepExtension = document.getElementById("diagStepExtension");
  const diagStepDesktop = document.getElementById("diagStepDesktop");
  const diagStepAuth = document.getElementById("diagStepAuth");
  const diagStepCapture = document.getElementById("diagStepCapture");
  const diagStepTab = document.getElementById("diagStepTab");
  const diagSummary = document.getElementById("diagSummary");

  if (btnTestConnection) {
    btnTestConnection.addEventListener("click", async () => {
      diagContainer.style.display = "block";
      const token = tokenInput.value.trim();

      // Step 1: Extension loaded
      diagStepExtension.innerHTML = "✅ <b>Browser Add-In:</b> Geladen & aktiv (v1.0.0)";
      diagStepExtension.style.color = "#81c784";

      // Step 2 & 3: Desktop reachability & Auth test
      diagStepDesktop.innerHTML = "⏳ <b>Desktop-Anwendung:</b> Verbinde mit 127.0.0.1:58291...";
      diagStepDesktop.style.color = "#ffb74d";
      diagStepAuth.innerHTML = "⏳ <b>Authentifizierung:</b> Warte auf Antwort...";
      diagStepAuth.style.color = "#b0bec5";

      let desktopData = null;
      try {
        const resp = await fetch("http://127.0.0.1:58291/api/test_connection", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-Token": token,
          },
          body: JSON.stringify({ token: token }),
        });

        if (resp.status === 200) {
          desktopData = await resp.json();
          diagStepDesktop.innerHTML = "✅ <b>Desktop-Anwendung:</b> Erreichbar auf Loopback (Port 58291)";
          diagStepDesktop.style.color = "#81c784";

          diagStepAuth.innerHTML = "✅ <b>Authentifizierung:</b> Token verifiziert & Handshake bestätigt";
          diagStepAuth.style.color = "#81c784";
        } else if (resp.status === 401) {
          diagStepDesktop.innerHTML = "✅ <b>Desktop-Anwendung:</b> Erreichbar auf Port 58291";
          diagStepDesktop.style.color = "#81c784";

          diagStepAuth.innerHTML = "❌ <b>Authentifizierung:</b> Ungültiger Token! Bitte Session-Token aus Desktop kopieren.";
          diagStepAuth.style.color = "#ef5350";
        } else {
          diagStepDesktop.innerHTML = `⚠️ <b>Desktop-Anwendung:</b> HTTP Status ${resp.status}`;
          diagStepDesktop.style.color = "#ffa726";
        }
      } catch (err) {
        diagStepDesktop.innerHTML = "❌ <b>Desktop-Anwendung:</b> Nicht erreichbar (Ist er-audio-tool gestartet?)";
        diagStepDesktop.style.color = "#ef5350";
        diagStepAuth.innerHTML = "❌ <b>Authentifizierung:</b> Verbindung verweigert (ECONNREFUSED)";
        diagStepAuth.style.color = "#ef5350";
      }

      // Step 4: TabCapture API availability
      if (chrome && chrome.tabCapture && typeof chrome.tabCapture.capture === "function") {
        diagStepCapture.innerHTML = "✅ <b>Browser Audio Capture:</b> tabCapture API verfügbar";
        diagStepCapture.style.color = "#81c784";
      } else {
        diagStepCapture.innerHTML = "❌ <b>Browser Audio Capture:</b> tabCapture API nicht verfügbar";
        diagStepCapture.style.color = "#ef5350";
      }

      // Step 5: Target tab ready
      if (selectedTabId) {
        const chosen = availableTabs.find(t => t.id === selectedTabId);
        const titleStr = chosen ? (chosen.title || "Tab " + chosen.id).substring(0, 30) : "ID: " + selectedTabId;
        diagStepTab.innerHTML = `✅ <b>Ausgewählter Tab:</b> ${titleStr}`;
        diagStepTab.style.color = "#81c784";

        // Also notify desktop server immediately if authenticated
        if (desktopData && desktopData.authenticated) {
          try {
            await fetch("http://127.0.0.1:58291/api/tab_selected", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ token: token, tabInfo: chosen }),
            });
          } catch (e) {}
        }
      } else {
        diagStepTab.innerHTML = "⚠️ <b>Ausgewählter Tab:</b> Keiner ausgewählt. Bitte unten anklicken.";
        diagStepTab.style.color = "#ffa726";
      }

      // Summary
      if (desktopData && desktopData.authenticated && selectedTabId) {
        diagSummary.innerHTML = "✨ <b>Status:</b> Alles betriebsbereit! Aufnahme kann gestartet werden.";
        diagSummary.style.color = "#4db6ac";
      } else if (!desktopData || !desktopData.authenticated) {
        diagSummary.innerHTML = "ℹ️ <b>Hinweis:</b> Bitte sicherstellen, dass er-audio-tool läuft und der richtige Token eingetragen ist.";
        diagSummary.style.color = "#ffb74d";
      } else {
        diagSummary.innerHTML = "ℹ️ <b>Hinweis:</b> Wähle noch einen Tab aus der Liste aus.";
        diagSummary.style.color = "#ffb74d";
      }
    });
  }
});
