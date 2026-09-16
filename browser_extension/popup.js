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
});
