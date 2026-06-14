// Shared utilities for Sri Vengamamba PG
const ENV = {
  API_BASE: (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || ''
};
function api(p) { return `${ENV.API_BASE}${p}`; }
function getToken() { return localStorage.getItem('sv_token') || ''; }
function setToken(t) { localStorage.setItem('sv_token', t); }
function getUser() {
  try { return JSON.parse(localStorage.getItem('sv_user') || 'null'); } catch { return null; }
}
function setUser(u) { localStorage.setItem('sv_user', JSON.stringify(u)); }
function logout() { localStorage.clear(); window.location.href = '/index.html'; }

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  const t = getToken();
  if (t) headers['Authorization'] = `Bearer ${t}`;
  const res = await fetch(api(path), { ...opts, headers });
  let data = null; try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `Error ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

function toast(msg, type = 'info') {
  let host = document.querySelector('.toast-host');
  if (!host) { host = document.createElement('div'); host.className = 'toast-host'; document.body.appendChild(host); }
  const el = document.createElement('div');
  el.className = `sv-toast ${type}`;
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function renderNavbar() {
  const u = getUser();
  const nav = document.getElementById('nav-user-area');
  if (!nav) return;
  if (u) {
    const dash = u.role === 'admin' ? '/admin.html' : '/my-bookings.html';
    nav.innerHTML = `
      <li class="nav-item"><a class="nav-link" href="${dash}" data-testid="nav-dashboard">${u.role === 'admin' ? 'Admin' : 'My Bookings'}</a></li>
      <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown" data-testid="nav-user-menu">
          <i class="bi bi-person-circle me-1"></i>${u.name || u.email}
        </a>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><span class="dropdown-item-text small text-muted">${u.email} (${u.role})</span></li>
          <li><hr class="dropdown-divider"></li>
          <li><a class="dropdown-item" href="#" onclick="logout();return false;" data-testid="nav-logout">Logout</a></li>
        </ul>
      </li>`;
  } else {
    nav.innerHTML = `
      <li class="nav-item"><a class="nav-link" href="/login.html" data-testid="nav-login">Login</a></li>
      <li class="nav-item ms-2"><a class="btn btn-sv-primary" href="/register.html" style="padding:8px 22px;font-size:.9rem;" data-testid="nav-register">Sign Up</a></li>`;
  }
}

function requireAuth(roles) {
  const u = getUser();
  if (!u) { window.location.href = '/login.html'; return null; }
  if (roles && !roles.includes(u.role)) { window.location.href = '/index.html'; return null; }
  return u;
}

function fmtINR(n) {
  if (n == null) return '₹0';
  return '₹' + Number(n).toLocaleString('en-IN');
}
function escapeHTML(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function qs(n) { return new URLSearchParams(location.search).get(n); }
function roomNo(floor, room) { return `${floor}${String(room).padStart(2,'0')}`; }
document.addEventListener('DOMContentLoaded', renderNavbar);
