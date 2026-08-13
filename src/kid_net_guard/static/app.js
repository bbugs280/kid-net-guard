/**
 * kid-net-guard — Console-style toggle strip.
 * Category-grouped slider toggles. One-thumb operation.
 */

const API = '/api';

// ── Service Catalog ────────────────────────────────────

const CATEGORIES = [
  {
    id: 'games', label: '🎮 Games',
    services: [
      { id: 'roblox',    icon: '🧱', label: 'Roblox' },
      { id: 'minecraft', icon: '⛏️', label: 'Minecraft' },
      { id: 'epic_games',  icon: '🎯', label: 'Fortnite' },
    ]
  },
  {
    id: 'video', label: '▶️ Video',
    services: [
      { id: 'youtube', icon: '▶️', label: 'YouTube' },
      { id: 'netflix', icon: '🎬', label: 'Netflix' },
      { id: 'tiktok',   icon: '🎵', label: 'TikTok' },
      { id: 'twitch',   icon: '🎮', label: 'Twitch' },
    ]
  },
  {
    id: 'social', label: '💬 Social',
    services: [
      { id: 'discord',   icon: '💬', label: 'Discord' },
      { id: 'whatsapp',  icon: '💬', label: 'WhatsApp' },
      { id: 'snapchat',  icon: '👻', label: 'Snapchat' },
      { id: 'instagram', icon: '📷', label: 'Instagram' },
      { id: 'facebook',  icon: '📘', label: 'Facebook' },
    ]
  },
  {
    id: 'other', label: '🎧 Other',
    services: [
      { id: 'steam',  icon: '🎮', label: 'Steam' },
      { id: 'spotify', icon: '🎵', label: 'Spotify' },
    ]
  },
];

// ── State ──────────────────────────────────────────────

let currentDevice = null;
let serviceStates = {};
let paused = false;

// ── Toast ──────────────────────────────────────────────

let toastTimer;
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
}

// ── Render ─────────────────────────────────────────────

async function load() {
  try {
    const r = await fetch(`${API}/devices`);
    const data = await r.json();
    if (!data.devices || data.devices.length === 0) {
      document.getElementById('content').innerHTML =
        '<div style="padding:40px 16px;text-align:center;color:var(--ink-muted);">No devices configured</div>';
      return;
    }
    currentDevice = data.devices[0];
    serviceStates = currentDevice.services || {};
    render();
  } catch (err) {
    document.getElementById('content').innerHTML =
      '<div style="padding:40px 16px;text-align:center;color:var(--red-fg);">Could not connect to AdGuard</div>';
  }
}

function render() {
  let html = '';
  let blockedCount = 0;

  for (const cat of CATEGORIES) {
    html += `<div class="section"><div class="section-header">${cat.label}</div>`;
    for (const svc of cat.services) {
      const blocked = !!serviceStates[svc.id];
      if (blocked) blockedCount++;
      html += `
        <div class="row" id="row-${svc.id}">
          <span class="row-icon">${svc.icon}</span>
          <span class="row-label">${svc.label}</span>
          <div class="slider ${blocked ? '' : 'on'}"
               onclick="toggleService('${svc.id}', ${blocked})"
               id="slider-${svc.id}"></div>
        </div>
      `;
    }
    html += `</div>`;
  }

  document.getElementById('content').innerHTML = html;

  // Update count badge
  const badge = document.getElementById('count-badge');
  if (blockedCount > 0) {
    badge.className = 'count-badge has-blocked';
    badge.textContent = `${blockedCount} blocked`;
  } else {
    badge.className = 'count-badge all-clear';
    badge.textContent = '✓ All clear';
  }
}

// ── Toggle ─────────────────────────────────────────────

async function toggleService(serviceId, currentlyBlocked) {
  const row = document.getElementById(`row-${serviceId}`);
  if (row) row.classList.add('loading');

  try {
    const action = currentlyBlocked ? 'unblock' : 'block';
    await fetch(`${API}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: currentDevice.id,
        service: serviceId,
        action,
      }),
    });

    // Optimistic update
    serviceStates[serviceId] = !currentlyBlocked;
    render();

    const label = findServiceLabel(serviceId);
    toast(currentlyBlocked ? `✅ ${label} allowed` : `🚫 ${label} blocked`);
  } catch (err) {
    if (row) row.classList.remove('loading');
    toast('⚠️ Toggle failed');
    console.error(err);
  }
}

function findServiceLabel(id) {
  for (const cat of CATEGORIES) {
    for (const svc of cat.services) {
      if (svc.id === id) return svc.label;
    }
  }
  return id;
}

// ── Pause All ──────────────────────────────────────────

async function pauseAll() {
  const btn = document.getElementById('pause-btn');
  btn.disabled = true;
  btn.textContent = '⏳ ...';

  try {
    const action = paused ? 'resume' : 'pause';
    await fetch(`${API}/pause-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    paused = !paused;
    btn.textContent = paused ? '▶️  Resume Internet' : '⏸️  Pause All Internet';
    btn.classList.toggle('paused', paused);
    toast(paused ? '⏸️ All internet cut off' : '✅ Internet restored');
  } catch (err) {
    toast('⚠️ Pause failed');
    console.error(err);
  } finally {
    btn.disabled = false;
  }
}

// ── Status ─────────────────────────────────────────────

async function checkStatus() {
  try {
    const r = await fetch(`${API}/status`);
    const s = await r.json();
    const dot = document.getElementById('dot');
    if (s.proxy_connected) {
      dot.className = 'dot';
    } else {
      dot.className = 'dot off';
    }
  } catch (e) {}
}

// ── Init ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  load();
  checkStatus();
  setInterval(load, 30000);
  setInterval(checkStatus, 30000);
});
