// Admin panel logic
requireAuth(['admin']);

const u = getUser();
if (u) document.getElementById('adm-name').textContent = u.name || u.email;
document.getElementById('today-label').textContent = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
const BE = window.APP_CONFIG.API_BASE_URL;

// ---------- Navigation ----------
const sections = ['overview','residents','rent','bookings','reminders','webhooks'];
const loaders = {};
function showSection(name) {
  sections.forEach(s => {
    document.getElementById('sec-' + s).classList.toggle('show', s === name);
    const a = document.querySelector(`.snav[data-section="${s}"]`);
    if (a) a.classList.toggle('active', s === name);
  });
  document.getElementById('page-title').textContent =
    { overview:'Overview', residents:'Residents', rent:'Monthly Rent', bookings:'All Bookings', reminders:'Reminders', webhooks:'Webhooks' }[name];
  if (loaders[name]) loaders[name]();
  history.replaceState(null, '', '#' + name);
}
document.querySelectorAll('.snav').forEach(a => {
  a.addEventListener('click', e => { e.preventDefault(); showSection(a.dataset.section); });
});


// ---------- Loaders ----------
loaders.overview = stats;
loaders.residents = residents;
loaders.rent = rentMatrix;
loaders.bookings = bks;
loaders.reminders = reminders;
loaders.webhooks = hooks;

async function stats() {
  try {
    const s = await apiFetch('/api/admin/stats');
    document.getElementById('s-total').textContent = s.total_beds;
    document.getElementById('s-booked').textContent = s.booked_beds;
    document.getElementById('s-avail').textContent = s.available_beds;
    document.getElementById('s-occ').textContent = s.occupancy_pct + '%';
    document.getElementById('s-users').textContent = s.users;
    document.getElementById('s-paid-bkn').textContent = s.paid_bookings;
    document.getElementById('s-rent-total').textContent = fmtINR(s.revenue_rent);
    document.getElementById('s-adv').textContent = fmtINR(s.revenue_advance);
    // Month section
    document.getElementById('s-month-label').textContent = s.current_month;
    document.getElementById('s-month-collected').textContent = fmtINR(s.rent_collected_month);
    document.getElementById('s-month-pending-amt').textContent = fmtINR(s.rent_pending_amount);
    document.getElementById('s-month-paid-cnt').textContent = s.rent_paid_count;
    document.getElementById('s-month-pending-cnt').textContent = s.rent_pending_count;
  } catch (e) { toast(e.message, 'error'); }
}

async function residents() {
  const host = document.getElementById('residents-grid');
  host.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';
  try {
    const d = await apiFetch('/api/admin/residents');
    if (!d.items.length) {
      host.innerHTML = '<p class="text-center text-muted py-5">No residents yet. Once guests pay, they\'ll show up here.</p>';
      return;
    }
    host.innerHTML = d.items.map(r => {
      const photo = r.photo_url
        ? `<img src="${BE}${escapeHTML(r.photo_url)}" class="resident-photo" onclick="viewDoc('${BE}${escapeHTML(r.photo_url)}','Photo – ${escapeHTML(r.name)}')" data-testid="resident-photo"/>`
        : `<div class="resident-photo placeholder"><i class="bi bi-person-fill"></i></div>`;
      const aadhaarBtn = r.aadhaar_url
        ? (r.aadhaar_url.toLowerCase().endsWith('.pdf')
            ? `<a class="btn btn-sv-outline btn-sm" href="${BE}${escapeHTML(r.aadhaar_url)}" target="_blank" data-testid="resident-aadhaar-pdf"><i class="bi bi-file-earmark-pdf me-1"></i>Aadhaar PDF</a>`
            : `<button class="btn btn-sv-outline btn-sm" onclick="viewDoc('${BE}${escapeHTML(r.aadhaar_url)}','Aadhaar – ${escapeHTML(r.name)}')" data-testid="resident-aadhaar-btn"><i class="bi bi-card-image me-1"></i>Aadhaar</button>`)
        : '';
      return `
        <div class="resident-card" data-testid="resident-card">
          ${photo}
          <div class="resident-info">
            <h5>${escapeHTML(r.name)}</h5>
            <div class="resident-meta">
              <span><i class="bi bi-telephone-fill"></i>${escapeHTML(r.phone)}${r.alt_phone?` / ${escapeHTML(r.alt_phone)}`:''}</span>
              <span><i class="bi bi-envelope-fill"></i>${escapeHTML(r.email)}</span>
              <span><i class="bi bi-credit-card-2-front-fill"></i>${escapeHTML(r.aadhaar_number||'—')}</span>
              <span><i class="bi bi-calendar-event-fill"></i>Joined ${escapeHTML(r.join_date||'-')}</span>
            </div>
            <div class="resident-beds-chips">
              ${r.beds.map(b => `<span class="bed-chip">F${b.floor} · ${escapeHTML(b.room)} · Bed ${b.bed} · ${b.sharing}-share</span>`).join('')}
              <span class="bed-chip" style="background:var(--accent);color:#fff">${fmtINR(r.monthly_rent)}/mo</span>
            </div>
            <div class="resident-actions">
              ${aadhaarBtn}
              <button class="btn btn-outline-danger btn-sm" onclick="checkOut('${r.booking_group_id}','${escapeHTML(r.name)}')" data-testid="checkout-btn"><i class="bi bi-box-arrow-right me-1"></i>Check Out</button>
            </div>
          </div>
        </div>`;
    }).join('');
  } catch (e) { toast(e.message, 'error'); }
}

async function rentMatrix() {
  const host = document.getElementById('rent-matrix-wrap');
  host.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';
  try {
    const d = await apiFetch('/api/admin/rent_matrix?months=8');
    if (!d.residents.length) {
      host.innerHTML = '<p class="text-center text-muted py-5">No rent schedule yet. Schedules are auto-created when a booking is paid.</p>';
      return;
    }
    const currentMonth = new Date().toISOString().slice(0,7);
    const rows = d.residents.map(r => {
      return `<tr>
        <td>
          <strong>${escapeHTML(r.name)}</strong><br/>
          <small class="text-muted">${escapeHTML(r.email)} · ${escapeHTML(r.phone)}</small>
        </td>
        ${d.months.map(m => {
          const cell = r.months[m];
          if (!cell) return '<td><span class="rent-cell rent-cancelled" title="N/A">—</span></td>';
          const overdue = cell.status === 'pending' && m < currentMonth ? ' overdue' : '';
          const icon = cell.status === 'paid' ? '<i class="bi bi-check2"></i>'
                     : cell.status === 'cancelled' ? '<i class="bi bi-x"></i>'
                     : '<i class="bi bi-hourglass-split"></i>';
          const title = `${m} · ${cell.status}${cell.paid_at?' on '+cell.paid_at.slice(0,10):''}`;
          const onclick = cell.status === 'pending'
            ? `onclick="openMarkPaid('${cell.id}','${escapeHTML(r.name)}','${m}',${r.amount})"`
            : '';
          const remindBtn = cell.status === 'pending'
            ? `<button class="btn btn-sm btn-link p-0 ms-1" onclick="event.stopPropagation();sendReminder('${cell.id}','${escapeHTML(r.name)}','${m}')" data-testid="send-reminder-btn" title="Send reminder"><i class="bi bi-bell-fill text-warning"></i></button>`
            : '';
          return `<td>
            <span class="rent-cell rent-${cell.status}${overdue}" ${onclick} title="${title}" data-testid="rent-cell-${cell.status}">
              ${icon}${cell.reminded ? '<span class="reminder-dot"></span>' : ''}
            </span>
            ${remindBtn}
          </td>`;
        }).join('')}
      </tr>`;
    });
    host.innerHTML = `
      <div class="table-responsive">
        <table class="rent-matrix-table">
          <thead><tr><th>Resident</th>${d.months.map(m => `<th>${m}</th>`).join('')}</tr></thead>
          <tbody>${rows.join('')}</tbody>
        </table>
      </div>`;
  } catch (e) { toast(e.message, 'error'); }
}

let _markPaidId = null;
function openMarkPaid(rentId, name, month, amount) {
  _markPaidId = rentId;
  document.getElementById('paid-info').innerHTML =
    `Mark rent paid for <strong>${escapeHTML(name)}</strong> · ${escapeHTML(month)} · <strong>${fmtINR(amount)}</strong>`;
  document.getElementById('paid-ref').value = '';
  new bootstrap.Modal('#paidModal').show();
}
async function confirmMarkPaid() {
  if (!_markPaidId) return;
  try {
    await apiFetch(`/api/admin/rent/${_markPaidId}/mark_paid`, {
      method: 'POST',
      body: JSON.stringify({
        payment_method: document.getElementById('paid-method').value,
        payment_reference: document.getElementById('paid-ref').value,
      }),
    });
    toast('Marked paid', 'success');
    bootstrap.Modal.getInstance(document.getElementById('paidModal')).hide();
    rentMatrix(); stats();
  } catch (e) { toast(e.message, 'error'); }
}

async function sendReminder(rentId, name, month) {
  if (!confirm(`Send rent reminder email to ${name} for ${month}?`)) return;
  try {
    const res = await apiFetch(`/api/admin/rent/${rentId}/send_reminder`, {
      method: 'POST',
      body: JSON.stringify({ channel: 'email' }),
    });
    if (res.sent) toast('✉ Reminder sent', 'success');
    else toast('Reminder logged (' + res.reason + ')', 'info');
    rentMatrix();
  } catch (e) { toast(e.message, 'error'); }
}

async function checkOut(gid, name) {
  if (!confirm(`Check out ${name}? This frees the beds and cancels future rent.`)) return;
  try {
    await apiFetch(`/api/admin/bookings/group/${gid}/checkout`, { method: 'POST' });
    toast('Checked out', 'success');
    residents(); rentMatrix(); stats();
  } catch (e) { toast(e.message, 'error'); }
}

async function bks() {
  const host = document.getElementById('a-bks');
  host.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';
  try {
    const d = await apiFetch('/api/admin/bookings');
    host.innerHTML = '<div class="table-responsive"><table class="table align-middle" style="background:var(--surface);border-radius:14px;overflow:hidden"><thead><tr><th>Created</th><th>Guest</th><th>Bed</th><th>Sharing</th><th>Rent</th><th>Docs</th><th>Status</th><th>Payment</th></tr></thead><tbody>' +
      d.items.map(b => {
        const photo = b.photo_url ? `<img src="${BE}${escapeHTML(b.photo_url)}" class="doc-thumb me-1" onclick="viewDoc('${BE}${escapeHTML(b.photo_url)}','Photo')" data-testid="view-photo-btn"/>` : '<span class="text-muted small">—</span>';
        const aad = b.aadhaar_url ? (b.aadhaar_url.toLowerCase().endsWith('.pdf')
          ? `<a href="${BE}${escapeHTML(b.aadhaar_url)}" target="_blank" class="btn btn-sm btn-sv-outline"><i class="bi bi-file-earmark-pdf"></i></a>`
          : `<img src="${BE}${escapeHTML(b.aadhaar_url)}" class="doc-thumb" onclick="viewDoc('${BE}${escapeHTML(b.aadhaar_url)}','Aadhaar')" data-testid="view-aadhaar-btn"/>`) : '';
        return `<tr>
          <td><small>${(b.created_at||'').slice(0,10)}</small></td>
          <td>${escapeHTML(b.name)}<br/><small class="text-muted">${escapeHTML(b.phone)}</small></td>
          <td>F${b.floor} · ${escapeHTML(b.room_number)} · B${b.bed}</td>
          <td>${b.sharing_type}-share</td>
          <td>${fmtINR(b.monthly_rent)}</td>
          <td class="d-flex gap-1">${photo}${aad}</td>
          <td><span class="status-pill status-${b.status}">${b.status}</span></td>
          <td><span class="status-pill status-${b.payment_status==='paid'?'paid':'pending'}">${b.payment_status}</span></td>
        </tr>`;
      }).join('') + '</tbody></table></div>';
  } catch (e) { toast(e.message, 'error'); }
}

async function reminders() {
  // Cron status
  try {
    const cron = await apiFetch('/api/admin/scheduler/status');
    const job = (cron.jobs || [])[0];
    document.getElementById('cron-next').textContent = job && job.next_run
      ? new Date(job.next_run).toLocaleString('en-IN', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', timeZone:'Asia/Kolkata' })
      : (cron.running ? 'No upcoming runs' : 'Scheduler offline');
  } catch (e) { /* non-blocking */ }

  const host = document.getElementById('a-rems');
  host.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';
  try {
    const d = await apiFetch('/api/admin/reminders');
    if (!d.items.length) {
      host.innerHTML = '<p class="text-center text-muted py-5">No reminders sent yet. Use the bell icon in the Rent Matrix to send one or click "Send to ALL overdue" above.</p>';
      return;
    }
    host.innerHTML = d.items.map(r => `
      <div class="reminder-row" data-testid="reminder-row">
        <div class="rem-icon"><i class="bi bi-${r.sent ? 'check2-circle' : 'envelope'}"></i></div>
        <div class="flex-grow-1">
          <div><strong>${escapeHTML(r.to_email||'—')}</strong> · ${escapeHTML(r.month||'')}</div>
          <small class="text-muted">${(r.sent_at||'').replace('T',' ').slice(0,19)} · ${escapeHTML(r.subject||'')} · by ${escapeHTML(r.triggered_by||'-')}</small>
        </div>
        <div class="text-end">
          <span class="status-pill status-${r.sent?'paid':'pending'}">${r.sent?'Sent':'Logged'}</span>
          ${r.reason ? `<div class="small text-muted mt-1">${escapeHTML(r.reason)}</div>` : ''}
        </div>
      </div>`).join('');
  } catch (e) { toast(e.message, 'error'); }
}

async function sendAllOverdue() {
  if (!confirm('Send rent reminders to ALL residents with pending dues (current month and earlier)?')) return;
  try {
    const res = await apiFetch('/api/admin/reminders/send_overdue', { method: 'POST' });
    toast(`Queued ${res.queued} · sent ${res.sent} · logged ${res.logged_only}`, 'success');
    reminders();
  } catch (e) { toast(e.message, 'error'); }
}

async function hooks() {
  const host = document.getElementById('a-hooks');
  host.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></div>';
  try {
    const d = await apiFetch('/api/admin/webhook_events');
    if (!d.items.length) {
      host.innerHTML = '<p class="text-center text-muted py-4">No webhook events yet.</p>';
      return;
    }
    host.innerHTML = '<table class="table" style="background:var(--surface);border-radius:14px;overflow:hidden"><thead><tr><th>Received</th><th>Event</th><th>Order</th><th>Payment</th></tr></thead><tbody>' +
      d.items.map(w => `<tr>
        <td><small>${(w.received_at||'').replace('T',' ').slice(0,19)}</small></td>
        <td><span class="status-pill status-${(w.event||'').includes('captured')?'paid':(w.event||'').includes('failed')?'cancelled':'pending'}">${escapeHTML(w.event||'-')}</span></td>
        <td><code class="small">${escapeHTML(w.order_id||'-')}</code></td>
        <td><code class="small">${escapeHTML(w.payment_id||'-')}</code></td>
      </tr>`).join('') + '</tbody></table>';
  } catch (e) { toast(e.message, 'error'); }
}

window.viewDoc = function(url, title) {
  document.getElementById('doc-title').textContent = title;
  document.getElementById('doc-img').src = url;
  document.getElementById('doc-download').href = url;
  new bootstrap.Modal(document.getElementById('docModal')).show();
};

// Boot — read hash to deep-link tabs
const initial = (location.hash || '#overview').slice(1);
showSection(sections.includes(initial) ? initial : 'overview');


// Resident Search
document.addEventListener("input", function(e) {
    if (e.target.id === "residentSearch") {
        const value = e.target.value.toLowerCase();

        document.querySelectorAll(".resident-card").forEach(card => {
            card.style.display =
                card.innerText.toLowerCase().includes(value)
                    ? "flex"
                    : "none";
        });
    }
});

// Booking Search
document.addEventListener("input", function(e) {
    if (e.target.id === "bookingSearch") {
        const value = e.target.value.toLowerCase();

        document.querySelectorAll("#a-bks tbody tr").forEach(row => {
            row.style.display =
                row.innerText.toLowerCase().includes(value)
                    ? ""
                    : "none";
        });
    }
});

document.addEventListener("DOMContentLoaded", function () {

    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("sidebar-toggle");

    toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        sidebar.classList.toggle("open");
    });

    document.addEventListener("click", function (e) {

        if (
            window.innerWidth <= 991 &&
            sidebar.classList.contains("open") &&
            !sidebar.contains(e.target) &&
            !toggle.contains(e.target)
        ) {
            sidebar.classList.remove("open");
        }

    });

    document.querySelectorAll(".snav").forEach(link => {

        link.addEventListener("click", function () {

            if (window.innerWidth <= 991) {
                sidebar.classList.remove("open");
            }

        });

    });

});

