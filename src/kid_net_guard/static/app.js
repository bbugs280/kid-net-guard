/**
 * kid-net-guard PWA — Mobile console logic.
 * Vanilla JS, no framework, no build step.
 */

const API = '/api';

// ── Service Icons ──────────────────────────────────────

const SERVICE_ICONS = {
  youtube: '▶️', netflix: '🎬', tiktok: '🎵', twitch: '🎮',
  discord: '💬', facebook: '📘', snapchat: '👻', roblox: '🧱',
  minecraft: '⛏️', fortnite: '🔫', steam: '🎮', epic_games: '🎮',
  whatsapp: '💬', instagram: '📷', spotify: '🎵',
};

function iconFor(service) {
  return SERVICE_ICONS[service] || '🌐';
}

// ── Render ─────────────────────────────────────────────

async function loadDevices() {
  const container = document.getElementById('devices');
  container.innerHTML = '<div class="schedule-placeholder">Loading...</div>';

  try {
    const r = await fetch(`${API}/devices`);
    const data = await r.json();

    container.innerHTML = data.devices.map(dev => `
      <div class="device-section">
        <div class="device-header">
          <span class="device-icon">📱</span>
          <div>
            <div class="device-name">${esc(dev.name)}</div>
            <div class="device-sub">${esc(dev.subtitle)}</div>
          </div>
        </div>
        <div class="toggles">
          ${renderToggles(dev)}
        </div>
      </div>
    `).join('');

  } catch (err) {
    container.innerHTML = `<div class="schedule-placeholder" style="color:var(--danger)">
      Could not load devices — is AdGuard Home running?
    </div>`;
  }
}

function renderToggles(dev) {
  // Show only the most relevant services
  const show = ['youtube', 'roblox', 'minecraft', 'fortnite', 'tiktok', 'discord', 'netflix', 'whatsapp'];
  return show.map(svc => {
    const blocked = dev.services[svc];
    const cls = blocked ? 'blocked' : 'allowed';
    const state = blocked ? 'BLOCKED' : 'ALLOWED';
    return `
      <button class="toggle ${cls}"
              onclick="toggleService('${esc(dev.id)}', '${esc(svc)}', ${!blocked})"
              id="btn-${esc(dev.id)}-${esc(svc)}">
        <span class="icon">${iconFor(svc)}</span>
        <span class="label">${capitalize(svc)}</span>
        <span class="state">${state}</span>
      </button>
    `;
  }).join('');
}

// ── Toggle ─────────────────────────────────────────────

async function toggleService(deviceId, service, toBlock) {
  const btn = document.getElementById(`btn-${deviceId}-${service}`);
  if (!btn) return;
  btn.classList.add('loading');

  try {
    const action = toBlock ? 'block' : 'unblock';
    await fetch(`${API}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, service, action }),
    });
    // Reload to get fresh state from AdGuard
    await loadDevices();
  } catch (err) {
    btn.classList.remove('loading');
    console.error('Toggle failed:', err);
  }
}

// ── Pause All ──────────────────────────────────────────

let paused = false;
async function pauseAll() {
  const btn = document.getElementById('pause-btn');
  const action = paused ? 'resume' : 'pause';
  btn.textContent = '⏳ ...';
  btn.disabled = true;

  try {
    await fetch(`${API}/pause-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    paused = !paused;
    btn.textContent = paused ? '▶️ Resume All Internet' : '⏸️ Pause All Internet';
    btn.style.borderColor = paused ? 'var(--success)' : 'var(--danger)';
    btn.style.color = paused ? 'var(--success)' : 'var(--danger)';
  } catch (err) {
    console.error('Pause failed:', err);
  } finally {
    btn.disabled = false;
  }
}

// ── Status check ───────────────────────────────────────

async function checkStatus() {
  try {
    const r = await fetch(`${API}/status`);
    const s = await r.json();
    const dot = document.getElementById('status-dot');
    dot.className = 'status-dot ' + (s.adguard_connected ? 'ok' : 'err');
    dot.title = s.adguard_connected ? 'AdGuard connected' : 'AdGuard unreachable';
  } catch (e) {
    // ignore
  }
}

// ── Helpers ────────────────────────────────────────────

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
}

// ── Init ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadDevices();
  checkStatus();
  // Refresh every 30s to stay in sync if another parent toggles
  setInterval(loadDevices, 30000);
  setInterval(checkStatus, 30000);
});
