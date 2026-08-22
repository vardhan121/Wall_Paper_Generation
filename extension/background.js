const API = "http://127.0.0.1:8765";
const FLUSH_MS = 15000;
const MAX_BATCH = 50;

let active = null;
let timer = null;
let queue = [];

function domainOf(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function safeEvent(tab, startedAt, durationSeconds) {
  if (!tab || !tab.url) return null;

  const url = tab.url;
  const blocked =
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("edge://") ||
    url.startsWith("about:");

  if (blocked) return null;

  return {
    url: url.split("?")[0].split("#")[0],
    domain: domainOf(url),
    title: (tab.title || "").slice(0, 1000),
    started_at: startedAt,
    duration_seconds: Math.max(0, Math.round(durationSeconds))
  };
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({
    active: true,
    lastFocusedWindow: true
  });
  return tabs[0] || null;
}

async function startTracking(tab) {
  if (!tab) return;
  active = {
    tabId: tab.id,
    startedAt: Date.now(),
    tabSnapshot: {
      id: tab.id,
      url: tab.url,
      title: tab.title
    }
  };
}

async function stopTracking() {
  if (!active) return;

  const duration = (Date.now() - active.startedAt) / 1000;
  const event = safeEvent(
    active.tabSnapshot,
    active.startedAt / 1000,
    duration
  );

  if (event && event.duration_seconds >= 2) {
    queue.push(event);
  }

  active = null;

  if (queue.length >= MAX_BATCH) {
    await flush();
  }
}

async function flush() {
  if (!queue.length) return;

  const batch = queue.splice(0, MAX_BATCH);

  try {
    const response = await fetch(`${API}/api/activity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch (err) {
    // Put the events back so a temporary backend restart doesn't lose them.
    queue = batch.concat(queue).slice(-200);
    console.warn("Memory Wallpaper backend unavailable:", err);
  }
}

async function refresh() {
  await stopTracking();
  const tab = await getActiveTab();
  await startTracking(tab);
}

chrome.tabs.onActivated.addListener(() => refresh());

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (active && active.tabId === tabId && (changeInfo.url || changeInfo.title)) {
    refresh();
  }
});

chrome.windows.onFocusChanged.addListener(() => refresh());

chrome.idle.onStateChanged.addListener(async (state) => {
  if (state === "active") {
    await refresh();
  } else {
    await stopTracking();
    await flush();
  }
});

chrome.runtime.onStartup.addListener(async () => {
  await refresh();
});

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({
    enabled: true,
    installedAt: Date.now()
  });
  await refresh();
});

timer = setInterval(async () => {
  await stopTracking();
  const tab = await getActiveTab();
  await startTracking(tab);
  await flush();
}, FLUSH_MS);
