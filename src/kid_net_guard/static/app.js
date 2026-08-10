/**
 * kid-net-guard PWA — Mobile console logic.
 * Vanilla JS, no framework, no build step.
 */

const API = '/api';

// ── Service Config ────────────────────────────────────

const SERVICE_META = {
  youtube:   { icon: '▶️', label: 'YouTube',   color: 'coral' },
  roblox:    { icon: '🧱', label: 'Roblox',    color: 'coral' },
  minecraft: { icon: '⛏️', label: 'Minecraft', color: 'mint' },
  fortnite:  { icon: '🎯', label: 'Fortnite',  color: 'sky' },
  tiktok:    { icon: '🎵', label: 'TikTok',    color: 'rose' },
  discord:   { icon: '💬', label: 'Discord',   color: 'lavender' },
  netflix:   { icon: '🎬', label: 'Netflix',   color: 'coral' },
  whatsapp:  { icon: '💬', label: 'WhatsApp',  color: 'mint' },
  twitch:    { icon: '🎮', label: 'Twitch',    color: 'lavender' },
  snapchat:  { icon: '👻', label: 'Snapchat',  color: 'sunset' },
  instagram: { icon: '📷', label: 'Instagram', color: 'rose' },
  facebook:  { icon: '📘', label: 'Facebook',  color: 'sky' },
  steam:     { icon: '🎮', label: 'Steam',     color: 'sky' },
  epic_games:{ icon: '🎮', label: 'Epic',      color: 'sky' },
  spotify:   { icon: '🎵', label: 'Spotify',   color: 'mint' },
};

const SHOW_SERVICES = ['youtube', 'roblox', 'minecraft', 'fortnite', 'tiktok', 'discord', 'netflix', 'whatsapp'];

// ── Toast ─────────────────────────────────────────────

let toastTimer;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2000);
}

// ── Render ─────────────────────────────────────────────

async function loadDevices() {
  const container = document.getElementById('devices');

  try {
    const r = await fetch(`${API}/devices`);
    const data = await r.json();
    if (!data.devices || data.devices.length === 0) {
      container.innerHTML = '<div class="loading-state">No devices configured</div>';
      return;
    }

    container.innerHTML = data.devices.map(dev => `
      <div class="device-card">
        <div class="device-top">
          <div class="device-avatar">📱</div>
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
    container.innerHTML = '<div class="loading-state" style="color:var(--accent-coral)">Could not load — is AdGuard running?</div>';
  }
}

function renderToggles(dev) {
  return SHOW_SERVICES.map(svc => {
    const meta = SERVICE_META[svc] || { icon: '🌐', label: svc };
    const blocked = dev.services[svc];
    const cls = blocked ? 'blocked' : 'allowed';
    const stateLabel = blocked ? 'BLOCKED' : 'ALLOWED';
    return `
      <button class="toggle ${cls}" data-service="${svc}"
              onclick="toggleService('${esc(dev.id)}', '${esc(svc)}', ${!blocked})"
              id="btn-${esc(dev.id)}-${esc(svc)}">
        <span class="icon">${meta.icon}</span>
        <span class="label">${meta.label}</span>
        <span class="state">${stateLabel}</span>
      </button>
    `;
  }).join('');
}

// ── Toggle ─────────────────────────────────────────────

async function toggleService(deviceId, service, toBlock) {
  const btn = document.getElementById(`btn-${deviceId}-${service}`);
  if (!btn) return;
  btn.classList.add('loading');

  const meta = SERVICE_META[service];
  const label = meta ? meta.label : service;

  try {
    const action = toBlock ? 'block' : 'unblock';
    await fetch(`${API}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, service, action }),
    });
    showToast(`${toBlock ? '🚫' : '✅'} ${label} ${toBlock ? 'blocked' : 'allowed'}`);
    await loadDevices();
  } catch (err) {
    btn.classList.remove('loading');
    showToast('⚠️ Toggle failed');
    console.error('Toggle failed:', err);
  }
}

// ── Pause All ──────────────────────────────────────────

let paused = false;
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
    if (paused) {
      btn.textContent = '▶️  Resume All Internet';
      btn.classList.add('paused');
      showToast('⏸️ All internet paused');
    } else {
      btn.textContent = '⏸️  Pause All Internet';
      btn.classList.remove('paused');
      showToast('✅ Internet resumed');
    }
  } catch (err) {
    showToast('⚠️ Pause failed');
    console.error('Pause failed:', err);
  } finally {
    btn.disabled = false;
  }
}

// ── Status ─────────────────────────────────────────────

async function checkStatus() {
  try {
    const r = await fetch(`${API}/status`);
    const s = await r.json();
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (s.adguard_connected) {
      dot.className = 'status-dot';
      text.textContent = 'Connected';
    } else {
      dot.className = 'status-dot err';
      text.textContent = 'Offline';
    }
  } catch (e) {
    // ignore
  }
}

// ── Helpers ────────────────────────────────────────────

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Init ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadDevices();
  checkStatus();
  setInterval(loadDevices, 30000);
  setInterval(checkStatus, 30000);
});
