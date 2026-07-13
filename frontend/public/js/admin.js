// Admin panel logic
requireAuth(['admin']);

const u = getUser();
if (u) document.getElementById('adm-name').textContent = u.name || u.email;
document.getElementById('today-label').textContent = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
const BE = window.APP_CONFIG.API_BASE_URL;

// ---------- Navigation ----------
const sections = [
  'overview',
  'residents',
  'rent',
  'bookings',
  'reminders',
  'webhooks',
  'expenditure'
];
const loaders = {};
function showSection(name) {

  // Hide Reports page
  document.getElementById("page-report").style.display = "none";

  // Hide all admin pages
  sections.forEach(s => {

    const page = document.getElementById("sec-" + s);

    if (page) {
      page.classList.remove("show");
      page.style.display = "none";
    }

    const a = document.querySelector(`.snav[data-section="${s}"]`);

    if (a) {
      a.classList.remove("active");
    }

  });

  // Show selected page
  const current = document.getElementById("sec-" + name);

  if (current) {
    current.classList.add("show");
    current.style.display = "block";
  }

  const active = document.querySelector(`.snav[data-section="${name}"]`);

  if (active) {
    active.classList.add("active");
  }

  document.getElementById("page-title").textContent = {
    overview: "Overview",
    residents: "Residents",
    rent: "Monthly Rent",
    bookings: "All Bookings",
    reminders: "Reminders",
    webhooks: "Webhooks",
    expenditure: "Expenditures"
  }[name];

  if (loaders[name]) {
    loaders[name]();
  }

  history.replaceState(null, "", "#" + name);
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
loaders.expenditure = loadExpensePage;
async function loadExpensePage() {


  await loadDashboardTotals();

  await loadExpenses();
}
async function loadDashboardTotals() {

  try {

    const stats = await apiFetch("/api/admin/stats");

    document.getElementById("totalIncome").innerText =
      "₹" + Number(stats.total_income || 0).toLocaleString("en-IN");

    document.getElementById("totalExpense").innerText =
      "₹" + Number(stats.total_expense || 0).toLocaleString("en-IN");

    document.getElementById("totalProfit").innerText =
      "₹" + Number(stats.profit || 0).toLocaleString("en-IN");

  } catch (err) {

    console.log(err);

  }

}

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
    const host = document.getElementById("residents-grid");

    host.innerHTML =
        '<div class="text-center py-4"><div class="spinner-border"></div></div>';

    try {

        const d = await apiFetch("/api/admin/residents");

        if (!d.items.length) {
            host.innerHTML =
                '<p class="text-center text-muted py-5">No residents found.</p>';
            return;
        }

        host.innerHTML = d.items.map(r => {

            const photoUrl = r.photo_url
                ? (r.photo_url.startsWith("http")
                    ? r.photo_url
                    : BE + r.photo_url)
                : "";

            const aadhaarUrl = r.aadhaar_url
                ? (r.aadhaar_url.startsWith("http")
                    ? r.aadhaar_url
                    : BE + r.aadhaar_url)
                : "";

            const photo = photoUrl
                ? `
                <img
                    src="${photoUrl}"
                    class="resident-photo"
                    onclick="viewDoc('${photoUrl}','Photo - ${escapeHTML(r.name)}')"
                    data-testid="resident-photo"
                />
                `
                : `
                <div class="resident-photo placeholder">
                    <i class="bi bi-person-fill"></i>
                </div>
                `;

            const aadhaarBtn = aadhaarUrl
                ? (
                    aadhaarUrl.toLowerCase().endsWith(".pdf")
                        ? `
                        <a
                            class="btn btn-sv-outline btn-sm"
                            href="${aadhaarUrl}"
                            target="_blank"
                        >
                            <i class="bi bi-file-earmark-pdf me-1"></i>
                            Aadhaar PDF
                        </a>
                        `
                        : `
                        <button
                            class="btn btn-sv-outline btn-sm"
                            onclick="viewDoc('${aadhaarUrl}','Aadhaar - ${escapeHTML(r.name)}')"
                        >
                            <i class="bi bi-card-image me-1"></i>
                            Aadhaar
                        </button>
                        `
                )
                : "";

            return `
            <div class="resident-card">

                ${photo}

                <div class="resident-info">

                    <h5>${escapeHTML(r.name)}</h5>

                    <div class="resident-meta">

                        <span>
                            <i class="bi bi-telephone-fill"></i>
                            ${escapeHTML(r.phone)}
                            ${r.alt_phone ? " / " + escapeHTML(r.alt_phone) : ""}
                        </span>

                        <span>
                            <i class="bi bi-envelope-fill"></i>
                            ${escapeHTML(r.email)}
                        </span>

                        <span>
                            <i class="bi bi-credit-card-2-front-fill"></i>
                            ${escapeHTML(r.aadhaar_number || "-")}
                        </span>

                        <span>
                            <i class="bi bi-calendar-event-fill"></i>
                            Joined ${escapeHTML(r.join_date || "-")}
                        </span>

                    </div>

                    <div class="resident-beds-chips">

                        ${r.beds.map(b => `
                            <span class="bed-chip">
                                F${b.floor} · ${escapeHTML(b.room)} · Bed ${b.bed} · ${b.sharing}-share
                            </span>
                        `).join("")}

                        <span class="bed-chip" style="background:var(--accent);color:#fff">
                            ${fmtINR(r.monthly_rent)}/mo
                        </span>

                    </div>

                    <div class="resident-actions">

                        ${aadhaarBtn}

                        <button
                            class="btn btn-outline-danger btn-sm"
                            onclick="checkOut('${r.booking_group_id}','${escapeHTML(r.name)}')">
                            <i class="bi bi-box-arrow-right me-1"></i>
                            Check Out
                        </button>

                    </div>

                </div>

            </div>
            `;

        }).join("");

    } catch (e) {

        toast(e.message, "error");
        console.error(e);

    }
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
    const currentMonth = new Date().toISOString().slice(0, 7);
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
        const title = `${m} · ${cell.status}${cell.paid_at ? ' on ' + cell.paid_at.slice(0, 10) : ''}`;
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
        const photoUrl = b.photo_url
    ? (b.photo_url.startsWith("http")
        ? b.photo_url
        : BE + b.photo_url)
    : "";

const photo = photoUrl
    ? `<img
          src="${photoUrl}"
          class="doc-thumb me-1"
          onclick="viewDoc('${photoUrl}','Photo')"
       />`
    : '<span class="text-muted small">—</span>';
        const aadhaarUrl = b.aadhaar_url
    ? (b.aadhaar_url.startsWith("http")
        ? b.aadhaar_url
        : BE + b.aadhaar_url)
    : "";

const aad = aadhaarUrl
    ? (aadhaarUrl.toLowerCase().endsWith(".pdf")
        ? `<a href="${aadhaarUrl}" target="_blank"
             class="btn btn-sm btn-sv-outline">
             <i class="bi bi-file-earmark-pdf"></i>
           </a>`
        : `<img
             src="${aadhaarUrl}"
             class="doc-thumb"
             onclick="viewDoc('${aadhaarUrl}','Aadhaar')"
           />`)
    : "";
        return `<tr>
          <td><small>${(b.created_at || '').slice(0, 10)}</small></td>
          <td>${escapeHTML(b.name)}<br/><small class="text-muted">${escapeHTML(b.phone)}</small></td>
          <td>F${b.floor} · ${escapeHTML(b.room_number)} · B${b.bed}</td>
          <td>${b.sharing_type}-share</td>
          <td>${fmtINR(b.monthly_rent)}</td>
          <td class="d-flex gap-1">${photo}${aad}</td>
          <td><span class="status-pill status-${b.status}">${b.status}</span></td>
          <td><span class="status-pill status-${b.payment_status === 'paid' ? 'paid' : 'pending'}">${b.payment_status}</span></td>
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
      ? new Date(job.next_run).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })
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
          <div><strong>${escapeHTML(r.to_email || '—')}</strong> · ${escapeHTML(r.month || '')}</div>
          <small class="text-muted">${(r.sent_at || '').replace('T', ' ').slice(0, 19)} · ${escapeHTML(r.subject || '')} · by ${escapeHTML(r.triggered_by || '-')}</small>
        </div>
        <div class="text-end">
          <span class="status-pill status-${r.sent ? 'paid' : 'pending'}">${r.sent ? 'Sent' : 'Logged'}</span>
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
        <td><small>${(w.received_at || '').replace('T', ' ').slice(0, 19)}</small></td>
        <td><span class="status-pill status-${(w.event || '').includes('captured') ? 'paid' : (w.event || '').includes('failed') ? 'cancelled' : 'pending'}">${escapeHTML(w.event || '-')}</span></td>
        <td><code class="small">${escapeHTML(w.order_id || '-')}</code></td>
        <td><code class="small">${escapeHTML(w.payment_id || '-')}</code></td>
      </tr>`).join('') + '</tbody></table>';
  } catch (e) { toast(e.message, 'error'); }
}

window.viewDoc = function (url, title) {
  document.getElementById('doc-title').textContent = title;
  document.getElementById('doc-img').src = url;
  document.getElementById('doc-download').href = url;
  new bootstrap.Modal(document.getElementById('docModal')).show();
};

// Boot — read hash to deep-link tabs
const initial = (location.hash || '#overview').slice(1);
showSection(sections.includes(initial) ? initial : 'overview');


// Resident Search
document.addEventListener("input", function (e) {
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
document.addEventListener("input", function (e) {
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
const addExpenseBtn = document.getElementById("btn-add-expense");
const reportBtn = document.getElementById("btn-expense-report");
const expensePopup = document.getElementById("expense-popup");
const closeExpenseBtn = document.getElementById("closeExpense");

if (addExpenseBtn) {
  addExpenseBtn.addEventListener("click", () => {
    expensePopup.style.display = "flex";
  });
}
if (reportBtn) {

  reportBtn.addEventListener("click", async () => {

    document.querySelectorAll(".admin-section").forEach(sec => {
      sec.style.display = "none";
    });


    document.getElementById("page-report").style.display = "block";

    requestAnimationFrame(async () => {
      await loadReports();
    });

  });

}

if (closeExpenseBtn) {
  closeExpenseBtn.addEventListener("click", () => {
    expensePopup.style.display = "none";
  });
}
window.addEventListener("click", function (e) {
  if (e.target === expensePopup) {
    expensePopup.style.display = "none";
  }
});

const saveExpenseBtn = document.getElementById("saveExpense");

let bookingChart = null;
let expenseChart = null;
let profitChart = null;
let incomeExpenseChart = null;
let allExpenses = [];

let editingExpenseId = null;

if (saveExpenseBtn) {
  saveExpenseBtn.addEventListener("click", saveExpense);
}

async function saveExpense() {

  const productName = document.getElementById("expenseProduct").value.trim();
  const price = Number(document.getElementById("expensePrice").value);
  const date = document.getElementById("expenseDate").value;
  const notes = document.getElementById("expenseNotes").value.trim();

  if (!productName || !price || !date) {
    alert("Please fill all fields");
    return;
  }

  const response = await fetch(

    `${window.APP_CONFIG.API_BASE_URL}/api/expenditures/${editingExpenseId || ""}`,

    {

      method: editingExpenseId ? "PUT" : "POST",

      headers: {
        "Content-Type": "application/json"
      },

      body: JSON.stringify({
        productName,
        price,
        date,
        notes
      })

    }

  );

  const data = await response.json();

  if (response.ok) {

    alert(
      editingExpenseId
        ?
        "Expenditure Updated Successfully"
        :
        "Expenditure Added Successfully"
    );

    document.getElementById("expenseProduct").value = "";
    document.getElementById("expensePrice").value = "";
    document.getElementById("expenseDate").value = "";
    document.getElementById("expenseNotes").value = "";
    editingExpenseId = null;

    saveExpenseBtn.textContent = "Save";
    loadExpenses();

    expensePopup.style.display = "none";

  } else {

    alert(data.detail || "Failed");

  }

}
async function loadExpenses() {

  const table = document.getElementById("expense-table");

  table.innerHTML = "<h5>Loading...</h5>";

  const response = await fetch(
    `${window.APP_CONFIG.API_BASE_URL}/api/expenditures/`
  );

  const expenses = await response.json();
  allExpenses = expenses;
  renderExpenseTable(expenses);

  updateExpenseSummary(expenses);



}
async function deleteExpense(id) {

  if (!confirm("Delete this expenditure?")) {
    return;
  }

  const response = await fetch(

    `${window.APP_CONFIG.API_BASE_URL}/api/expenditures/${id}`,

    {
      method: "DELETE"
    }

  );

  const data = await response.json();

  if (response.ok) {

    alert(data.message);

    loadExpenses();

  } else {

    alert(data.detail);

  }

}
async function editExpense(id) {

  const response = await fetch(
    `${window.APP_CONFIG.API_BASE_URL}/api/expenditures/`
  );

  const expenses = await response.json();

  const expense = expenses.find(x => x._id === id);

  if (!expense) return;

  editingExpenseId = id;

  document.getElementById("expenseProduct").value = expense.productName;
  document.getElementById("expensePrice").value = expense.price;
  document.getElementById("expenseDate").value = expense.date.substring(0, 10);
  document.getElementById("expenseNotes").value = expense.notes;

  expensePopup.style.display = "flex";

  saveExpenseBtn.textContent = "Update";
}

function updateExpenseSummary(expenses) {

  let totalExpense = 0;

  let monthExpense = 0;

  const currentMonth = new Date().toISOString().slice(0, 7);

  expenses.forEach(expense => {

    totalExpense += Number(expense.price);

    if (expense.date.slice(0, 7) === currentMonth) {

      monthExpense += Number(expense.price);

    }

  });

  document.getElementById("totalExpense").textContent =
    "₹" + totalExpense.toLocaleString();

  document.getElementById("monthExpense").textContent =
    "₹" + monthExpense.toLocaleString();

}
document.getElementById("expenseSearch").addEventListener("input", function () {

  const keyword = this.value.toLowerCase();

  const filtered = allExpenses.filter(expense =>

    expense.productName.toLowerCase().includes(keyword)

  );

  renderExpenseTable(filtered);

});
function renderExpenseTable(expenses) {

  const table = document.getElementById("expense-table");

  let html = `
    <table class="table table-bordered table-hover">
        <thead class="table-dark">
            <tr>
                <th>Product</th>
                <th>Price</th>
                <th>Date</th>
                <th>Notes</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
    `;

  expenses.forEach(expense => {

    html += `
        <tr>
            <td>${expense.productName}</td>
            <td>₹${expense.price}</td>
            <td>${expense.date}</td>
            <td>${expense.notes}</td>
            <td>
                <button class="btn btn-warning btn-sm"
                    onclick="editExpense('${expense._id}')">
                    Edit
                </button>

                <button class="btn btn-danger btn-sm"
                    onclick="deleteExpense('${expense._id}')">
                    Delete
                </button>
            </td>
        </tr>
        `;

  });

  html += `
        </tbody>
    </table>
    `;

  table.innerHTML = html;

}
async function loadReports() {

  const data = await apiFetch("/api/admin/monthly-chart");

  document.getElementById("reportIncome").innerText =
    "₹" + data.income.reduce((a, b) => a + b, 0);

  document.getElementById("reportExpense").innerText =
    "₹" + data.expense.reduce((a, b) => a + b, 0);

  document.getElementById("reportProfit").innerText =
    "₹" + data.profit.reduce((a, b) => a + b, 0);

  document.getElementById("reportLoss").innerText =
    "₹" + data.loss.reduce((a, b) => a + b, 0);
  const totalLoss = data.profit
    .filter(v => v < 0)
    .reduce((a, b) => a + Math.abs(b), 0);

  document.getElementById("reportLoss").innerText =
    "₹" + totalLoss;

  drawIncomeExpenseChart(data);
  drawBookingChart(data);
  drawProfitChart(data);
  drawExpenseChart(data);

}
function backToExpense() {

  document.getElementById("page-report").style.display = "none";

  document.querySelectorAll(".admin-section").forEach(sec => {
    sec.style.display = "none";
  });

  document.getElementById("sec-expenditure").style.display = "block";

}
function drawIncomeExpenseChart(data) {

  try {




    const canvas = document.getElementById("incomeExpenseChart");

    if (!canvas) {

      return;
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = 300;
    }

    const ctx = canvas.getContext("2d");

    if (!ctx) {
      console.error("Cannot get 2D context");
      return;
    }

    if (incomeExpenseChart) {
      incomeExpenseChart.destroy();
    }

    incomeExpenseChart = new Chart(ctx, {
      type: "bar",

      data: {
        labels: data.months || [],
        datasets: [
          {
            label: "Income",
            data: data.income || [],
            backgroundColor: "#28a745"
          },
          {
            label: "Expense",
            data: data.expense || [],
            backgroundColor: "#dc3545"
          }
        ]
      },

      options: {
        responsive: true,
        maintainAspectRatio: false,

        plugins: {
          legend: {
            position: "top"
          }
        },

        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    });

  } catch (err) {
    console.error("Chart Error:", err);
  }
}
function drawExpenseChart(data) {

  const canvas = document.getElementById("expenseChart");

  if (!canvas) {

    return;
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = 300;
  }

  const ctx = canvas.getContext("2d");

  if (expenseChart) {
    expenseChart.destroy();
  }

  expenseChart = new Chart(ctx, {
    type: "pie",

    data: {
      labels: data.expense_labels || [],
      datasets: [{
        data: data.expense_values || []
      }]
    },

    options: {
      responsive: true,
      maintainAspectRatio: false
    }
  });

}
function drawProfitChart(data) {

    const canvas = document.getElementById("profitChart");

    if (profitChart) {
        profitChart.destroy();
    }

    profitChart = new Chart(canvas, {

        type: "bar",

        data: {

            labels: data.months,

            datasets: [

                {
                    label: "Profit",
                    data: data.profit,
                    backgroundColor: "green"
                },

                {
                    label: "Loss",
                    data: data.loss,
                    backgroundColor: "red"
                }

            ]

        },

        options: {
            responsive: true,
            maintainAspectRatio: false
        }

    });

}
function drawBookingChart(data) {

  const canvas = document.getElementById("bookingChart");

  if (!canvas) {

    return;
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = 300;
  }

  const ctx = canvas.getContext("2d");

  if (bookingChart) {
    bookingChart.destroy();
  }

  bookingChart = new Chart(ctx, {
    type: "line",

    data: {
      labels: data.months || [],
      datasets: [{
        label: "Bookings",
        data: data.bookings || [],
        tension: 0.4
      }]
    },

    options: {
      responsive: true,
      maintainAspectRatio: false
    }

  });

}

