let baseUrl = "";
let pollInterval = null;
let currentPhase = "None";
let queueModes = {};
let selectedChampId = 0;
let activeSpellSlot = 1; // 1 or 2
let configData = {};
let searchFilter = "";
let pickableChampions = [];
let currentActionType = "pick"; // "pick" or "ban"

const UI = {
  screens: {
    connect: document.getElementById("connect-screen"),
    dashboard: document.getElementById("dashboard-screen")
  },
  inputs: {
    ip: document.getElementById("ip-input")
  },
  buttons: {
    connect: document.getElementById("btn-connect"),
    disconnect: document.getElementById("btn-disconnect"),
    launch: document.getElementById("btn-launch"),
    queue: document.getElementById("btn-queue")
  },
  display: {
    error: document.getElementById("connect-error"),
    phase: document.getElementById("phase-display"),
    queueMode: document.getElementById("queue-mode-display"),
    statusIcon: document.getElementById("connection-status"),
    summonerName: document.getElementById("summoner-name"),
    summonerIcon: document.getElementById("summoner-icon")
  },
  tabs: {
    home: document.getElementById("tab-home"),
    draft: document.getElementById("tab-draft"),
    settings: document.getElementById("tab-settings")
  },
  nav: {
    home: document.getElementById("nav-btn-home"),
    draft: document.getElementById("nav-btn-draft"),
    settings: document.getElementById("nav-btn-settings")
  },
  lobby: {
    active: document.getElementById("lobby-active"),
    inactive: document.getElementById("lobby-inactive"),
    queueMode: document.getElementById("lobby-queue-mode"),
    membersCount: document.getElementById("lobby-members-count"),
    membersList: document.getElementById("lobby-members-list"),
    invite: document.getElementById("btn-lobby-invite"),
    leave: document.getElementById("btn-lobby-leave"),
    selectMode: document.getElementById("select-queue-mode"),
    create: document.getElementById("btn-create-lobby")
  },
  logs: {
    container: document.getElementById("log-container")
  },
  ready: {
    overlay: document.getElementById("ready-check-overlay"),
    accept: document.getElementById("btn-ready-accept"),
    decline: document.getElementById("btn-ready-decline")
  },
  draft: {
    active: document.getElementById("draft-active-view"),
    inactive: document.getElementById("draft-inactive-view"),
    badge: document.getElementById("draft-badge"),
    phaseTitle: document.getElementById("draft-phase-title"),
    phaseSub: document.getElementById("draft-phase-sub"),
    timer: document.getElementById("draft-timer"),
    timerBar: document.getElementById("draft-timer-bar"),
    benchSection: document.getElementById("bench-section"),
    benchList: document.getElementById("bench-list"),
    reroll: document.getElementById("btn-draft-reroll"),
    rerollCount: document.getElementById("reroll-count"),
    spellsList: document.getElementById("spells-list"),
    search: document.getElementById("draft-search"),
    clearSearch: document.getElementById("btn-clear-search"),
    champGrid: document.getElementById("champion-grid"),
    lockIn: document.getElementById("btn-lock-in"),
    teamList: document.getElementById("draft-team-list")
  },
  config: {
    autoAccept: document.getElementById("cfg-auto-accept"),
    autoLock: document.getElementById("cfg-auto-lock"),
    autoRunes: document.getElementById("cfg-auto-runes"),
    autoHonor: document.getElementById("cfg-auto-honor"),
    skipStats: document.getElementById("cfg-skip-stats"),
    autoHover: document.getElementById("cfg-auto-hover"),
    arenaLock: document.getElementById("cfg-arena-lock"),
    arenaSynergy: document.getElementById("cfg-arena-synergy"),
    acceptDelay: document.getElementById("cfg-accept-delay"),
    acceptDelayVal: document.getElementById("accept-delay-val")
  }
};

const spellsList = [
  { id: 4, name: "Flash", icon: "⚡" },
  { id: 14, name: "Ignite", icon: "🔥" },
  { id: 11, name: "Smite", icon: "⚔️" },
  { id: 7, name: "Heal", icon: "💚" },
  { id: 12, name: "Teleport", icon: "🌀" },
  { id: 6, name: "Ghost", icon: "👻" },
  { id: 3, name: "Exhaust", icon: "💤" },
  { id: 21, name: "Barrier", icon: "🛡️" },
  { id: 1, name: "Cleanse", icon: "🧼" },
  { id: 32, name: "Mark", icon: "❄️" }
];

// Helper to log actions in UI log panel
function addLog(msg) {
  const time = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerText = `[${time}] ${msg}`;
  if (UI.logs.container) {
    UI.logs.container.appendChild(entry);
    UI.logs.container.scrollTop = UI.logs.container.scrollHeight;
    while (UI.logs.container.childNodes.length > 50) {
      UI.logs.container.removeChild(UI.logs.container.firstChild);
    }
  }
}

// Switching view tabs (Home, Draft, Settings)
function switchTab(name) {
  Object.keys(UI.tabs).forEach(k => {
    if (UI.tabs[k]) UI.tabs[k].classList.remove("active");
    if (UI.nav[k]) UI.nav[k].classList.remove("active");
  });
  if (UI.tabs[name]) UI.tabs[name].classList.add("active");
  if (UI.nav[name]) UI.nav[name].classList.add("active");
  addLog(`Switched to: ${name.toUpperCase()}`);
}

Object.keys(UI.tabs).forEach(k => {
  if (UI.nav[k]) {
    UI.nav[k].addEventListener("click", () => switchTab(k));
  }
});

// Setup Connect & Disconnect handlers
window.addEventListener('DOMContentLoaded', () => {
    const savedIp = localStorage.getItem("leagueloop_ip");
    if (savedIp) {
        UI.inputs.ip.value = savedIp;
    }
});

UI.buttons.connect.addEventListener("click", async () => {
  const ip = UI.inputs.ip.value.trim() || "127.0.0.1";
  baseUrl = `http://${ip}:8337`;
  
  try {
    const res = await fetch(`${baseUrl}/status`);
    if (res.ok) {
      localStorage.setItem("leagueloop_ip", ip);
      UI.display.error.classList.add("hidden");
      switchScreen("dashboard");
      addLog(`Linked to http://${ip}:8337`);
      await initData();
      startPolling();
    } else {
      throw new Error("HTTP Error");
    }
  } catch (err) {
    UI.display.error.classList.remove("hidden");
    console.error(err);
  }
});

UI.buttons.disconnect.addEventListener("click", () => {
  stopPolling();
  switchScreen("connect");
  addLog("Disconnected.");
});

function switchScreen(name) {
  Object.values(UI.screens).forEach(s => {
    if (s) s.classList.add("hidden");
  });
  if (UI.screens[name]) {
    UI.screens[name].classList.remove("hidden");
  }
}

// Initial remote payload setup
async function initData() {
  try {
    const qRes = await fetch(`${baseUrl}/queue-modes`);
    if (qRes.ok) {
      const qData = await qRes.json();
      queueModes = qData.modes;
      if (UI.lobby.selectMode) {
        UI.lobby.selectMode.innerHTML = Object.keys(queueModes).map(m => `
          <option value="${m}">${m}</option>
        `).join("");
      }
    }

    const cRes = await fetch(`${baseUrl}/config`);
    if (cRes.ok) {
      configData = await cRes.json();
      updateConfigUI();
    }
  } catch (err) {
    console.error("Failed to initialize API data", err);
  }
}

// Update settings UI from remote configurations
function updateConfigUI() {
  if (UI.config.autoAccept) UI.config.autoAccept.checked = configData.auto_accept || false;
  if (UI.config.autoLock) UI.config.autoLock.checked = configData.auto_lock_in || false;
  if (UI.config.autoRunes) UI.config.autoRunes.checked = configData.auto_runes_enabled || false;
  if (UI.config.autoHonor) UI.config.autoHonor.checked = configData.auto_honor_enabled || false;
  if (UI.config.skipStats) UI.config.skipStats.checked = configData.skip_stats_enabled || false;
  if (UI.config.autoHover) UI.config.autoHover.checked = configData.auto_hover || false;
  if (UI.config.arenaLock) UI.config.arenaLock.checked = configData.arena_auto_lock || false;
  if (UI.config.arenaSynergy) UI.config.arenaSynergy.checked = configData.arena_synergy_enabled || false;
  
  if (UI.config.acceptDelay) {
    UI.config.acceptDelay.value = configData.accept_delay || 0;
    if (UI.config.acceptDelayVal) {
      UI.config.acceptDelayVal.innerText = `${parseFloat(UI.config.acceptDelay.value).toFixed(1)}s`;
    }
  }
}

// Post config updates to desktop backend
async function saveConfig(key, value) {
  try {
    const res = await fetch(`${baseUrl}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value })
    });
    if (res.ok) {
      configData[key] = value;
      addLog(`Config updated: ${key} = ${value}`);
    }
  } catch (err) {
    console.error("Failed to save config", err);
  }
}

const configMappings = {
  "cfg-auto-accept": { key: "auto_accept" },
  "cfg-auto-lock": { key: "auto_lock_in" },
  "cfg-auto-runes": { key: "auto_runes_enabled" },
  "cfg-auto-honor": { key: "auto_honor_enabled" },
  "cfg-skip-stats": { key: "skip_stats_enabled" },
  "cfg-auto-hover": { key: "auto_hover" },
  "cfg-arena-lock": { key: "arena_auto_lock" },
  "cfg-arena-synergy": { key: "arena_synergy_enabled" }
};

Object.keys(configMappings).forEach(id => {
  const mapping = configMappings[id];
  const element = document.getElementById(id);
  if (element) {
    element.addEventListener("change", () => {
      saveConfig(mapping.key, element.checked);
    });
  }
});

if (UI.config.acceptDelay) {
  UI.config.acceptDelay.addEventListener("input", () => {
    if (UI.config.acceptDelayVal) {
      UI.config.acceptDelayVal.innerText = `${parseFloat(UI.config.acceptDelay.value).toFixed(1)}s`;
    }
  });
  UI.config.acceptDelay.addEventListener("change", () => {
    saveConfig("accept_delay", parseFloat(UI.config.acceptDelay.value));
  });
}

// Action Dispatcher
async function sendAction(actionStr, payload = {}) {
  try {
    const res = await fetch(`${baseUrl}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: actionStr, ...payload })
    });
    if (res.ok) {
      addLog(`Executed: ${actionStr}`);
    }
  } catch (err) {
    console.error("Action failed", err);
  }
}

UI.buttons.launch.addEventListener("click", () => sendAction("launch_client"));
UI.buttons.queue.addEventListener("click", () => {
  if (currentPhase === "Matchmaking") {
    sendAction("cancel_matchmaking");
  } else {
    sendAction("find_match");
  }
});

if (UI.lobby.create) {
  UI.lobby.create.addEventListener("click", () => {
    const mode = UI.lobby.selectMode.value;
    sendAction("create_lobby", { queue_mode: mode });
  });
}
if (UI.lobby.leave) {
  UI.lobby.leave.addEventListener("click", () => sendAction("leave_lobby"));
}
if (UI.lobby.invite) {
  UI.lobby.invite.addEventListener("click", () => sendAction("mass_invite"));
}

UI.ready.accept.addEventListener("click", () => {
  fetch(`${baseUrl}/ready-check/accept`, { method: "POST" });
  UI.ready.overlay.classList.add("hidden");
  addLog("Remotely Accepted Match!");
});
UI.ready.decline.addEventListener("click", () => {
  fetch(`${baseUrl}/ready-check/decline`, { method: "POST" });
  UI.ready.overlay.classList.add("hidden");
  addLog("Remotely Declined Match.");
});

// Draft Search and Filtering
if (UI.draft.search) {
  UI.draft.search.addEventListener("input", (e) => {
    searchFilter = e.target.value.toLowerCase().trim();
    renderChampionGrid();
  });
}
if (UI.draft.clearSearch) {
  UI.draft.clearSearch.addEventListener("click", () => {
    UI.draft.search.value = "";
    searchFilter = "";
    renderChampionGrid();
  });
}

function renderChampionGrid() {
  if (!UI.draft.champGrid) return;
  const filtered = pickableChampions.filter(c => c.name.toLowerCase().includes(searchFilter));
  if (filtered.length === 0) {
    UI.draft.champGrid.innerHTML = `<div style="grid-column: 1 / span 4; text-align: center; color: var(--text-muted); padding: 20px;">No champions match search</div>`;
    return;
  }

  UI.draft.champGrid.innerHTML = filtered.map(c => `
    <div class="champ-card ${selectedChampId === c.id ? 'selected' : ''}" data-id="${c.id}">
      <div class="champ-card-initial">${c.name.charAt(0)}</div>
      <span>${c.name}</span>
    </div>
  `).join("");

  UI.draft.champGrid.querySelectorAll(".champ-card").forEach(card => {
    card.addEventListener("click", async () => {
      const cId = parseInt(card.dataset.id);
      selectedChampId = cId;
      renderChampionGrid();

      // Trigger automatic hover picks/bans in real-time
      const endpointType = (currentActionType === "ban") ? "ban" : "pick";
      try {
        await fetch(`${baseUrl}/champ-select/${endpointType}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ championId: cId })
        });
        addLog(`Hovering ${getChampNameFromList(cId)}`);
      } catch (err) {
        console.error("Failed to hover champion selection", err);
      }
    });
  });
}

function getChampNameFromList(id) {
  const found = pickableChampions.find(c => c.id === id);
  return found ? found.name : `Champion #${id}`;
}

if (UI.draft.lockIn) {
  UI.draft.lockIn.addEventListener("click", async () => {
    if (selectedChampId === 0) return;
    try {
      const res = await fetch(`${baseUrl}/champ-select/lock`, { method: "POST" });
      if (res.ok) {
        addLog("Locked in Selection!");
        selectedChampId = 0;
      }
    } catch (err) {
      console.error("Lock in failed", err);
    }
  });
}

// Summoner Spells Selection Panel
function renderSpells(myRosterItem) {
  if (!UI.draft.spellsList) return;
  const s1Id = myRosterItem ? myRosterItem.spell1Id : 4;
  const s2Id = myRosterItem ? myRosterItem.spell2Id : 14;

  let html = `
    <div class="spell-slots-row" style="display: flex; gap: 12px; margin-bottom: 12px; grid-column: 1 / span 5; justify-content: center; width: 100%;">
      <div id="spell-slot-1" class="spell-slot-indicator ${activeSpellSlot === 1 ? 'active' : ''}" style="padding: 6px 12px; border: 2px solid ${activeSpellSlot === 1 ? 'var(--accent-hextech)' : 'rgba(255,255,255,0.08)'}; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 700; color: ${activeSpellSlot === 1 ? 'var(--accent-hextech)' : '#fff'}">
        Slot 1: ${getSpellName(s1Id)}
      </div>
      <div id="spell-slot-2" class="spell-slot-indicator ${activeSpellSlot === 2 ? 'active' : ''}" style="padding: 6px 12px; border: 2px solid ${activeSpellSlot === 2 ? 'var(--accent-hextech)' : 'rgba(255,255,255,0.08)'}; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 700; color: ${activeSpellSlot === 2 ? 'var(--accent-hextech)' : '#fff'}">
        Slot 2: ${getSpellName(s2Id)}
      </div>
    </div>
  `;

  spellsList.forEach(s => {
    const isActive = (s.id === s1Id || s.id === s2Id);
    html += `
      <button class="spell-btn ${isActive ? 'active' : ''}" data-id="${s.id}">
        <span style="font-size: 1.5rem;">${s.icon}</span>
        <span style="font-size: 0.65rem; margin-top: 4px;">${s.name}</span>
      </button>
    `;
  });

  UI.draft.spellsList.innerHTML = html;

  // Bind active spell slot triggers
  document.getElementById("spell-slot-1").addEventListener("click", () => {
    activeSpellSlot = 1;
    renderSpells(myRosterItem);
  });
  document.getElementById("spell-slot-2").addEventListener("click", () => {
    activeSpellSlot = 2;
    renderSpells(myRosterItem);
  });

  UI.draft.spellsList.querySelectorAll(".spell-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const sId = parseInt(btn.dataset.id);
      const payload = {};
      if (activeSpellSlot === 1) {
        if (sId === s2Id) return; // Prevent equipping duplicate summoners
        payload.spell1Id = sId;
      } else {
        if (sId === s1Id) return; // Prevent equipping duplicate summoners
        payload.spell2Id = sId;
      }

      try {
        const res = await fetch(`${baseUrl}/champ-select/spells`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          addLog(`Spell updated to ${getSpellName(sId)} in Slot ${activeSpellSlot}`);
          activeSpellSlot = (activeSpellSlot === 1) ? 2 : 1; // Auto-advance to next slot
        }
      } catch (err) {
        console.error("Spell equip failed", err);
      }
    });
  });
}

function getSpellName(id) {
  const found = spellsList.find(s => s.id === id);
  return found ? found.name : `Spell #${id}`;
}

// Adaptive state monitoring loops
function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  fetchStatus(); 
  pollInterval = setInterval(fetchStatus, 2000);
}

function stopPolling() {
  if (pollInterval) clearInterval(pollInterval);
}

function adjustPollingInterval(phase) {
  let interval = 2000;
  if (phase === "ReadyCheck" || phase === "ChampSelect") {
    interval = 500; // Fast 500ms loops during time-sensitive screens
  } else if (phase === "InProgress") {
    interval = 4000; // Slower 4s loops during passive in-game states
  } else {
    interval = 1500; // Standard 1.5s check loops for lobbies
  }

  stopPolling();
  pollInterval = setInterval(fetchStatus, interval);
  addLog(`Polling adjusted to ${interval}ms (${phase})`);
}

async function fetchStatus() {
  try {
    const res = await fetch(`${baseUrl}/status`);
    if (!res.ok) throw new Error("Offline");
    
    const data = await res.json();
    const phase = data.phase || "None";
    
    // Check for phase transitions
    if (phase !== currentPhase) {
      currentPhase = phase;
      adjustPollingInterval(phase);
    }
    
    // Render Summoner Card
    if (data.summoner) {
      if (UI.display.summonerName) UI.display.summonerName.innerText = data.summoner.summoner_name;
      const rankText = data.summoner.tier !== "UNRANKED" 
        ? `${data.summoner.tier} ${data.summoner.rank} (${data.summoner.lp} LP)` 
        : `Level ${data.summoner.level}`;
      if (UI.display.statusIcon) UI.display.statusIcon.innerText = `● ${rankText}`;
      
      const sIconId = data.summoner.profile_icon_id || 1;
      if (UI.display.summonerIcon) {
        UI.display.summonerIcon.innerHTML = `<img src="https://ddragon.leagueoflegends.com/cdn/14.1.1/img/profileicon/${sIconId}.png" style="width: 100%; height: 100%; border-radius: 50%; border: 1.5px solid var(--accent-hextech);" />`;
      }
    } else {
      if (UI.display.summonerName) UI.display.summonerName.innerText = "LEAGUELOOP";
      if (UI.display.statusIcon) UI.display.statusIcon.innerText = "● LINKED";
      if (UI.display.summonerIcon) UI.display.summonerIcon.innerHTML = "👤";
    }

    // Update Home tab UI
    if (UI.display.phase) UI.display.phase.innerText = formatPhase(phase);
    
    if (phase === "Matchmaking") {
      const min = Math.floor(data.queue_timer / 60);
      const sec = data.queue_timer % 60;
      const secStr = sec < 10 ? `0${sec}` : sec;
      if (UI.display.queueMode) UI.display.queueMode.innerText = `Queueing: ${min}:${secStr}`;
      document.getElementById("queue-btn-text").innerText = "Cancel Queue";
    } else {
      if (UI.display.queueMode) UI.display.queueMode.innerText = `Mode: ${data.queue_mode || "None"}`;
      document.getElementById("queue-btn-text").innerText = "Enter Queue";
    }

    // Ready Check Overlay
    if (phase === "ReadyCheck") {
      if (UI.ready.overlay) UI.ready.overlay.classList.remove("hidden");
    } else {
      if (UI.ready.overlay) UI.ready.overlay.classList.add("hidden");
    }

    // Lobby panel state management
    if (data.lobby) {
      if (UI.lobby.active) UI.lobby.active.classList.remove("hidden");
      if (UI.lobby.inactive) UI.lobby.inactive.classList.add("hidden");
      
      const qModeStr = Object.keys(queueModes).find(k => queueModes[k] === data.lobby.queueId) || "Custom Lobby";
      if (UI.lobby.queueMode) UI.lobby.queueMode.innerText = qModeStr;
      if (UI.lobby.membersCount) UI.lobby.membersCount.innerText = `${data.lobby.members.length}/5 Players`;
      
      if (UI.lobby.membersList) {
        UI.lobby.membersList.innerHTML = data.lobby.members.map(m => `
          <div class="member-card">
            <div class="member-info">
              <div class="member-status-dot"></div>
              <span class="member-name">${m.summonerName}</span>
              ${m.isLeader ? `<span class="member-role">Leader</span>` : ''}
            </div>
            <div style="font-size: 0.72rem; color: var(--text-muted); display: flex; gap: 6px;">
              <span>${m.position1}</span>
              <span>${m.position2}</span>
            </div>
          </div>
        `).join("");
      }
    } else {
      if (UI.lobby.active) UI.lobby.active.classList.add("hidden");
      if (UI.lobby.inactive) UI.lobby.inactive.classList.remove("hidden");
    }

    // Champ Select Polling and Panels
    if (phase === "ChampSelect") {
      await fetchChampSelectStatus();
    } else {
      if (UI.draft.active) UI.draft.active.classList.add("hidden");
      if (UI.draft.inactive) UI.draft.inactive.classList.remove("hidden");
      if (UI.draft.badge) UI.draft.badge.classList.add("hidden");
    }

  } catch (err) {
    if (UI.display.phase) UI.display.phase.innerText = "Disconnected";
    if (UI.display.statusIcon) {
      UI.display.statusIcon.style.color = "var(--error)";
      UI.display.statusIcon.innerText = "● Offline";
    }
  }
}

// Fetch details for the active draft session
async function fetchChampSelectStatus() {
  try {
    const csRes = await fetch(`${baseUrl}/champ-select`);
    if (!csRes.ok) return;

    const data = await csRes.json();
    if (data.active) {
      if (UI.draft.active) UI.draft.active.classList.remove("hidden");
      if (UI.draft.inactive) UI.draft.inactive.classList.add("hidden");
      if (UI.draft.badge) UI.draft.badge.classList.remove("hidden");

      // Progress bars and timer
      if (UI.draft.timer) UI.draft.timer.innerText = data.timer;
      if (UI.draft.timerBar) {
        const pct = Math.max(0, Math.min(100, (data.timer / 30) * 100));
        UI.draft.timerBar.style.width = `${pct}%`;
      }

      currentActionType = data.phase || "pick";
      if (UI.draft.phaseTitle) UI.draft.phaseTitle.innerText = `${currentActionType.toUpperCase()} PHASE`;
      
      const isMyTurn = data.currentAction ? data.currentAction.isMyTurn : false;
      if (UI.draft.phaseSub) {
        UI.draft.phaseSub.innerText = isMyTurn ? "YOUR TURN" : "Waiting for other players...";
        UI.draft.phaseSub.style.color = isMyTurn ? "var(--accent-hextech)" : "var(--text-muted)";
      }

      if (UI.draft.lockIn) {
        UI.draft.lockIn.disabled = !isMyTurn || selectedChampId === 0;
        if (isMyTurn && selectedChampId > 0) {
          UI.draft.lockIn.classList.add("glow");
        } else {
          UI.draft.lockIn.classList.remove("glow");
        }
      }

      // Bench (ARAM swaps)
      if (data.benchChampions && data.benchChampions.length > 0) {
        if (UI.draft.benchSection) UI.draft.benchSection.classList.remove("hidden");
        if (UI.draft.benchList) {
          UI.draft.benchList.innerHTML = data.benchChampions.map(b => `
            <button class="bench-btn" style="padding: 8px 12px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; color: #fff; font-size: 0.8rem; font-weight: 600; cursor: pointer; display: inline-block;" data-id="${b.championId}">
              ${b.championName}
            </button>
          `).join("");
          
          UI.draft.benchList.querySelectorAll(".bench-btn").forEach(btn => {
            btn.addEventListener("click", () => {
              const cid = parseInt(btn.dataset.id);
              fetch(`${baseUrl}/champ-select/bench-swap`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ championId: cid })
              });
              addLog(`Swapped bench: ${btn.innerText.trim()}`);
            });
          });
        }
        
        if (UI.draft.reroll) UI.draft.reroll.classList.remove("hidden");
        if (UI.draft.rerollCount) UI.draft.rerollCount.innerText = data.rerollsRemaining || 0;
      } else {
        if (UI.draft.benchSection) UI.draft.benchSection.classList.add("hidden");
        if (UI.draft.reroll) UI.draft.reroll.classList.add("hidden");
      }

      // Render Spells
      const me = data.myTeam.find(t => t.cellId === data.localCellId);
      renderSpells(me);

      // Render Team list
      if (UI.draft.teamList) {
        UI.draft.teamList.innerHTML = data.myTeam.map(t => {
          const isLocal = (t.cellId === data.localCellId);
          return `
            <div class="team-member" style="border: 1px solid ${isLocal ? 'var(--accent-hextech)' : 'rgba(255,255,255,0.04)'}; background: ${isLocal ? 'rgba(200, 170, 110, 0.05)' : 'rgba(0,0,0,0.2)'}">
              <div class="team-member-info">
                <span class="team-member-champ">${t.championName || t.assignedPosition || 'Selecting...'}</span>
                <span class="team-member-pos">${t.assignedPosition || ''}</span>
              </div>
              <span class="team-member-status" style="color: ${t.completed ? 'var(--success)' : 'var(--accent-hextech)'}">
                ${t.completed ? 'Locked' : 'Hovering'}
              </span>
            </div>
          `;
        }).join("");
      }

      // Populate pickable list
      if (data.pickableChampions && data.pickableChampions.length > 0 && pickableChampions.length === 0) {
        pickableChampions = data.pickableChampions;
        renderChampionGrid();
      }
    } else {
      if (UI.draft.active) UI.draft.active.classList.add("hidden");
      if (UI.draft.inactive) UI.draft.inactive.classList.remove("hidden");
      if (UI.draft.badge) UI.draft.badge.classList.add("hidden");
      pickableChampions = []; // Reset champion registry
    }
  } catch (err) {
    console.error("Draft session fetch failed", err);
  }
}

function formatPhase(phase) {
  const map = {
    "None": "Idle",
    "Lobby": "In Lobby",
    "Matchmaking": "In Queue...",
    "ReadyCheck": "Match Found!",
    "ChampSelect": "Champ Select",
    "InProgress": "In Game"
  };
  return map[phase] || phase;
}
