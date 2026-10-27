// Shared helpers for all views. Every view talks to the SAME server/db.json,
// so an action taken in one view is visible in the others on next refresh.

const STATE_LABELS = {
  created: "Created",
  scheduled: "Scheduled",
  site_visit: "Site visit",
  report_drafting: "Report drafting",
  engineer_review: "Engineer review",
  approved: "Approved",
  closed: "Closed",
};

const ROLE_LABELS = {
  admin: "Admin (HOD)",
  engineer: "Engineer",
  cs: "Customer Service",
  technician: "Technician",
};

// ---------- Icon set (replaces unicode emoji, item 9 of the handover list) ----------
// One consistent stroke-style SVG per icon, instead of unicode emoji (which
// render differently per OS/device — e.g. the old &#128295; wrench looked
// different on Windows vs Android vs iOS). Each icon is 1em x 1em so it
// scales with whatever font-size its container already uses, and inherits
// color via currentColor — no extra CSS required to use it.
const ICON_PATHS = {
  warning: '<path d="M12 3.5 21 19.5H3Z"/><line x1="12" y1="9.5" x2="12" y2="13.5"/><circle cx="12" cy="16.3" r="0.9" fill="currentColor" stroke="none"/>',
  reschedule: '<path d="M4.5 12a7.5 7.5 0 0 1 12.8-5.3L19 8"/><path d="M19 4v4h-4"/><path d="M19.5 12a7.5 7.5 0 0 1-12.8 5.3L5 16"/><path d="M5 20v-4h4"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="16" rx="2"/><line x1="3.5" y1="9.5" x2="20.5" y2="9.5"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>',
  shield: '<path d="M12 3 20 6.5V12c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6.5Z"/><path d="M9 12l2 2 4-4.5"/>',
  user: '<circle cx="12" cy="8.5" r="3.2"/><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6"/>',
  wrench: '<path d="M16.5 3.5 20.5 7.5 17 11 13 7Z"/><path d="M13 7 4.5 15.5a2 2 0 1 0 2.8 2.8L15.8 10"/>',
  check: '<path d="M4.5 13 9.5 18 19.5 7"/>',
  document: '<path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"/><path d="M14 3.5V8h4"/><line x1="8.5" y1="12" x2="15.5" y2="12"/><line x1="8.5" y1="15.5" x2="15.5" y2="15.5"/>',
  clipboard: '<rect x="5.5" y="4.5" width="13" height="16" rx="1.5"/><rect x="9" y="3" width="6" height="3" rx="1"/><line x1="8.5" y1="10.5" x2="15.5" y2="10.5"/><line x1="8.5" y1="14" x2="15.5" y2="14"/><line x1="8.5" y1="17.5" x2="12.5" y2="17.5"/>',
  compass: '<circle cx="12" cy="12" r="8.5"/><path d="M15 9l-2 6-6 2 2-6Z"/>',
  lightning: '<path d="M13 3 6 13h5l-1 8 7-10h-5Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><line x1="12" y1="2.5" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="21.5"/><line x1="2.5" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="21.5" y2="12"/><line x1="5" y1="5" x2="6.8" y2="6.8"/><line x1="17.2" y1="17.2" x2="19" y2="19"/><line x1="5" y1="19" x2="6.8" y2="17.2"/><line x1="17.2" y1="6.8" x2="19" y2="5"/>',
  pin: '<path d="M12 21s7-6.5 7-11.5A7 7 0 0 0 5 9.5C5 14.5 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.2"/>',
  lock: '<rect x="5.5" y="10.5" width="13" height="10" rx="1.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  phone: '<path d="M6 3.5h3l1.5 4-2 2a12 12 0 0 0 6 6l2-2 4 1.5v3a1.5 1.5 0 0 1-1.6 1.5A16 16 0 0 1 4.5 5.1 1.5 1.5 0 0 1 6 3.5Z"/>',
  pencil: '<path d="M4 20l1-4.5L15.5 5 19 8.5 8.5 19Z"/><line x1="13.5" y1="6.5" x2="17.5" y2="10.5"/>',
  upload: '<path d="M12 3v12"/><path d="M8 7l4-4 4 4"/><path d="M4.5 16.5V19a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-2.5"/>',
  download: '<path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M4.5 16.5V19a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-2.5"/>',
  logout: '<path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3"/><line x1="21" y1="12" x2="10.5" y2="12"/><path d="M17 8l4 4-4 4"/>',
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.2"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.2"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.2"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.2"/>',
  ticket: '<path d="M3.5 9a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v1.5a1.5 1.5 0 0 0 0 3V15a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-1.5a1.5 1.5 0 0 0 0-3Z"/><line x1="9" y1="7" x2="9" y2="17" stroke-dasharray="2 2"/>',
  building: '<rect x="5" y="3.5" width="9" height="17" rx="1"/><rect x="14" y="9" width="5" height="11.5" rx="1"/><line x1="7.5" y1="7" x2="9.5" y2="7"/><line x1="7.5" y1="11" x2="9.5" y2="11"/><line x1="7.5" y1="15" x2="9.5" y2="15"/>',
  chart: '<line x1="4" y1="20" x2="20" y2="20"/><rect x="6" y="13" width="3" height="7"/><rect x="11" y="9" width="3" height="11"/><rect x="16" y="5" width="3" height="15"/>',
  stopwatch: '<circle cx="12" cy="13" r="7.5"/><line x1="12" y1="13" x2="12" y2="9"/><line x1="12" y1="13" x2="15" y2="14.5"/><line x1="9.5" y1="2.5" x2="14.5" y2="2.5"/><line x1="12" y1="2.5" x2="12" y2="5.5"/>',
  book: '<path d="M4 5.5A2 2 0 0 1 6 3.5h5v17H6a2 2 0 0 1-2-2Z"/><path d="M20 5.5a2 2 0 0 0-2-2h-5v17h5a2 2 0 0 0 2-2Z"/>',
  users: '<circle cx="9" cy="8.5" r="3"/><path d="M3.5 20c0-3.3 2.9-5.5 5.5-5.5s5.5 2.2 5.5 5.5"/><circle cx="17" cy="9" r="2.3"/><path d="M15 14.2c2.3.3 4 2 4.5 4.3"/>',
  sparkle: '<path d="M12 3 13.3 9 19 10.3 13.3 11.6 12 17.6 10.7 11.6 5 10.3 10.7 9Z"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><ellipse cx="12" cy="12" rx="3.5" ry="8.5"/><line x1="3.5" y1="12" x2="20.5" y2="12"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2.2H4.5Z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  home: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6.5 10v9a1 1 0 0 0 1 1h3v-5h3v5h3a1 1 0 0 0 1-1v-9"/>',
  menu: '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>',
};

// icon(name, extraClass?) -> inline SVG string, sized to 1em so it drops into
// any spot that used to hold an emoji character without further CSS.
function icon(name, extraClass) {
  const body = ICON_PATHS[name];
  if (!body) return ""; // unknown name: fail quiet, not with a broken render
  const cls = extraClass ? ` ${extraClass}` : "";
  return `<svg class="icon-svg${cls}" viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-0.15em" aria-hidden="true">${body}</svg>`;
}

// ---------- Skeleton loading placeholders (Fasa 2, Item 10) ----------
// Shown the instant a page's static shell is in place, BEFORE the first
// render() has resolved its await api(...) calls — avoids the "blank flash"
// then "snap to full" feeling while the browser is waiting on the network.
// Purely visual: render() still overwrites the same container with real
// content exactly as before once data arrives, nothing about that flow
// changes.
function skeletonCard() {
  return `<div class="job-card-rich skeleton-wrap">
    <div class="skeleton-box" style="width:44px;height:44px;border-radius:12px;flex-shrink:0;"></div>
    <div class="job-card-rich-body">
      <div class="skeleton-line" style="width:70%;"></div>
      <div class="skeleton-line" style="width:45%;"></div>
    </div>
  </div>`;
}
function skeletonCards(count) {
  return Array.from({ length: count || 2 }, skeletonCard).join("");
}

// Row-shaped variant for .attention-item lists (dashboard "needs your
// attention" sections, list pages) — title+meta on the left, a pill-shaped
// badge placeholder on the right.
function skeletonRow() {
  return `<div class="attention-item skeleton-wrap">
    <div style="flex:1;">
      <div class="skeleton-line" style="width:55%;height:13px;"></div>
      <div class="skeleton-line" style="width:35%;height:11px;margin-top:6px;"></div>
    </div>
    <div class="skeleton-box" style="width:70px;height:20px;border-radius:999px;flex-shrink:0;"></div>
  </div>`;
}
function skeletonRows(count) {
  return Array.from({ length: count || 2 }, skeletonRow).join("");
}

// ---------- Empty state helper (Fasa 2, Item 11) ----------
// Drop-in replacement for the old `<div class="empty">plain text</div>`
// one-liners — same class, same spot in the page, so nothing about where or
// when these appear changes. Just adds a small muted icon above the message
// so a genuinely-empty list reads as "nothing here yet" rather than a blank
// gap that looks broken. iconName is optional — omit it to get the old
// plain-text look exactly as before.
function emptyState(message, iconName, extraStyle) {
  const iconHtml = iconName ? `<div class="empty-icon">${icon(iconName)}</div>` : "";
  const styleAttr = extraStyle ? ` style="${extraStyle}"` : "";
  return `<div class="empty"${styleAttr}>${iconHtml}<div>${message}</div></div>`;
}

// ---------- CSV export (client-side only — no backend endpoint needed,
// the data is already in hand wherever this is called from) ----------

// Per RFC 4180: wrap a field in quotes (and double up any quotes inside it)
// whenever it contains a comma, quote, or newline — otherwise leave it bare.
function csvEscapeField(value) {
  const s = value === null || value === undefined ? "" : String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

// `rows` is an array of arrays (first row = header). Builds the CSV text
// and triggers a browser download named `filename` (should end in .csv).
function downloadCsv(filename, rows) {
  const csv = rows.map(row => row.map(csvEscapeField).join(",")).join("\r\n");
  // Leading BOM so Excel/Google Sheets auto-detect UTF-8 instead of mangling
  // non-ASCII characters (e.g. names with diacritics).
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------- Session (simple picker login, no password) ----------
// Stored in localStorage as JSON: { id, name, role }. Every page except
// index.html (the login/picker) should call requireRole() before rendering.

function getSession() {
  try {
    return JSON.parse(localStorage.getItem("om_session"));
  } catch (e) {
    return null;
  }
}

function setSession(account) {
  localStorage.setItem("om_session", JSON.stringify(account));
}

function clearSession() {
  localStorage.removeItem("om_session");
}

// role: a single role string, an array of allowed roles, or null/undefined for "any logged-in account".
// Redirects to the login page AND throws, so the rest of the calling script — which
// assumes a valid session — never executes against null during the window before
// the browser actually finishes navigating away.
function requireRole(role) {
  const s = getSession();
  const allowed = role ? (Array.isArray(role) ? role : [role]) : null;
  if (!s || (allowed && !allowed.includes(s.role))) {
    window.location.href = "index.html";
    throw new Error("No valid session for this page — redirecting to login.");
  }
  return s;
}

function initials(name) {
  const parts = name.replace(/^[A-Za-z]+ - /, "").trim().split(/\s+/);
  return parts.slice(0, 2).map(p => p[0]).join("").toUpperCase();
}

function logout() {
  clearSession();
  window.location.href = "index.html";
}

// ---------- Ticket display helpers ----------

// Simple external status (Open / In Progress / Approved / Closed) — this is what a
// non-technical role (CS, Technician) should see instead of the internal state name.
function simpleStatus(t) {
  if (t.state === "closed") return t.closure.type === "early" ? "Closed (early)" : "Closed";
  if (t.state === "approved") return "Approved — ready to close";
  if (t.state === "created") return "Open";
  return "In progress";
}

function badgeClass(t) {
  if (t.state === "closed") return t.closure.type === "early" ? "badge badge-early" : "badge badge-closed";
  if (t.state === "approved") return "badge badge-approved";
  if (t.state === "created") return "badge badge-open";
  return "badge badge-progress";
}

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

// ---------- Ticket navigation context (Previous/Next on ticket-detail.html) ----------
// IMPORTANT: these two must stay at the TOP LEVEL of the file (not nested
// inside ticketTableHtml) — ticket-detail.html calls getTicketNavNeighbors()
// directly on page load, before ticketTableHtml ever runs, so if it were
// nested it would not exist yet and the page would crash with a
// ReferenceError (this happened before — see the fix note in this function).
function saveTicketNavList(orderedIds) {
  try { sessionStorage.setItem("ticketNavList", JSON.stringify(orderedIds)); } catch (e) {}
}

function getTicketNavNeighbors(currentId) {
  try {
    const list = JSON.parse(sessionStorage.getItem("ticketNavList") || "[]");
    const idx = list.indexOf(currentId);
    if (idx === -1) return { prev: null, next: null, position: null, total: 0 };
    return {
      prev: idx > 0 ? list[idx - 1] : null,
      next: idx < list.length - 1 ? list[idx + 1] : null,
      position: idx + 1,
      total: list.length,
    };
  } catch (e) {
    return { prev: null, next: null, position: null, total: 0 };
  }
}
function minutesSince(iso) {
  return (Date.now() - new Date(iso).getTime()) / 60000;
}

// SLA badge for an in-progress step. `deadlineDays` = calendar days allowed
// since `sinceIso`. Returns null once the day limit hasn't been reached yet,
// so callers can skip rendering anything for on-time items.
function slaInfo(sinceIso, deadlineDays) {
  if (!sinceIso) return null;
  const elapsedDays = (Date.now() - new Date(sinceIso).getTime()) / 86400000;
  const daysLeft = Math.ceil(deadlineDays - elapsedDays);
  if (daysLeft > 1) return null; // still comfortably within SLA, no badge needed
  if (daysLeft >= 0) return { overdue: false, label: daysLeft === 0 ? "Due today" : `${daysLeft} day left`, color: "#92400e" };
  const daysOver = Math.abs(daysLeft);
  return { overdue: true, label: `${daysOver} day${daysOver === 1 ? "" : "s"} overdue`, color: "#b91c1c" };
}

// A ticket is "stale" (needs attention) if it's not closed, not snoozed into the
// future, and its last event is older than the configured threshold — OR its
// snooze date has already passed (which forces it back into view).
function isStale(t, staleMinutes) {
  if (t.state === "closed") return false;
  if (t.snooze_until) {
    const snoozedUntil = new Date(t.snooze_until).getTime();
    if (snoozedUntil > Date.now()) return false; // still snoozed
    return true; // snooze expired — force back into view
  }
  const last = t.event_log[t.event_log.length - 1];
  if (!last) return false;
  return minutesSince(last.ts) >= staleMinutes;
}

function visitDayByDate(t, dateStr) {
  return (t.visit_days || []).find(d => d.date === dateStr) || null;
}
function todaysVisitDay(t) {
  return visitDayByDate(t, todayYmd());
}
function nextUpcomingVisitDay(t) {
  const today = todayYmd();
  const upcoming = (t.visit_days || []).filter(d => d.date >= today).sort((a, b) => a.date.localeCompare(b.date));
  return upcoming[0] || null;
}
function isAssignedToDay(day, name) {
  return !!(day && (day.technicians || []).includes(name));
}
function isAssignedAnyDay(t, name) {
  return (t.visit_days || []).some(d => (d.technicians || []).includes(name));
}

// Team-aware version: a technician sees a visit day if ANY technician assigned
// to that day (not just themselves) shares their team — this is what makes
// "assign by team" actually gate the technician's own view too.
function isMyTeamDay(day, session, accountsByName) {
  if (!day) return false;
  // An engineer sees only their own engineer-only visits (no technicians) on the phone pages.
  if (session.role === "engineer") return (day.technicians || []).length === 0 && day.engineer === session.name;
  const techs = day.technicians || [];
  if (techs.includes(session.name)) return true;
  if (!session.team) return false;
  return techs.some(name => {
    const acc = accountsByName[name];
    return acc && acc.team === session.team;
  });
}
function isMyTeamTicket(t, session, accountsByName) {
  return (t.visit_days || []).some(day => isMyTeamDay(day, session, accountsByName));
}
function dayStatusLabel(day) {
  if (!day) return "—";
  if (day.status === "submitted") return "Submitted";
  if (day.status === "unfinished") return "Unfinished";
  if (day.checklist && day.checklist.checklist_started_at) return "In progress";
  return "Not started";
}

// ---------- Who may do what (mirror of ACTION_ROLES in server.py — keep in sync) ----------
// The server is the one that enforces this; the UI uses canDo() only to hide buttons the
// server would refuse. admin = HOD.
const ACTION_ROLES = (() => {
  const HOD_ENG_CS = ["admin", "engineer", "cs"], HOD_CS = ["admin", "cs"], TECH_ENG = ["technician", "engineer"], HOD_ENG = ["admin", "engineer"];
  const t = {
    create_ticket: HOD_ENG_CS, assign: HOD_ENG_CS, update_ticket_details: HOD_ENG_CS, snooze: HOD_ENG_CS,
    link_events: HOD_CS, unlink_event: HOD_CS, set_day_people: HOD_CS, clear_reschedule: HOD_CS,
    reschedule: TECH_ENG,
    start_checklist: TECH_ENG, checklist_item: TECH_ENG, checklist_general: TECH_ENG, checklist_pdf: TECH_ENG, submit_checklist: TECH_ENG,
    submit_report: TECH_ENG, report_edit: TECH_ENG, // report_edit = every report_* content edit
    report_approve: HOD_ENG, report_reject: HOD_ENG,
    close: HOD_CS, early_close: HOD_CS, delete_ticket: HOD_CS,
    message: ["admin", "engineer", "cs", "technician"], mark_ticket_read: ["admin", "engineer", "cs", "technician"],
    override_report_timestamp: ["admin"],
    create_client: HOD_ENG_CS, create_calendar_event: HOD_CS, update_settings: ["admin"],
  };
  return t;
})();
function canDo(role, action) { const r = ACTION_ROLES[action]; return !r || r.includes(role); }

async function doAction(ticketId, action, payload, onDone, onError) {
  try {
    await api(`/api/tickets/${ticketId}/${action}`, "POST", payload);
    onDone && onDone();
  } catch (e) {
    onError ? onError(e.message) : showToast(e.message);
  }
}

// ---------- Sidebar shell rendering ----------
// Renders the sidebar user block (avatar, name, role, logout) into a container.
// Called by every page after requireRole() confirms a session exists.
function renderSidebarUser(session, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <div class="sidebar-user">
      <div class="avatar">${initials(session.name)}</div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:12px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${session.name}</div>
        <div class="role-caption">${ROLE_LABELS[session.role] || session.role}</div>
      </div>
      <button class="secondary logout-btn" onclick="logout()" title="Log out">${icon("logout")}</button>
    </div>
  `;
}

// ---------- Full page shell (sidebar + topbar + page title) ----------
// One definition of the nav list, used everywhere, so every page's sidebar
// stays in sync. Non-functional items are rendered visibly but inert —
// they represent real pages in the IT department's product that this
// prototype doesn't build out, rather than being hidden entirely.

// ---------- Responsive desktop shell (13 Okt) ----------
// renderShell() was built for computers only. For the roles listed here it
// also adapts to a phone: below SHELL_PHONE_QUERY the sidebar turns into a
// slide-in menu (☰ in the top bar), cards/columns stack, wide tables scroll
// sideways and buttons get bigger. On a computer nothing changes — every
// rule in style.css is scoped to "body.shell-responsive" inside a
// max-width media query.
const RESPONSIVE_SHELL_ROLES = ["engineer", "admin", "cs"];
const SHELL_PHONE_QUERY = "(max-width: 768px)";

function shellMakeResponsive() {
  try {
    document.body.classList.add("shell-responsive");
    // Desktop pages have no viewport tag in their HTML, so a phone would
    // render them at ~980px wide and zoom out. Add one if it's missing.
    if (!document.querySelector('meta[name="viewport"]')) {
      const meta = document.createElement("meta");
      meta.name = "viewport";
      meta.content = "width=device-width, initial-scale=1";
      document.head.appendChild(meta);
    }
  } catch (e) {}
}

function toggleShellSidebar(forceOpen) {
  const sidebar = document.getElementById("shellSidebar");
  const overlay = document.getElementById("shellSidebarOverlay");
  if (!sidebar || !overlay) return;
  const open = typeof forceOpen === "boolean" ? forceOpen : !sidebar.classList.contains("open");
  sidebar.classList.toggle("open", open);
  overlay.classList.toggle("open", open);
}

const NAV_ITEMS = [
  { key: "dashboard", icon: icon("grid"), label: "Dashboard", href: role => `dashboard-${role}.html` },
  { key: "tickets", icon: icon("ticket"), label: "Tickets", href: role => `${role}.html` },
  { key: "reports", icon: icon("document"), label: "Reports", href: () => "reports.html" },
  { key: "safety", icon: icon("shield"), label: "Safety Checklists", href: () => "safety-checklists.html" },
  { key: "calibration", icon: icon("wrench"), label: "Calibration Tracking", disabled: true },
  { key: "calendar", icon: icon("calendar"), label: "Calendar", href: () => "calendar.html" },
  { key: "clients", icon: icon("building"), label: "Clients & Sites", href: () => "clients.html" },
  { key: "tools", icon: icon("compass"), label: "Tools", href: () => "tools.html", roles: ["admin", "engineer", "cs"] },
  { key: "analytics", icon: icon("chart"), label: "Analytics & Reporting", href: () => "analytics.html", adminOnly: true },
  { key: "activity", icon: icon("stopwatch"), label: "Activity Log", disabled: true },
  { key: "kb", icon: icon("book"), label: "Knowledge Base", href: () => "knowledge-base.html", roles: ["admin", "engineer", "cs"] },
  { key: "users", icon: icon("users"), label: "Technician Team", href: () => "users.html", roles: ["admin", "cs"] },
];

// opts: { active, role, pageTitle, pageSubtitle, session }
// Inserts the shell at the top of <body> and leaves an empty
// <main id="pageContent"> for the calling page to fill in.
function renderShell(opts) {
  const navHtml = NAV_ITEMS.filter(item => item.roles ? item.roles.includes(opts.role) : (!item.adminOnly || opts.role === "admin")).map(item => {
    const activeCls = item.key === opts.active ? " active" : "";
    if (item.disabled) {
      return `<span class="nav-item disabled"><span class="icon">${item.icon}</span> ${item.label}</span>`;
    }
    return `<a href="${item.href(opts.role)}" class="nav-item${activeCls}"><span class="icon">${item.icon}</span> ${item.label}</a>`;
  }).join("");
  // PWA (desktop app install) is switched on per role — see PWA_DESKTOP_ROLES.
  const pwaOn = PWA_DESKTOP_ROLES.includes(opts.role);
  // Phone-friendly layout for this shell, also per role — see RESPONSIVE_SHELL_ROLES.
  const responsive = RESPONSIVE_SHELL_ROLES.includes(opts.role);
  if (responsive) shellMakeResponsive();

  document.body.insertAdjacentHTML("afterbegin", `
    <div class="app-shell">
      ${responsive ? `<div id="shellSidebarOverlay" class="shell-sidebar-overlay" onclick="toggleShellSidebar()"></div>` : ""}
      <aside class="sidebar"${responsive ? ` id="shellSidebar"` : ""}>
        <div class="sidebar-logo"><span class="mark">${icon("sparkle")}</span> ERS <span class="tag">O&amp;M</span></div>
        <nav class="sidebar-nav">${navHtml}${pwaOn ? `<a id="pwaInstallNavItem" href="#" class="nav-item" style="display:none;" onclick="pwaInstall(); return false;"><span class="icon">${icon("download")}</span> Install App</a>` : ""}</nav>
        <div class="sidebar-footer" id="sidebarUserSlot"></div>
      </aside>
      <div class="main-col">
        <header class="topbar">
          ${responsive ? `<button class="shell-menu-btn" onclick="toggleShellSidebar()" aria-label="Menu">${icon("menu")}</button>` : ""}
          <div class="topbar-title">
            <h1>${opts.pageTitle}</h1>
            <p>${opts.pageSubtitle}</p>
          </div>
          <div class="topbar-icons">${icon("moon")} ${icon("globe")} EN
            <span class="notif-bell" id="notifBell" onclick="toggleNotifDropdown(event)">
              ${icon("bell")}
              <span class="notif-badge" id="notifBadge" style="display:none;"></span>
              <div class="notif-dropdown" id="notifDropdown" style="display:none;" onclick="event.stopPropagation();"></div>
            </span>
          </div>
        </header>
        ${pwaOn ? `<div id="pwaBannerSlot" class="pwa-banner-slot pwa-banner-slot-desktop"></div>` : ""}
        <main class="content" id="pageContent"></main>
      </div>
    </div>
  `);
  renderSidebarUser(opts.session, "sidebarUserSlot");
  initNotifications(opts.session);
  if (pwaOn) {
    pwaInjectHeadTags();
    initPwa(responsive && window.matchMedia(SHELL_PHONE_QUERY).matches ? "phone" : "computer");
  }
}

// ---------- @mention notifications (badge + dropdown on the bell icon) ----------
// No real SMTP in this prototype — see queue_mock_email() in server.py. The
// badge/dropdown here is entirely computed client-side from the ticket list
// the server already returns (no new GET endpoint needed): a message is
// "unread" for the current user when they're in its `mentions` and the
// ticket's per-user high-water-mark (`mention_reads`) hasn't caught up to it
// yet (mark_ticket_read action, called when the ticket detail page opens).
function unreadMentions(tickets, myName) {
  const out = [];
  tickets.forEach(t => {
    const readUpTo = (t.mention_reads || {})[myName] || 0;
    (t.messages || []).forEach(m => {
      if ((m.mentions || []).includes(myName) && m.id > readUpTo) {
        out.push({ ticket: t, message: m });
      }
    });
  });
  out.sort((a, b) => b.message.ts.localeCompare(a.message.ts));
  return out;
}

async function initNotifications(session) {
  if (!session || session.role === "technician") return; // technicians don't use the ticket thread
  try {
    const { tickets } = await api("/api/tickets");
    const unread = unreadMentions(tickets, session.name);
    renderNotifBadge(unread);
  } catch (e) {
    // Best-effort — a failed notification check should never block the page.
  }
}

function renderNotifBadge(unread) {
  const badge = document.getElementById("notifBadge");
  const dropdown = document.getElementById("notifDropdown");
  if (!badge || !dropdown) return;
  if (unread.length) {
    badge.textContent = unread.length > 9 ? "9+" : String(unread.length);
    badge.style.display = "flex";
  } else {
    badge.style.display = "none";
  }
  dropdown.innerHTML = unread.length
    ? unread.map(({ ticket, message }) => `
        <a class="notif-dropdown-item" href="ticket-detail.html?id=${ticket.id}">
          <div class="notif-dropdown-ticket">${ticket.title}</div>
          <div class="notif-dropdown-snippet">${message.author}: ${message.text}</div>
          <div class="notif-dropdown-ts">${fmtTime(message.ts)}</div>
        </a>
      `).join("")
    : `<div class="notif-dropdown-empty">No new mentions.</div>`;
}

function toggleNotifDropdown(event) {
  // Without this, the click bubbles straight up to the document-level
  // "close on outside click" listener below, which closes the dropdown in
  // the same click — so it looked like clicking the bell did nothing.
  if (event) event.stopPropagation();
  const dropdown = document.getElementById("notifDropdown");
  if (!dropdown) return;
  dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
}
document.addEventListener("click", () => {
  const dropdown = document.getElementById("notifDropdown");
  if (dropdown) dropdown.style.display = "none";
});

// ---------- Progress bar (delivery-tracker style) ----------

const LIFECYCLE_STEPS = [
  { key: "created", label: "Created" },
  { key: "scheduled", label: "Scheduled" },
  { key: "site_visit", label: "Site visit" },
  { key: "report_drafting", label: "Report drafting" },
  { key: "engineer_review", label: "Engineer review" },
  { key: "approved", label: "Approved" },
  { key: "closed", label: "Closed" },
];

// Renders the 7-stage tracker. A normally-closed ticket shows every stage done.
// An early-closed ticket shows only the stages actually reached (derived from the
// early_close event's "from" state) as done, with a note explaining the shortcut —
// it never implies the ticket walked the full path it didn't take.
function stageCompletionInfo(ticket, fromKey, toKey) {
  const matches = ticket.event_log.filter(e => e.from === fromKey && e.to === toKey);
  return matches.length ? matches[matches.length - 1] : null;
}

// ---------- Report duration tracking (Fasa 5, Item 18-21) ----------
// "Report Started" is the first report-EDITING event in event_log, not the
// moment the ticket's state flips to report_drafting. A report object exists
// from the moment the ticket is created (see build_report() in server.py), so
// the state transition alone would make "report started" look earlier than
// when anyone actually began filling it in.
function reportStartedAt(ticket) {
  // A manual correction (Fasa 5, Item 22) always wins over the computed
  // value — that's the whole point of letting the HOD fix a wrong one.
  const override = ticket.report && ticket.report.duration_overrides && ticket.report.duration_overrides.report_started_at;
  if (override) return override.value;
  const first = (ticket.event_log || []).find(e =>
    e.action && e.action.startsWith("report_") &&
    !["report_submitted", "report_approved", "report_rejected"].includes(e.action)
  );
  return first ? first.ts : null;
}

// "Report Submitted" normally comes straight from ticket.report.submitted_at
// (set by action_submit_report on the server) — this just also honours a
// manual correction, same as reportStartedAt() above.
function reportSubmittedAt(ticket) {
  const override = ticket.report && ticket.report.duration_overrides && ticket.report.duration_overrides.report_submitted_at;
  if (override) return override.value;
  return (ticket.report && ticket.report.submitted_at) || null;
}

// Human-readable elapsed time, e.g. "45 min", "2 hrs 10 min", "3 days 4 hrs".
function formatDuration(ms) {
  if (ms == null || isNaN(ms) || ms < 0) return null;
  const mins = Math.round(ms / 60000);
  if (mins < 1) return "< 1 min";
  if (mins < 60) return `${mins} min`;
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hrs < 24) return remMins ? `${hrs} hrs ${remMins} min` : `${hrs} hrs`;
  const days = Math.floor(hrs / 24);
  const remHrs = hrs % 24;
  return remHrs ? `${days} day${days === 1 ? "" : "s"} ${remHrs} hrs` : `${days} day${days === 1 ? "" : "s"}`;
}

// Duration label for one timeline step — "how long the ticket spent at this
// stage before moving to the next one". Returns null when there's nothing
// meaningful to show yet (e.g. still in progress, or no data).
function stepDurationInfo(ticket, order, i, doneUpToIndex, isEarly) {
  const startTs = i === 0 ? ticket.created_at : (stageCompletionInfo(ticket, order[i - 1], order[i]) || {}).ts;
  if (!startTs) return null;

  // Special-cased: report drafting's real duration is Report Started (first
  // edit) to Report Submitted — not just whenever the state happened to flip —
  // since that's the number the HOD actually asked to track.
  if (order[i] === "report_drafting") {
    const submitted = reportSubmittedAt(ticket);
    if (!submitted) return null; // still drafting — nothing to report yet
    const started = reportStartedAt(ticket) || startTs;
    const text = formatDuration(new Date(submitted) - new Date(started));
    return text ? { text, highlight: true } : null;
  }

  let endTs = null;
  if (i + 1 < order.length) {
    const nextInfo = stageCompletionInfo(ticket, order[i], order[i + 1]);
    if (nextInfo) endTs = nextInfo.ts;
  }
  if (!endTs && isEarly && i === doneUpToIndex) {
    const ev = [...ticket.event_log].reverse().find(e => e.action === "early_close");
    if (ev) endTs = ev.ts;
  }
  if (!endTs) return null;
  const text = formatDuration(new Date(endTs) - new Date(startTs));
  return text ? { text, highlight: false } : null;
}

// Total ticket duration: created → closed (or "still running" while open).
function totalTicketDuration(ticket) {
  const start = ticket.created_at;
  if (!start) return null;
  // Fasa 7 audit (3 Okt) — used to fall back to ticket.updated_at for a
  // closed ticket, but updated_at keeps moving on events that can still
  // happen AFTER closure (a follow-up message, or an HOD "correct report
  // timestamp" override) — both bump updated_at without reopening the
  // ticket, which made "Total Duration" silently grow long after the
  // ticket was actually done. closure.closed_at is set once, at the exact
  // moment the ticket closes (action_close/action_early_close), and never
  // changes after — that's the correct "end" for a closed ticket's duration.
  const end = ticket.state === "closed" ? (ticket.closure && ticket.closure.closed_at) : Date.now();
  if (!end) return null;
  const text = formatDuration(new Date(end) - new Date(start));
  if (!text) return null;
  return ticket.state === "closed" ? text : `${text} (still running)`;
}

function renderProgressBar(ticket, session) {
  const order = LIFECYCLE_STEPS.map(s => s.key);
  const isEarly = ticket.state === "closed" && ticket.closure.type === "early";
  const isNormalClosed = ticket.state === "closed" && !isEarly;
  let doneUpToIndex;

  if (isEarly) {
    const ev = [...ticket.event_log].reverse().find(e => e.action === "early_close");
    doneUpToIndex = order.indexOf(ev ? ev.from : "created");
  } else if (isNormalClosed) {
    doneUpToIndex = order.length - 1;
  } else {
    doneUpToIndex = order.indexOf(ticket.state);
  }

  const stepsHtml = order.map((key, i) => {
    let cls;
    if (isEarly) {
      cls = i <= doneUpToIndex ? "done" : "future";
    } else if (i < doneUpToIndex) {
      cls = "done";
    } else if (i === doneUpToIndex) {
      cls = isNormalClosed ? "done" : "current";
    } else {
      cls = "future";
    }
    let subLabel = "";
    if (key === "created") {
      subLabel = `${ticket.event_log[0] ? ticket.event_log[0].actor : ""} \u2014 ${fmtTime(ticket.created_at)}`;
    } else if (i <= doneUpToIndex || cls === "done") {
      const info = stageCompletionInfo(ticket, order[i - 1], key);
      if (info) {
        subLabel = key === "site_visit" ? fmtTime(info.ts) : `${info.actor} \u2014 ${fmtTime(info.ts)}`;
      }
    }
    // Duration label (Fasa 5, Item 20) — only for a step the ticket has fully
    // passed through (cls === "done"); a current/future step has no "how long
    // did this take" answer yet.
    let durationHtml = "";
    if (cls === "done") {
      const dur = stepDurationInfo(ticket, order, i, doneUpToIndex, isEarly);
      if (dur) {
        durationHtml = `<div class="progress-duration${dur.highlight ? " highlight" : ""}">${dur.text}</div>`;
      }
    }
    return `<div class="progress-step ${cls}">${durationHtml}<div class="progress-dot"></div><div class="progress-label">${LIFECYCLE_STEPS[i].label}</div>${subLabel ? `<div class="progress-sublabel">${subLabel}</div>` : ""}</div>`;
  }).join("");

  const note = isEarly
    ? `<div class="small progress-early-note">${icon("warning")} Closed early at "${STATE_LABELS[order[doneUpToIndex]] || order[doneUpToIndex]}" — ${ticket.closure.reason || "no reason given"}</div>`
    : "";

  // Total duration (Fasa 5, Item 21) — shown underneath the whole timeline,
  // separate from the per-stage labels above each dot.
  const total = totalTicketDuration(ticket);
  const totalHtml = total ? `<div class="small" style="margin-top:6px;">Total duration: <b style="color:var(--text);">${total}</b></div>` : "";

  // Manual override entry point (Fasa 5, Item 22) — HOD/Admin only. Lets them
  // correct a wrong Report Started/Submitted time without touching the
  // original event_log (that stays an honest record of what happened).
  const overrideHtml = (session && session.role === "admin")
    ? `<div class="progress-override-link" onclick="openOverrideModal('${ticket.id}', '${reportStartedAt(ticket) || ""}', '${reportSubmittedAt(ticket) || ""}', '${(session.name || "").replace(/'/g, "\\'")}')">${icon("pencil")} Correct report timestamps</div>`
    : "";

  return `<div class="progress-track">${stepsHtml}</div>${note}${totalHtml}${overrideHtml}`;
}

// ---------- Manual override modal (Fasa 5, Item 22 — HOD/Admin safeguard) ----------
// Lets the HOD fix a wrong "Report Started" or "Report Submitted" time used
// for duration tracking. The original event_log is never touched — this
// layers a correction on top, with who/when/why recorded for audit.

function isoToLocalInputValue(iso) {
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function openOverrideModal(ticketId, startedIso, submittedIso, actorName) {
  const existing = document.getElementById("overrideOverlay");
  if (existing) existing.remove();
  const seedStarted = startedIso ? isoToLocalInputValue(startedIso) : "";
  const seedSubmitted = submittedIso ? isoToLocalInputValue(submittedIso) : "";
  document.body.insertAdjacentHTML("beforeend", `
    <div id="overrideOverlay" class="modal-overlay">
      <div class="modal-dialog">
        <h2><span>Correct report timestamps</span><button class="modal-close" onclick="document.getElementById('overrideOverlay').remove()">&times;</button></h2>
        <label>Report Started</label>
        <input type="datetime-local" id="overrideStarted" value="${seedStarted}">
        <label style="margin-top:10px;">Report Submitted</label>
        <input type="datetime-local" id="overrideSubmitted" value="${seedSubmitted}">
        <label style="margin-top:10px;">Reason for correction</label>
        <input type="text" id="overrideReason" placeholder="e.g. technician forgot to log the real start time">
        <button class="mobile-btn mobile-btn-primary" style="margin-top:10px;" onclick="submitOverride('${ticketId}', '${seedStarted}', '${seedSubmitted}', '${actorName.replace(/'/g, "\\'")}')">Save correction</button>
      </div>
    </div>
  `);
}

async function submitOverride(ticketId, seedStarted, seedSubmitted, actorName) {
  const reason = document.getElementById("overrideReason").value.trim();
  if (!reason) { showToast("A reason is required."); return; }

  const startedLocal = document.getElementById("overrideStarted").value;
  const submittedLocal = document.getElementById("overrideSubmitted").value;
  const changes = [];
  if (startedLocal && startedLocal !== seedStarted) changes.push(["report_started_at", new Date(startedLocal).toISOString()]);
  if (submittedLocal && submittedLocal !== seedSubmitted) changes.push(["report_submitted_at", new Date(submittedLocal).toISOString()]);
  if (!changes.length) { showToast("Nothing changed."); return; }

  try {
    for (const [field, value] of changes) {
      await api(`/api/tickets/${ticketId}/override_report_timestamp`, "POST", { actor: actorName, field, value, reason });
    }
    document.getElementById("overrideOverlay").remove();
    showToast("Timestamp(s) corrected.");
    if (typeof render === "function") render();
  } catch (e) {
    showToast(e.message || "Could not save the correction.");
  }
}

// ---------- Ticket type labels and priority ----------

const TYPE_LABELS = {
  site_survey: "Site Survey",
  servicing: "Servicing", // legacy value — kept so older tickets still show a label, no longer offered when creating a new ticket
  troubleshooting: "Troubleshooting", // legacy value — same as above
  dere: "DERE",
  residential_servicing: "Residential Servicing",
  residential_troubleshooting: "Residential Troubleshoot/Rectification",
  ci_servicing: "C&I Servicing",
  ci_troubleshooting: "C&I Troubleshoot/Rectification",
  ntp_phase_1: "NTP Phase 1",
  ntp_phase_2: "NTP Phase 2",
  ntp_phase_3: "NTP Phase 3",
  ntp_phase_4: "NTP Phase 4",
};

const PRIORITY_LABELS = { low: "Low", medium: "Medium", high: "High", critical: "Critical" };

function priorityBadge(t) {
  const p = t.priority || "medium";
  return `<span class="badge badge-priority-${p}">${PRIORITY_LABELS[p] || p}</span>`;
}

// ---------- Compact ticket list row (Tickets index pages) ----------

function ticketListRow(t) {
  return `<div class="list-row" onclick="location.href='ticket-detail.html?id=${t.id}'">
    <div class="list-row-main">
      <div class="list-row-id">${t.id}</div>
      <div class="list-row-title">${t.title}</div>
      <div class="list-row-meta">${t.client} · assignees: ${t.assignees.join(", ") || "none"}</div>
    </div>
    <div class="list-row-badges">
      ${priorityBadge(t)}
      <span class="badge badge-type">${TYPE_LABELS[t.type] || t.type}</span>
      <span class="${badgeClass(t)}">${simpleStatus(t)}</span>
    </div>
    <div class="list-row-updated">${fmtTime(t.updated_at)}</div>
  </div>`;
}

// ---------- Tickets table (Tickets index pages: admin/cs/engineer) ----------
const PRIORITY_SORT_ORDER = { low: 0, medium: 1, high: 2, critical: 3 };
const STATUS_SORT_ORDER = {
  "Open": 0,
  "In progress": 1,
  "Approved — ready to close": 2,
  "Closed": 3,
  "Closed (early)": 3,
};

let _ticketSort = { key: "updated", dir: "desc" };

function setTicketSort(key) {
  if (_ticketSort.key === key) {
    _ticketSort.dir = _ticketSort.dir === "asc" ? "desc" : "asc";
  } else {
    _ticketSort = { key, dir: key === "status" ? "asc" : "desc" };
  }
  if (typeof render === "function") render();
}

function sortTicketsForTable(tickets) {
  const { key, dir } = _ticketSort;
  const mul = dir === "asc" ? 1 : -1;
  const sorted = tickets.slice();
  sorted.sort((a, b) => {
    if (key === "priority") {
      return mul * ((PRIORITY_SORT_ORDER[a.priority || "medium"] ?? 1) - (PRIORITY_SORT_ORDER[b.priority || "medium"] ?? 1));
    }
    if (key === "status") {
      return mul * ((STATUS_SORT_ORDER[simpleStatus(a)] ?? 9) - (STATUS_SORT_ORDER[simpleStatus(b)] ?? 9));
    }
    return mul * (a.updated_at || "").localeCompare(b.updated_at || "");
  });
  return sorted;
}

function filterTicketsBySearch(tickets, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return tickets;
  return tickets.filter(t =>
    t.id.toLowerCase().includes(q) ||
    (t.client || "").toLowerCase().includes(q) ||
    (t.title || "").toLowerCase().includes(q)
  );
}

function sortArrow(key) {
  if (_ticketSort.key !== key) return `<span style="opacity:0.35;">&#8597;</span>`;
  return _ticketSort.dir === "asc" ? `<span style="color:var(--accent);">&#8593;</span>` : `<span style="color:var(--accent);">&#8595;</span>`;
}

// PIC = who's assigned to this ticket. There's no dedicated "pic" field in the
// data model, only the assignees list — so this shows everyone in that list,
// with their role prefix ("HOD - ", "CS - ", etc.) stripped for a cleaner
// read, comma-separated when there's more than one. Returns null (rendered
// as "Unassigned") when the list is empty.
function picForTicket(t) {
  const names = (t.assignees || []).map(n => n.replace(/^[A-Za-z]+ - /, ""));
  return names.length ? names.join(", ") : null;
}

function ticketTableHtml(tickets) {
  const sorted = sortTicketsForTable(tickets);
  saveTicketNavList(sorted.map(t => t.id));
  const sortableTh = (key, label) =>
    `<th style="cursor:pointer;user-select:none;" onclick="setTicketSort('${key}')">${label} ${sortArrow(key)}</th>`;

  const rows = sorted.length
    ? sorted.map(t => {
        const pic = picForTicket(t);
        return `
        <tr onclick="location.href='ticket-detail.html?id=${t.id}'">
          <td class="tt-id" style="white-space:nowrap;"><div style="font-weight:800;color:var(--accent);font-size:13px;">${t.id}</div></td>
          <td class="tt-title">
            <div style="font-weight:700;">${t.title}</div>
            <div style="font-size:12px;color:var(--muted);margin-top:2px;">${t.client}</div>
          </td>
          <td class="tt-pic">${pic
            ? `<span style="font-weight:600;">${pic}</span>`
            : `<span style="color:var(--muted);font-style:italic;">Unassigned</span>`}</td>
          <td class="tt-type"><span class="badge badge-type">${TYPE_LABELS[t.type] || t.type}</span></td>
          <td class="tt-status"><span class="${badgeClass(t)}">${simpleStatus(t)}</span></td>
          <td class="tt-priority">${priorityBadge(t)}</td>
          <td class="table-updated tt-updated">${fmtTime(t.updated_at)}</td>
        </tr>
      `;
      }).join("")
    : `<tr><td colspan="7">${emptyState("No tickets to show.", "ticket")}</td></tr>`;

  // Phone-only sort buttons (the column headers that carry the sort arrows
  // are hidden when the table turns into cards on a phone). Hidden on a
  // computer by CSS; same setTicketSort() as the headers.
  const mobileSortBtn = (key, label) =>
    `<button type="button" class="secondary${_ticketSort.key === key ? " active" : ""}" onclick="setTicketSort('${key}')">${label} ${sortArrow(key)}</button>`;

  return `
    <div class="tickets-sort-mobile">
      <span>Sort by</span>
      ${mobileSortBtn("priority", "Priority")}
      ${mobileSortBtn("updated", "Last updated")}
    </div>
    <table class="tickets-table tickets-table-cards">
      <thead><tr>
        <th style="white-space:nowrap;">Ticket No</th>
        <th>Title</th>
        <th>PIC</th>
        <th>Type</th>
        <th>Status</th>
        ${sortableTh("priority", "Priority")}
        ${sortableTh("updated", "Updated")}
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ---------- Ticket navigation context (Previous/Next on ticket-detail.html) ----------
// The Tickets table calls saveTicketNavList() after it sorts/filters, so
// ticket-detail.html can offer Previous/Next in that SAME order — not guessed
// by ticket ID. sessionStorage = temporary browser storage, cleared when the
// tab closes, so it only reflects "what I was just browsing", not forever.
function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

// ---------- Client helpers ----------

// Tickets link to a client by name (free-text field at ticket creation), not by
// client_id — so this match is case-insensitive on name. It's a known soft spot:
// a typo or near-duplicate client name would miss the match. Wiring ticket
// creation to select an existing client record would remove this fragility.
function ticketsForClient(tickets, client) {
  const norm = client.name.trim().toLowerCase();
  return tickets.filter(t => t.client.trim().toLowerCase() === norm);
}

// A ticket "has a report" once it has reached a stage where report content
// exists — this reads the same embedded report object every ticket already
// carries; there's no separate report entity behind this.
function ticketsWithReports(tickets) {
  return tickets.filter(t =>
    t.report && (t.report.psh_calc || ["engineer_review", "approved"].includes(t.state) ||
      (t.state === "closed" && t.closure.type === "resolved"))
  );
}

function reportStatusLabel(t) {
  if (t.state === "engineer_review") return "Draft";
  if (t.state === "approved" || (t.state === "closed" && t.closure.type === "resolved")) return "Approved";
  return "—";
}

function clientTypeBadge(c) {
  return c.type === "company"
    ? `<span class="badge badge-type">Company</span>`
    : `<span class="badge badge-type">Individual</span>`;
}

function clientListRow(c) {
  return `<div class="list-row" onclick="location.href='client-detail.html?id=${c.id}'">
    <div class="list-row-main">
      <div class="list-row-title">${c.name} ${clientTypeBadge(c)}</div>
      <div class="list-row-meta">${c.contact_person ? c.contact_person + " · " : ""}${c.phone || "no phone on file"}</div>
    </div>
    <div class="list-row-badges">
      <span class="small">${c.state || "—"}</span>
    </div>
    <div class="list-row-updated">${c.sites.length} site(s)</div>
  </div>`;
}

// ---------- Multi-technician checkbox list ----------
// Used both when scheduling a visit and when editing one later — a visit can
// have more than one technician assigned to it.

window.__techListsByPrefix = window.__techListsByPrefix || {};

function technicianCheckboxList(accounts, selectedNames, idPrefix) {
  const techs = accounts.filter(a => a.role === "technician");
  window.__techListsByPrefix[idPrefix] = techs;
  if (!techs.length) return emptyState("No technician accounts found.", "users");
  const teamButtons = `
    <div style="display:flex;gap:6px;margin-bottom:8px;">
      <button type="button" class="secondary" id="teamBtn-${idPrefix}-1" style="margin:0;padding:4px 10px;font-size:12px;" onclick="selectTechTeam('${idPrefix}', 'Team 1')">Select Team 1</button>
      <button type="button" class="secondary" id="teamBtn-${idPrefix}-2" style="margin:0;padding:4px 10px;font-size:12px;" onclick="selectTechTeam('${idPrefix}', 'Team 2')">Select Team 2</button>
    </div>`;
  const rows = techs.map(a => `<div class="checklist-item">
    <input type="checkbox" id="${idPrefix}-${a.id}" value="${a.name}"${(selectedNames || []).includes(a.name) ? " checked" : ""} onchange="syncTeamButtonHighlight('${idPrefix}')">
    <label for="${idPrefix}-${a.id}" style="text-transform:none;font-weight:500;color:var(--text);margin:0;">${a.name}${a.team ? ` <span class="small">(${a.team})</span>` : ""}</label>
  </div>`).join("");
  setTimeout(() => syncTeamButtonHighlight(idPrefix), 0);
  return teamButtons + rows;
}

function selectTechTeam(idPrefix, team) {
  const techs = window.__techListsByPrefix[idPrefix] || [];
  techs.forEach(a => {
    const el = document.getElementById(`${idPrefix}-${a.id}`);
    if (el) el.checked = a.team === team;
  });
  syncTeamButtonHighlight(idPrefix);
}

// Highlight butang "Select Team" yang match checkbox yang checked sekarang —
// hilang balik automatik kalau CS tambah/buang orang secara manual.
function syncTeamButtonHighlight(idPrefix) {
  const techs = window.__techListsByPrefix[idPrefix] || [];
  const checkedNames = techs
    .filter(a => { const el = document.getElementById(`${idPrefix}-${a.id}`); return el && el.checked; })
    .map(a => a.name);
  const team1Names = techs.filter(a => a.team === "Team 1").map(a => a.name);
  const team2Names = techs.filter(a => a.team === "Team 2").map(a => a.name);
  setTeamBtnState(document.getElementById(`teamBtn-${idPrefix}-1`), team1Names.length && sameNameSet(checkedNames, team1Names));
  setTeamBtnState(document.getElementById(`teamBtn-${idPrefix}-2`), team2Names.length && sameNameSet(checkedNames, team2Names));
}
function sameNameSet(a, b) {
  if (a.length !== b.length) return false;
  const s = new Set(a);
  return b.every(name => s.has(name));
}
function setTeamBtnState(btn, active) {
  if (!btn) return;
  btn.style.background = active ? "var(--accent-dark)" : "";
  btn.style.color = active ? "#fff" : "";
  btn.style.borderColor = active ? "var(--accent-dark)" : "";
}

// "Team 1"/"Team 2" hanya kalau SEMUA nama dalam list tu satu team sama —
// kalau campur atau ada yang belum ada team, pulangkan null.
function teamLabelForTechnicians(names, accountsByName) {
  if (!names || !names.length) return null;
  const teams = new Set(names.map(n => accountsByName[n] && accountsByName[n].team).filter(Boolean));
  if (teams.size === 1 && names.every(n => accountsByName[n] && accountsByName[n].team)) {
    return [...teams][0];
  }
  return null;
}

function checkedValues(idPrefix) {
  return [...document.querySelectorAll(`[id^="${idPrefix}-"]:checked`)].map(el => el.value);
}

// ---------- Calendar: date utilities (plain YYYY-MM-DD strings throughout,
// using local-time Date objects only for arithmetic, to avoid timezone drift) ----------

function pad2(n) { return String(n).padStart(2, "0"); }
function ymd(y, m, d) { return `${y}-${pad2(m)}-${pad2(d)}`; }
function parseYmd(s) {
  const [y, m, d] = s.split("-").map(Number);
  return { y, m, d, dateObj: new Date(y, m - 1, d) };
}
function addDaysStr(s, n) {
  const { dateObj } = parseYmd(s);
  dateObj.setDate(dateObj.getDate() + n);
  return ymd(dateObj.getFullYear(), dateObj.getMonth() + 1, dateObj.getDate());
}
function dayOfWeekStr(s) { return parseYmd(s).dateObj.getDay(); } // 0=Sun
function startOfWeekStr(s) { return addDaysStr(s, -dayOfWeekStr(s)); }
// "Today" follows Malaysia time (UTC+8), the same as the server's today_str() in server.py,
// so the browser and the server always agree which day it is (checklists open and close at
// midnight Malaysia time). It does not depend on the device's own time zone.
// Keep this equal to BUSINESS_UTC_OFFSET_HOURS in server.py.
const BUSINESS_UTC_OFFSET_HOURS = 8;
function todayYmd() {
  const d = new Date(Date.now() + BUSINESS_UTC_OFFSET_HOURS * 3600000);
  return ymd(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
}
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}
const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAY_NAMES = ["SUN","MON","TUE","WED","THU","FRI","SAT"];

// ---------- Lane assignment for all-day / multi-day spanning bars ----------
// Greedy interval scheduling, same idea Google Calendar uses: events sorted by
// start (then longest first), each placed in the first lane whose last event
// has already ended.

function assignLanes(events, rangeStart, rangeEnd, preferredLanes) {
  // Fasa 8 audit (5 Okt) — `preferredLanes` (optional: {eventId: lane}) lets
  // a caller carry a multi-week event's lane over from the previous week,
  // so it keeps the same row instead of visually "jumping" rows at the
  // week boundary (it used to get re-packed from scratch every week with
  // no memory of where it was before). Events with a preferred lane are
  // placed first, directly into that lane; everything else is packed
  // around them with the original first-fit logic, unchanged.
  preferredLanes = preferredLanes || {};
  const sorted = [...events].sort((a, b) =>
    a.date.localeCompare(b.date) || b.end_date.localeCompare(a.end_date));
  const continuing = sorted.filter(e => preferredLanes[e.id] !== undefined);
  const rest = sorted.filter(e => preferredLanes[e.id] === undefined);
  const laneEnds = [];
  const placed = [];
  const place = (e, lane) => {
    const s = e.date < rangeStart ? rangeStart : e.date;
    const en = e.end_date > rangeEnd ? rangeEnd : e.end_date;
    laneEnds[lane] = en;
    const startCol = dayOfWeekStr(s);
    const endCol = dayOfWeekStr(en);
    placed.push({ event: e, lane, startCol, span: endCol - startCol + 1 });
  };
  continuing.forEach(e => place(e, preferredLanes[e.id]));
  for (const e of rest) {
    const s = e.date < rangeStart ? rangeStart : e.date;
    let lane = laneEnds.findIndex(end => end !== undefined && end < s);
    if (lane === -1) lane = laneEnds.length;
    place(e, lane);
  }
  return { placed, laneCount: laneEnds.length };
}

function isSpanning(e) { return e.all_day || e.end_date !== e.date; }

// ---------- Month grid ----------
// onDayClickFn: name of a global function, called as fn('YYYY-MM-DD'), via onclick="".

function renderMonthGrid(year, month, events, onDayClickFn, onEventClickFn) {
  const first = ymd(year, month, 1);
  const gridStart = startOfWeekStr(first);
  const daysInMonth = new Date(year, month, 0).getDate();
  const last = ymd(year, month, daysInMonth);
  const gridEnd = addDaysStr(startOfWeekStr(last), 6);
  const today = todayYmd();
  const eventClick = onEventClickFn || onDayClickFn;

  let cursor = gridStart;
  let weeksHtml = "";
  let carryLanes = {}; // Fasa 8 audit (5 Okt) — see assignLanes() note above.
  while (cursor <= gridEnd) {
    const weekStart = cursor;
    const weekEnd = addDaysStr(weekStart, 6);
    const spanning = events.filter(isSpanning).filter(e => e.date <= weekEnd && e.end_date >= weekStart);
    const { placed, laneCount } = assignLanes(spanning, weekStart, weekEnd, carryLanes);
    // Carry forward the lane of any event that continues past this week,
    // so it lands in the same row next week; drop ids that end this week.
    const nextCarry = {};
    placed.forEach(p => { if (p.event.end_date > weekEnd) nextCarry[p.event.id] = p.lane; });
    carryLanes = nextCarry;
    const visibleLanes = Math.min(laneCount, 3);
    const topPad = 22 + visibleLanes * 20;

    const dayCells = [];
    for (let i = 0; i < 7; i++) {
      const d = addDaysStr(weekStart, i);
      const inMonth = parseYmd(d).m === month;
      const timed = events.filter(e => !isSpanning(e) && e.date === d);
      const overflowSpanning = placed.filter(p => p.startCol <= i && i < p.startCol + p.span && p.lane >= 3).length;
      const chipsToShow = timed.slice(0, 2);
      const overflowTimed = timed.length - chipsToShow.length;
      dayCells.push(`
        <div class="cal-daycell${inMonth ? "" : " cal-dim"}${d === today ? " cal-today" : ""}" style="grid-column:${i+1};grid-row:1;padding-top:${topPad}px;" onclick="${onDayClickFn}('${d}')">
          <div class="cal-daynum">${parseYmd(d).d}</div>
          ${chipsToShow.map(e => `<div class="cal-chip" onclick="event.stopPropagation();${eventClick}('${eventClick === onDayClickFn ? d : e.id}')" title="${e.title}${e.time ? " " + e.time + (e.end_time && e.end_time !== e.time ? "\u2013" + e.end_time : "") : ""}">${e.time ? e.time + " " : ""}${e.title}</div>`).join("")}
          ${(overflowTimed > 0 || overflowSpanning > 0) ? `<div class="cal-more">+${overflowTimed + overflowSpanning} more</div>` : ""}
        </div>`);
    }

    const barsHtml = placed.filter(p => p.lane < 3).map(p => `
      <div class="cal-bar" style="left:calc(${p.startCol} * (100% / 7) + 2px);width:calc(${p.span} * (100% / 7) - 4px);top:${22 + p.lane * 20}px;" onclick="event.stopPropagation();${eventClick}('${eventClick === onDayClickFn ? p.event.date : p.event.id}')" title="${p.event.title}">${p.event.title}</div>
    `).join("");

    weeksHtml += `<div class="cal-week">${dayCells.join("")}${barsHtml}</div>`;
    cursor = addDaysStr(cursor, 7);
  }

  return `
    <div class="cal-weekday-row">${DAY_NAMES.map(d => `<div>${d}</div>`).join("")}</div>
    <div class="cal-month-grid">${weeksHtml}</div>
  `;
}

// ---------- Week grid: an all-day banner row + an hourly grid for timed events ----------

function renderWeekGrid(weekStartStr, events, onDayClickFn, onEventClickFn) {
  const days = Array.from({ length: 7 }, (_, i) => addDaysStr(weekStartStr, i));
  const weekEnd = days[6];
  const today = todayYmd();
  const eventClick = onEventClickFn || onDayClickFn;
  const spanning = events.filter(isSpanning).filter(e => e.date <= weekEnd && e.end_date >= weekStartStr);
  const { placed, laneCount } = assignLanes(spanning, weekStartStr, weekEnd);
  const allDayHeight = Math.max(1, laneCount) * 22 + 8;

  const headerHtml = days.map(d => `
    <div class="cal-week-headcell${d === today ? " cal-today" : ""}" onclick="${onDayClickFn}('${d}')">
      <div class="cal-week-dayname">${DAY_NAMES[dayOfWeekStr(d)]}</div>
      <div class="cal-week-daynum">${parseYmd(d).d}</div>
    </div>`).join("");

  const allDayBars = placed.map(p => `
    <div class="cal-bar" style="left:calc(${p.startCol} * (100% / 7) + 2px);width:calc(${p.span} * (100% / 7) - 4px);top:${4 + p.lane * 20}px;" onclick="${eventClick}('${eventClick === onDayClickFn ? p.event.date : p.event.id}')" title="${p.event.title}">${p.event.title}</div>
  `).join("");

  const hourRows = Array.from({ length: 24 }, (_, h) => `<div class="cal-hour-label">${pad2(h)}:00</div>`).join("");
  const hourLines = Array.from({ length: 24 }, () => `<div class="cal-hour-line"></div>`).join("");

  const dayColumns = days.map((d, i) => {
    const timed = events.filter(e => !isSpanning(e) && e.date === d && e.time);
    const blocks = timed.map(e => {
      const [hh, mm] = e.time.split(":").map(Number);
      const top = (hh * 60 + (mm || 0)) / 60 * 36;
      let bottom = top + 36; // default: a minimal one-slot block when there's no end time
      if (e.end_time && e.end_time !== e.time) {
        const [ehh, emm] = e.end_time.split(":").map(Number);
        const endMinutes = ehh * 60 + (emm || 0);
        bottom = Math.max(top + 18, endMinutes / 60 * 36);
      }
      const height = bottom - top;
      const label = e.end_time && e.end_time !== e.time ? `${e.time}\u2013${e.end_time} ${e.title}` : `${e.time} ${e.title}`;
      return `<div class="cal-time-block" style="top:${top}px;height:${height}px;" onclick="${eventClick}('${eventClick === onDayClickFn ? d : e.id}')" title="${label}">${label}</div>`;
    }).join("");
    return `<div class="cal-day-column">${hourLines}${blocks}</div>`;
  }).join("");

  return `
    <div class="cal-week-header">
      <div class="cal-week-headcell cal-week-headcell-spacer"></div>
      ${headerHtml}
    </div>
    <div class="cal-allday-row" style="height:${allDayHeight}px;">
      <div class="cal-allday-label">ALL DAY</div>
      <div class="cal-allday-grid">${allDayBars}</div>
    </div>
    <div class="cal-hourgrid-wrap">
      <div class="cal-hour-labels">${hourRows}</div>
      <div class="cal-hourgrid">${dayColumns}</div>
    </div>
  `;
}

// ---------- Mobile shell (Technician-only) ----------
// A completely separate, lightweight shell from renderShell() — technicians
// use this on their phones almost exclusively, so it optimizes for large
// touch targets and a hidden-by-default nav drawer instead of a fixed sidebar.

function renderMobileShell(opts) {
  // Which of the 4 nav links should show as "active". Defaults to the
  // current page's own filename — correct for free for the 4 pages that
  // ARE a nav link themselves (dashboard-technician/checklist-list/
  // report-list/technician-calendar.html). A page reached FROM one of
  // those (job-detail.html, checklist.html, report.html) isn't itself a
  // nav link, so it passes opts.active explicitly to say which section it
  // belongs under.
  const activePage = opts.active || location.pathname.split("/").pop();
  const navLink = (href, iconName, label) =>
    `<a href="${href}" class="mobile-nav-item${href === activePage ? " active" : ""}">${icon(iconName)} ${label}</a>`;
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="mobile-app">
      <header class="mobile-topbar">
        <button class="mobile-menu-btn" onclick="toggleMobileSidebar()" aria-label="Menu">${icon("menu")}</button>
        <div class="mobile-title">${opts.pageTitle}</div>
        <div style="width:40px;"></div>
      </header>
      <div id="pwaBannerSlot" class="pwa-banner-slot"></div>
      <div id="mobileSidebarOverlay" class="mobile-sidebar-overlay" style="display:none;" onclick="toggleMobileSidebar()"></div>
      <aside id="mobileSidebar" class="mobile-sidebar-drawer">
        <div class="mobile-sidebar-header">
          <span><span class="mark">${icon("sparkle")}</span> ERS O&amp;M</span>
          <button class="mobile-sidebar-close" onclick="toggleMobileSidebar()">&times;</button>
        </div>
        <nav class="mobile-nav">
          ${opts.session.role === "engineer"
            ? navLink("dashboard-engineer.html", "home", "Dashboard")
            : navLink("dashboard-technician.html", "home", "Dashboard") +
              navLink("checklist-list.html", "clipboard", "Safety Checklist") +
              navLink("report-list.html", "document", "Report") +
              navLink("technician-calendar.html", "calendar", "Calendar")}
          <a id="pwaInstallNavItem" href="#" class="mobile-nav-item" style="display:none;" onclick="pwaInstall(); return false;">${icon("download")} Install App</a>
        </nav>
        <div class="mobile-sidebar-footer">
          <div class="mobile-sidebar-name">${opts.session.name}</div>
          <button class="secondary" onclick="logout()">Log out</button>
        </div>
      </aside>
      <main class="mobile-content" id="pageContent"></main>
    </div>
  `);
  initPwa("phone");
}

function toggleMobileSidebar() {
  const drawer = document.getElementById("mobileSidebar");
  const overlay = document.getElementById("mobileSidebarOverlay");
  const opening = !drawer.classList.contains("open");
  drawer.classList.toggle("open", opening);
  overlay.style.display = opening ? "block" : "none";
}

// ---------- PWA: installable app (13 Okt) ----------
// Lets the portal be installed as an app and opened in its own window.
//   * Technician (phone): wired into renderMobileShell(). Those pages carry
//     the PWA <head> tags in their HTML (iPhone needs them there).
//   * Desktop-shell roles listed in PWA_DESKTOP_ROLES (computer, or a phone
//     for roles that also use the responsive shell): wired into
//     renderShell(). The <head> tags are added from JS by
//     pwaInjectHeadTags() instead, so the desktop HTML pages don't need
//     editing — Chrome/Edge on a computer pick a script-added manifest up.
// Roles not switched on never register the service worker or see any of
// these banners.
//
// Three banners share one slot under the top bar (#pwaBannerSlot):
//   offline  - shown while the phone has no connection
//   update   - a new sw.js is ready; "Reload" switches over
//   install  - Android: real install prompt. iPhone: how-to text, since iOS
//              has no install prompt API.
// The install banner can be dismissed for PWA_DISMISS_DAYS; the "Install
// App" drawer item stays available regardless until the app is installed.
//
// Everything here is an add-on: any failure is swallowed so the page itself
// always works exactly as before. A service worker needs a secure context
// (https://, or http://localhost) — over plain http on a LAN IP the app
// still works as a normal website, just without install/offline support.

// Desktop-shell roles that get the install-as-app option. Add a role
// here to switch it on — nothing else needs to change for it.
const PWA_DESKTOP_ROLES = ["cs", "engineer", "admin"];

const PWA_DISMISS_KEY = "om_pwa_install_dismissed_at";
const PWA_DISMISS_DAYS = 7;

// Desktop pages don't carry the PWA <head> tags in their HTML, so add them
// here (once). Skipped if the page already has a manifest link.
function pwaInjectHeadTags() {
  try {
    if (document.querySelector('link[rel="manifest"]')) return;
    const link = document.createElement("link");
    link.rel = "manifest";
    link.href = "manifest.json";
    document.head.appendChild(link);
    if (!document.querySelector('meta[name="theme-color"]')) {
      const meta = document.createElement("meta");
      meta.name = "theme-color";
      meta.content = "#ffffff";
      document.head.appendChild(meta);
    }
  } catch (e) {}
}
let _pwaInstallEvent = null;   // Android/Chrome's deferred install prompt
let _pwaWaitingWorker = null;  // new service worker waiting to take over
let _pwaUpdating = false;      // true only after the user taps "Reload"

function pwaIsStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function pwaIsIos() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); // iPadOS reports as Mac
}

function pwaInstallDismissedRecently() {
  try {
    const at = Number(localStorage.getItem(PWA_DISMISS_KEY) || 0);
    return at && (Date.now() - at) < PWA_DISMISS_DAYS * 24 * 60 * 60 * 1000;
  } catch (e) {
    return false;
  }
}

function pwaShowBanner(kind, html) {
  const slot = document.getElementById("pwaBannerSlot");
  if (!slot) return;
  let el = document.getElementById(`pwaBanner-${kind}`);
  if (!el) {
    el = document.createElement("div");
    el.id = `pwaBanner-${kind}`;
    el.className = `pwa-banner pwa-banner-${kind}`;
    // Offline is the most urgent, so it always sits on top.
    if (kind === "offline") slot.prepend(el); else slot.appendChild(el);
  }
  el.innerHTML = html;
}

function pwaHideBanner(kind) {
  const el = document.getElementById(`pwaBanner-${kind}`);
  if (el) el.remove();
}

function pwaInstall() {
  if (_pwaInstallEvent) {
    const evt = _pwaInstallEvent;
    _pwaInstallEvent = null; // a prompt event can only be used once
    evt.prompt();
    evt.userChoice.finally(() => {
      pwaHideBanner("install");
      const nav = document.getElementById("pwaInstallNavItem");
      if (nav) nav.style.display = "none";
    });
  } else if (pwaIsIos()) {
    showToast("Tap the Share button, then “Add to Home Screen”.");
  }
}

function pwaDismissInstall() {
  try { localStorage.setItem(PWA_DISMISS_KEY, String(Date.now())); } catch (e) {}
  pwaHideBanner("install");
}

function pwaOfferUpdate(worker) {
  _pwaWaitingWorker = worker;
  pwaShowBanner("update", `
    <span class="pwa-banner-text">${icon("reschedule")} A new version is available.</span>
    <button type="button" class="pwa-banner-btn" onclick="pwaApplyUpdate()">Reload</button>`);
}

function pwaApplyUpdate() {
  if (!_pwaWaitingWorker) { location.reload(); return; }
  _pwaUpdating = true;
  _pwaWaitingWorker.postMessage({ type: "SKIP_WAITING" });
  // The page reloads itself on "controllerchange" (see initPwa).
}

function initPwa(device) {
  try {
    // 1) Service worker (install + offline page + update detection).
    if ("serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("sw.js").then(reg => {
        if (reg.waiting && navigator.serviceWorker.controller) pwaOfferUpdate(reg.waiting);
        reg.addEventListener("updatefound", () => {
          const incoming = reg.installing;
          if (!incoming) return;
          incoming.addEventListener("statechange", () => {
            // Only an UPDATE (an older worker already in control) gets the
            // banner — the very first install needs no reload at all.
            if (incoming.state === "installed" && navigator.serviceWorker.controller) pwaOfferUpdate(incoming);
          });
        });
      }).catch(() => {});
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        // Reload only when the user asked for the update, never on the
        // first-ever install (clients.claim() also fires this event).
        if (_pwaUpdating) location.reload();
      });
    }

    // 2) Offline banner.
    const syncOnline = () => {
      if (navigator.onLine) pwaHideBanner("offline");
      else pwaShowBanner("offline", `<span class="pwa-banner-text">${icon("warning")} No internet connection — changes can't be saved until you're back online.</span>`);
    };
    window.addEventListener("online", syncOnline);
    window.addEventListener("offline", syncOnline);
    syncOnline();

    // 3) Install prompt — nothing to offer once already running as the app.
    if (pwaIsStandalone()) return;
    const installBanner = text => `
      <span class="pwa-banner-text">${icon("download")} ${text}</span>
      <span class="pwa-banner-actions">
        ${_pwaInstallEvent ? `<button type="button" class="pwa-banner-btn" onclick="pwaInstall()">Install</button>` : ""}
        <button type="button" class="pwa-banner-btn pwa-banner-btn-ghost" onclick="pwaDismissInstall()">Later</button>
      </span>`;

    window.addEventListener("beforeinstallprompt", e => {
      e.preventDefault(); // show our own banner instead of Chrome's mini-bar
      _pwaInstallEvent = e;
      const nav = document.getElementById("pwaInstallNavItem");
      if (nav) nav.style.display = "";
      if (!pwaInstallDismissedRecently()) pwaShowBanner("install", installBanner(device === "computer"
        ? "Install ERS O&M as an app on this computer."
        : "Install the ERS O&M app on this phone."));
    });
    window.addEventListener("appinstalled", () => {
      _pwaInstallEvent = null;
      pwaHideBanner("install");
      const nav = document.getElementById("pwaInstallNavItem");
      if (nav) nav.style.display = "none";
    });

    if (pwaIsIos()) {
      const nav = document.getElementById("pwaInstallNavItem");
      if (nav) nav.style.display = "";
      if (!pwaInstallDismissedRecently()) {
        pwaShowBanner("install", installBanner("Install this app: tap Share, then “Add to Home Screen”."));
      }
    }
  } catch (e) {
    // PWA extras must never break the page.
  }
}

// ---------- Checklist stage/status helpers, shared by the technician
// checklist wizard and any admin-facing summaries ----------

const CHECKLIST_STAGE_LABELS = { pre: "Before work", during: "During work", post: "After work" };
const CHECKLIST_STAGE_CLASS = { pre: "stage-pre", during: "stage-during", post: "stage-post" };
const CHECKLIST_STATUS_LABELS = { pass: "Pass", fail: "Fail", na: "N/A" };

// Two Safety Checklist question sets exist server-side (server.py's
// CHECKLIST_TEMPLATE / CHECKLIST_TEMPLATE_CI, picked per ticket type by
// checklist_template_key): the 20-item residential form for Residential
// Servicing/Troubleshoot, and the 22-item C&I form (PTW, LOTO, substation
// safety, etc.) for C&I Servicing/Troubleshoot, DERE, and Site Survey.
// NTP Phase 1-4 don't use a checklist at all — planned as a single PDF
// upload instead (not built yet), so they still get a "Coming soon"
// placeholder wherever a checklist link appears.
const SAFETY_CHECKLIST_TYPES = [
  "residential_servicing", "residential_troubleshooting",
  "ci_servicing", "ci_troubleshooting", "dere", "site_survey",
  "ntp_phase_1", "ntp_phase_2", "ntp_phase_3", "ntp_phase_4",
];
function isSafetyChecklistType(type) { return SAFETY_CHECKLIST_TYPES.includes(type); }

// Renders **bold** markers from the checklist template as real <strong> tags.
function renderChecklistText(text) {
  return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function checklistStatusChipClass(status) {
  if (status === "pass") return "chip-pass";
  if (status === "fail") return "chip-fail";
  if (status === "na") return "chip-na";
  return "chip-pending";
}

// ---------- Shared job-picker overlay (Technician dashboard utility buttons) ----------
// tickets: array of {id, client, type, ...}. onPick(ticketId) is called once confirmed.

function openJobPicker(title, tickets, onPickFnName) {
  const existing = document.getElementById("jobPickerOverlay");
  if (existing) existing.remove();
  document.body.insertAdjacentHTML("beforeend", `
    <div id="jobPickerOverlay" class="modal-overlay">
      <div class="modal-dialog">
        <h2><span>${title}</span><button class="modal-close" onclick="document.getElementById('jobPickerOverlay').remove()">&times;</button></h2>
        <label>Select a job</label>
        <select id="jobPickerSelect">${tickets.length ? tickets.map(t => `<option value="${t.id}">${t.client} — ${TYPE_LABELS[t.type] || t.type}</option>`).join("") : `<option value="">No jobs available</option>`}</select>
        <button class="mobile-btn mobile-btn-primary" style="margin-top:10px;" onclick="${onPickFnName}(document.getElementById('jobPickerSelect').value)">Confirm</button>
      </div>
    </div>
  `);
}

// ---------- Report media: pseudo-photo generation + shared category list ----------
// This demo has no real camera capture, so a tap generates a small SVG "photo"
// instead — a colored card with the category and time on it. Deterministic
// enough to look consistent, cheap enough to need no storage beyond the label
// string already used everywhere else in this project's mock-media pattern.

const REPORT_MEDIA_CATEGORIES = [
  ["pv_before", "PV Modules \u2013 Before", "#2563eb"],
  ["pv_after", "PV Modules \u2013 After", "#16a34a"],
  ["inverter", "Inverter + Serial No.", "#d97706"],
  ["ac_photo", "AC Photo", "#7c3aed"],
  ["dc_photo", "DC Photo", "#0d9488"],
  ["fit_meter", "FiT Meters & Others", "#db2777"],
];

function escapeXml(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function pseudoPhotoLabel(categoryLabel) {
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return `${categoryLabel} \u2014 ${time}`;
}

function pseudoPhotoDataUri(label, color) {
  const parts = label.split(" \u2014 ");
  const title = escapeXml(parts[0] || label);
  const time = escapeXml(parts[1] || "");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 220">
    <rect width="300" height="220" fill="${color}"/>
    <circle cx="150" cy="82" r="36" fill="white" opacity="0.22"/>
    <circle cx="150" cy="82" r="21" fill="white" opacity="0.32"/>
    <circle cx="150" cy="82" r="9" fill="white" opacity="0.5"/>
    <text x="150" y="168" text-anchor="middle" fill="white" font-family="sans-serif" font-size="15" font-weight="700">${title}</text>
    <text x="150" y="190" text-anchor="middle" fill="white" font-family="sans-serif" font-size="11" opacity="0.85">${time}</text>
  </svg>`;
  return "data:image/svg+xml," + encodeURIComponent(svg);
}

function mediaCategoryMeta(key) {
  return REPORT_MEDIA_CATEGORIES.find(c => c[0] === key) || [key, key, "#6b7280"];
}

// ---------- Toast: brief on-screen confirmation that an action actually happened ----------

function showToast(message) {
  const existing = document.getElementById("appToast");
  if (existing) existing.remove();
  document.body.insertAdjacentHTML("beforeend", `<div id="appToast" class="app-toast">${message}</div>`);
  const el = document.getElementById("appToast");
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => { if (el) el.classList.remove("show"); }, 1600);
  setTimeout(() => { if (el && el.parentNode) el.remove(); }, 2000);
}

// ---------- Analytics: completeness + per-role summaries ----------
// Pure functions over the full ticket/client/account lists already fetched
// elsewhere — no new endpoint, computed client-side same as the rest of this
// demo. Deliberately never produces a single ranked "score" per person; see
// the analytics page for why.

const TICKET_COMPLETENESS_FIELDS = [
  ["Site / Address", t => t.site],
  ["Panels", t => t.equipment.panels],
  ["Inverter Brand", t => t.equipment.inverter_brand],
  ["Inverter Model", t => t.equipment.inverter_model],
  ["NEMCD Ref", t => t.equipment.nemcd_ref],
  ["DLP End Date", t => t.commercial.dlp_end_date],
  ["SO Number", t => t.additional.so_number],
  ["Premium Care Status", t => t.additional.premium_care_status],
  ["System Size", t => t.additional.system_size],
  ["Assigned Team", t => t.additional.assigned_team],
  ["Contact Phone", t => t.additional.contact_phone],
  ["Client Remarks", t => t.additional.client_remarks],
];
const CLIENT_COMPLETENESS_FIELDS = [
  ["Contact Person", c => c.contact_person], ["Phone", c => c.phone], ["Email", c => c.email],
  ["Address", c => c.address], ["City", c => c.city], ["State", c => c.state], ["Postcode", c => c.postcode],
];

function fieldCompleteness(obj, fieldDefs) {
  const missing = fieldDefs.filter(([, get]) => !(get(obj) || "").toString().trim()).map(([label]) => label);
  const filled = fieldDefs.length - missing.length;
  return { filled, total: fieldDefs.length, pct: fieldDefs.length ? Math.round((filled / fieldDefs.length) * 100) : 100, missing };
}
function ticketCompleteness(t) { return fieldCompleteness(t, TICKET_COMPLETENESS_FIELDS); }
function clientCompleteness(c) { return fieldCompleteness(c, CLIENT_COMPLETENESS_FIELDS); }

function daysAgoStr(n) { return addDaysStr(todayYmd(), -n); }
function withinLastNDays(dateStr, n) { return dateStr >= daysAgoStr(n) && dateStr <= todayYmd(); }
function tsWithinLastNDays(ts, n) { return withinLastNDays(ts.slice(0, 10), n); }

function hoursBetween(tsFrom, tsTo) { return (new Date(tsTo) - new Date(tsFrom)) / 3600000; }

function avg(nums) { return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null; }
function fmtHours(h) {
  if (h === null) return "—";
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(1)} h`;
  return `${(h / 24).toFixed(1)} d`;
}

// ---- CS ----
function fieldGapFrequency(items, fieldDefs) {
  const counts = {};
  fieldDefs.forEach(([label]) => { counts[label] = 0; });
  items.forEach(item => {
    fieldCompleteness(item, fieldDefs).missing.forEach(label => { counts[label] = (counts[label] || 0) + 1; });
  });
  return Object.entries(counts).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]);
}

function segmentedCompletenessBar(item, fieldDefs) {
  return `<div class="seg-bar">${fieldDefs.map(([label, get]) => {
    const filled = !!(get(item) || "").toString().trim();
    return `<div class="seg-cell ${filled ? "seg-filled" : "seg-empty"}" title="${label}: ${filled ? "filled" : "missing"}"></div>`;
  }).join("")}</div>`;
}

function csSummary(name, tickets, clients, periodDays) {
  const created = tickets.filter(t => t.event_log[0] && t.event_log[0].actor === name);
  const createdInPeriod = created.filter(t => tsWithinLastNDays(t.created_at, periodDays));
  const unscheduled = created.filter(t => t.state === "created");
  const scheduleTimes = [];
  created.forEach(t => {
    const schedEvent = t.event_log.find(e => e.from === "created" && e.to === "scheduled");
    if (schedEvent) scheduleTimes.push(hoursBetween(t.created_at, schedEvent.ts));
  });
  const myClients = clients.filter(c => c.created_by === name);
  return {
    name,
    createdInPeriod: createdInPeriod.length,
    unscheduledCount: unscheduled.length,
    avgTimeToScheduleHrs: avg(scheduleTimes),
    ticketCompletenessPct: avg(created.map(t => ticketCompleteness(t).pct)),
    ticketsWithGaps: created.filter(t => ticketCompleteness(t).pct < 100),
    clientCompletenessPct: myClients.length ? avg(myClients.map(c => clientCompleteness(c).pct)) : null,
    clientsWithGaps: myClients.filter(c => clientCompleteness(c).pct < 100),
  };
}

// ---- Engineer ----
function engineerSummary(name, tickets, periodDays) {
  const acted = [];
  tickets.forEach(t => t.event_log.forEach(e => {
    if ((e.action === "report_approved" || e.action === "report_rejected") && e.actor === name) acted.push({ t, e });
  }));
  const actedInPeriod = acted.filter(({ e }) => tsWithinLastNDays(e.ts, periodDays));
  const turnarounds = [];
  actedInPeriod.forEach(({ t, e }) => {
    const submitEvent = [...t.event_log].reverse().find(ev => ev.action === "report_submitted" && ev.ts < e.ts);
    if (submitEvent) turnarounds.push(hoursBetween(submitEvent.ts, e.ts));
  });
  const queue = tickets.filter(t => t.state === "engineer_review" &&
    (t.default_engineer === name || (t.visit_days || []).some(d => d.engineer === name)));
  const byType = {};
  actedInPeriod.forEach(({ t }) => { byType[t.type] = (byType[t.type] || 0) + 1; });
  return {
    name, reviewedInPeriod: actedInPeriod.length, byType,
    approvedCount: actedInPeriod.filter(({ e }) => e.action === "report_approved").length,
    rejectedCount: actedInPeriod.filter(({ e }) => e.action === "report_rejected").length,
    currentQueue: queue.length,
    avgTurnaroundHrs: avg(turnarounds),
  };
}

// ---- Technician ----
function technicianSummary(name, tickets, periodDays) {
  const myDays = [];
  tickets.forEach(t => (t.visit_days || []).forEach(d => { if ((d.technicians || []).includes(name)) myDays.push({ t, d }); }));
  const completedInPeriod = myDays.filter(({ d }) => d.status === "submitted" && d.checklist.checklist_completed_at && tsWithinLastNDays(d.checklist.checklist_completed_at, periodDays));
  const unfinishedInPeriod = myDays.filter(({ d }) => d.status === "unfinished" && withinLastNDays(d.date, periodDays));
  const upcoming = myDays.filter(({ d }) => d.date >= todayYmd());
  const byType = {};
  completedInPeriod.forEach(({ t }) => { byType[t.type] = (byType[t.type] || 0) + 1; });
  let failItems = 0, failWithMedia = 0;
  completedInPeriod.forEach(({ d }) => d.checklist.items.forEach(i => {
    if (i.status === "fail") { failItems++; if (i.attachments && i.attachments.length) failWithMedia++; }
  }));
  return {
    name, completedInPeriod: completedInPeriod.length, byType,
    unfinishedInPeriod: unfinishedInPeriod.length,
    upcomingCount: upcoming.length,
    failItems, failWithMedia,
    documentationRatePct: failItems ? Math.round((failWithMedia / failItems) * 100) : null,
  };
}

// ---- Operational KPIs (HOD request, 14 Oct) ----
// ASSUMPTION (to be confirmed by HOD): tickets have no "preventive/corrective"
// field, so we map by type — any *servicing* type = Preventive, any
// *troubleshooting* type = Corrective, and DERE = Corrective (confirmed by
// user, 14 Oct). Site Survey and NTP are not maintenance work, so they are
// left out of this split.
function maintenanceKind(type) {
  if (/servicing/.test(type)) return "preventive";
  if (/troubleshoot/.test(type) || type === "dere") return "corrective";
  return null;
}
const SLA_ENGINEER_REVIEW_HRS = 72; // same 3-day limit used on the dashboards
const SLA_CS_CLOSE_HRS = 48;        // same 2-day limit used on the dashboards

function kpiSummary(tickets, periodDays) {
  // Preventive vs Corrective — tickets opened in the period
  let preventive = 0, corrective = 0;
  tickets.forEach(t => {
    if (!tsWithinLastNDays(t.created_at, periodDays)) return;
    const k = maintenanceKind(t.type);
    if (k === "preventive") preventive++; else if (k === "corrective") corrective++;
  });
  const maintTotal = preventive + corrective;

  // Internal SLA compliance. Each measured step is one report_submitted ->
  // report_approved/rejected (limit 72h) or report_approved -> close (limit 48h).
  // Steps are counted when they finished in the period. Steps still waiting past
  // their limit count as breaches. Early closures have no review step, so skipped.
  let engOk = 0, engTotal = 0, csOk = 0, csTotal = 0;
  const now = Date.now();
  tickets.forEach(t => {
    const log = t.event_log || [];
    log.forEach((e, i) => {
      if (e.action === "report_submitted") {
        const next = log.slice(i + 1).find(x => x.action === "report_approved" || x.action === "report_rejected");
        if (next) {
          if (!tsWithinLastNDays(next.ts, periodDays)) return;
          engTotal++; if (hoursBetween(e.ts, next.ts) <= SLA_ENGINEER_REVIEW_HRS) engOk++;
        } else if (t.state === "engineer_review" && tsWithinLastNDays(e.ts, periodDays)) {
          const waited = (now - new Date(e.ts)) / 3600000;
          if (waited > SLA_ENGINEER_REVIEW_HRS) engTotal++; // overdue = breach; not yet due is left out
        }
      } else if (e.action === "report_approved") {
        const next = log.slice(i + 1).find(x => x.action === "close");
        if (next) {
          if (!tsWithinLastNDays(next.ts, periodDays)) return;
          csTotal++; if (hoursBetween(e.ts, next.ts) <= SLA_CS_CLOSE_HRS) csOk++;
        } else if (t.state === "approved" && tsWithinLastNDays(e.ts, periodDays)) {
          const waited = (now - new Date(e.ts)) / 3600000;
          if (waited > SLA_CS_CLOSE_HRS) csTotal++;
        }
      }
    });
  });
  const pct = (a, b) => b ? (a / b) * 100 : null;
  return {
    preventive, corrective, maintTotal,
    preventivePct: pct(preventive, maintTotal), correctivePct: pct(corrective, maintTotal),
    engOk, engTotal, engPct: pct(engOk, engTotal),
    csOk, csTotal, csPct: pct(csOk, csTotal),
    slaPct: pct(engOk + csOk, engTotal + csTotal), slaTotal: engTotal + csTotal,
  };
}

// ---- Department rollup ----
function departmentSummary(tickets, periodDays) {
  const byType = {}, byState = {};
  tickets.forEach(t => {
    byType[t.type] = (byType[t.type] || 0) + 1;
    byState[t.state] = (byState[t.state] || 0) + 1;
  });
  const allDays = [];
  tickets.forEach(t => (t.visit_days || []).forEach(d => { if (withinLastNDays(d.date, periodDays)) allDays.push(d); }));
  const submitted = allDays.filter(d => d.status === "submitted").length;
  const unfinished = allDays.filter(d => d.status === "unfinished").length;
  const resolvedDays = submitted + unfinished;
  const stagePairs = [["created", "scheduled"], ["scheduled", "site_visit"], ["site_visit", "report_drafting"], ["report_drafting", "engineer_review"], ["engineer_review", "approved"]];
  const stageTurnarounds = stagePairs.map(([from, to]) => {
    const durations = [];
    tickets.forEach(t => {
      const ev = t.event_log.find(e => e.from === from && e.to === to);
      if (ev && tsWithinLastNDays(ev.ts, periodDays)) {
        const startEv = [...t.event_log].filter(e => e.to === from).pop();
        if (startEv) durations.push(hoursBetween(startEv.ts, ev.ts));
      }
    });
    return { from, to, avgHrs: avg(durations), count: durations.length };
  });

  // Created / closed in period, by type
  const createdInPeriod = tickets.filter(t => tsWithinLastNDays(t.created_at, periodDays));
  const createdByType = {};
  createdInPeriod.forEach(t => { createdByType[t.type] = (createdByType[t.type] || 0) + 1; });
  const mostOpenedType = Object.entries(createdByType).sort((a, b) => b[1] - a[1])[0] || null;
  const closedInPeriod = tickets.filter(t => t.state === "closed" && t.closure.closed_at && tsWithinLastNDays(t.closure.closed_at, periodDays));

  // Average lifetime, excluding early closures
  const lifetimesHrs = tickets
    .filter(t => t.state === "closed" && t.closure.type !== "early" && t.closure.closed_at)
    .map(t => hoursBetween(t.created_at, t.closure.closed_at));

  // Backlog trend: open-ticket count at each of the last periodDays days
  const backlogTrend = [];
  const openThenCount = (asOf) => tickets.filter(t => {
    if (t.created_at.slice(0, 10) > asOf) return false;
    if (t.state !== "closed") return true;
    return !t.closure.closed_at || t.closure.closed_at.slice(0, 10) > asOf;
  }).length;
  for (let i = periodDays - 1; i >= 0; i -= Math.max(1, Math.floor(periodDays / 10))) {
    const asOf = daysAgoStr(i);
    backlogTrend.push({ date: asOf, count: openThenCount(asOf) });
  }
  // Fasa 8 audit (5 Okt) — the step above (floor(periodDays/10), e.g. 3 for
  // the default 30-day period) steps past 0 without ever landing on it, so
  // the chart's right-most point was always a few days stale, never "today".
  // Make sure today is always the last point sampled.
  const todayStr = daysAgoStr(0);
  if (!backlogTrend.length || backlogTrend[backlogTrend.length - 1].date !== todayStr) {
    backlogTrend.push({ date: todayStr, count: openThenCount(todayStr) });
  }

  // Snooze reasons, grouped (from event_log 'snooze' actions with a note)
  const snoozeReasons = {};
  tickets.forEach(t => t.event_log.forEach(e => {
    if (e.action === "snooze" && e.note) snoozeReasons[e.note] = (snoozeReasons[e.note] || 0) + 1;
  }));

  // Department-wide report rejection rate: rejections vs (rejections + approvals)
  let rejected = 0, approved = 0;
  tickets.forEach(t => t.event_log.forEach(e => {
    if (e.action === "report_rejected") rejected++;
    if (e.action === "report_approved") approved++;
  }));
  const reportRejectionRatePct = (rejected + approved) ? Math.round((rejected / (rejected + approved)) * 100) : null;

  return {
    totalTickets: tickets.length, byType, byState,
    onTimeRatePct: resolvedDays ? Math.round((submitted / resolvedDays) * 100) : null,
    unfinishedCount: unfinished, submittedCount: submitted,
    stageTurnarounds,
    createdByType, createdInPeriodCount: createdInPeriod.length, mostOpenedType,
    closedInPeriodCount: closedInPeriod.length,
    avgLifetimeHrs: avg(lifetimesHrs), lifetimeSampleCount: lifetimesHrs.length,
    backlogTrend, snoozeReasons, reportRejectionRatePct, rejectedCount: rejected, approvedCount: approved,
  };
}

function ticketAgeDistribution(tickets) {
  const buckets = [
    { label: "0-1d", maxHrs: 24 }, { label: "1-3d", maxHrs: 72 }, { label: "3-7d", maxHrs: 168 },
    { label: "7-14d", maxHrs: 336 }, { label: "14-30d", maxHrs: 720 }, { label: "30d+", maxHrs: Infinity },
  ];
  const resolved = tickets.filter(t => t.state === "closed" && t.closure.type !== "early" && t.closure.closed_at);
  const early = tickets.filter(t => t.state === "closed" && t.closure.type === "early" && t.closure.closed_at);
  function bucketCounts(list) {
    const counts = buckets.map(() => 0);
    list.forEach(t => {
      const hrs = hoursBetween(t.created_at, t.closure.closed_at);
      const idx = buckets.findIndex(b => hrs <= b.maxHrs);
      counts[idx >= 0 ? idx : buckets.length - 1]++;
    });
    return counts;
  }
  // Outliers: normally-resolved tickets that took much longer than typical (>2x the average) —
  // a simple, explainable rule rather than a formal statistical test, appropriate for this scale of data.
  const lifetimes = resolved.map(t => ({ t, hrs: hoursBetween(t.created_at, t.closure.closed_at) }));
  const meanHrs = avg(lifetimes.map(x => x.hrs)) || 0;
  const outliers = lifetimes.filter(x => x.hrs > meanHrs * 2).sort((a, b) => b.hrs - a.hrs);
  return {
    labels: buckets.map(b => b.label),
    resolvedCounts: bucketCounts(resolved), earlyCounts: bucketCounts(early),
    meanHrs, outliers,
  };
}

function failurePatternSummary(tickets) {
  const counts = {};
  tickets.forEach(t => (t.visit_days || []).forEach(d => d.checklist.items.forEach(it => {
    if (it.status === "fail") counts[it.section] = (counts[it.section] || 0) + 1;
  })));
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}

function topClientsByVolume(tickets, n) {
  const counts = {};
  tickets.forEach(t => { counts[t.client] = (counts[t.client] || 0) + 1; });
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  return {
    top: sorted.slice(0, n),
    repeatCount: sorted.filter(([, c]) => c > 1).length,
    oneTimeCount: sorted.filter(([, c]) => c === 1).length,
  };
}

function currentlySnoozedSummary(tickets) {
  const snoozed = tickets.filter(t => t.snooze_until && t.snoozed_at);
  const totalHrs = snoozed.reduce((sum, t) => sum + hoursBetween(t.snoozed_at, new Date().toISOString()), 0);
  return { count: snoozed.length, totalHrs, tickets: snoozed };
}

function clientActivitySummary(clients, tickets, periodDays) {
  const monthStart = todayYmd().slice(0, 7) + "-01";
  const today = todayYmd();
  return clients.map(c => {
    const myTickets = tickets.filter(t => t.client === c.name);
    const activeDates = new Set();
    myTickets.forEach(t => {
      const start = t.created_at.slice(0, 10);
      const end = t.state === "closed" && t.closure.closed_at ? t.closure.closed_at.slice(0, 10) : today;
      let d = start < monthStart ? monthStart : start;
      const stop = end < today ? end : today;
      while (d <= stop) { activeDates.add(d); d = addDaysStr(d, 1); }
    });
    return { client: c, ticketCount: myTickets.length, activeDaysThisMonth: activeDates.size };
  }).sort((a, b) => b.activeDaysThisMonth - a.activeDaysThisMonth);
}

// ---------- Hand-rolled SVG charts ----------
// This project has no external dependencies anywhere (stdlib-only server,
// zero CDN scripts) — charts are built the same way, plain SVG generated
// from data, not a charting library. Hover tooltips use native SVG <title>
// elements, which every browser shows for free with no JS.

const CHART_PALETTE = ["#2563eb", "#16a34a", "#d97706", "#7c3aed", "#0d9488", "#db2777", "#64748b", "#0891b2"];

function svgDonutChart(segments, opts) {
  opts = opts || {};
  const size = opts.size || 180;
  const stroke = opts.stroke || 26;
  const r = (size - stroke) / 2;
  const cx = size / 2, cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  let offset = 0;
  const arcs = total === 0
    ? `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#e5e7eb" stroke-width="${stroke}"/>`
    : segments.filter(seg => seg.value > 0).map((seg, i) => {
        const frac = seg.value / total;
        const dash = frac * circumference;
        const gap = circumference - dash;
        const rotation = (offset / total) * 360 - 90;
        offset += seg.value;
        const color = seg.color || CHART_PALETTE[i % CHART_PALETTE.length];
        return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}"
          stroke-dasharray="${dash} ${gap}" transform="rotate(${rotation} ${cx} ${cy})">
          <title>${seg.label}: ${seg.value}${opts.pctLabels ? ` (${Math.round(frac*100)}%)` : ""}</title>
        </circle>`;
      }).join("");
  const centerLabel = opts.centerLabel !== undefined ? opts.centerLabel : total;
  return `
    <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" style="overflow:visible;">
      ${arcs}
      <text x="${cx}" y="${cy - (opts.centerSubLabel ? 6 : 0)}" text-anchor="middle" font-size="26" font-weight="800" fill="var(--text)">${centerLabel}</text>
      ${opts.centerSubLabel ? `<text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="11" fill="var(--muted)">${opts.centerSubLabel}</text>` : ""}
    </svg>
  `;
}

function chartLegend(segments) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  return `<div class="chart-legend">${segments.map((seg, i) => `
    <div class="chart-legend-row">
      <span class="chart-legend-swatch" style="background:${seg.color || CHART_PALETTE[i % CHART_PALETTE.length]};"></span>
      <span class="chart-legend-label">${seg.label}</span>
      <span class="chart-legend-value">${seg.value}${total ? ` (${Math.round(seg.value/total*100)}%)` : ""}</span>
    </div>`).join("")}</div>`;
}

function svgBarChart(groups, opts) {
  opts = opts || {};
  const width = opts.width || 320, height = opts.height || 160;
  const padBottom = 26, padTop = 10, padSide = 8;
  const plotH = height - padBottom - padTop;
  const maxVal = Math.max(1, ...groups.flatMap(g => g.bars.map(b => b.value)));
  const groupW = (width - padSide * 2) / groups.length;
  const barsHtml = groups.map((g, gi) => {
    const n = g.bars.length;
    const barW = Math.min(30, groupW / (n + 1));
    const gStart = padSide + gi * groupW + (groupW - barW * n - (n - 1) * 4) / 2;
    const bars = g.bars.map((b, bi) => {
      const h = (b.value / maxVal) * plotH;
      const x = gStart + bi * (barW + 4);
      const y = padTop + plotH - h;
      const color = b.color || CHART_PALETTE[bi % CHART_PALETTE.length];
      return `<rect x="${x}" y="${y}" width="${barW}" height="${Math.max(1, h)}" fill="${color}" rx="3"><title>${g.label} \u2013 ${b.label}: ${b.value}</title></rect>`;
    }).join("");
    return `${bars}<text x="${padSide + gi * groupW + groupW / 2}" y="${height - 8}" text-anchor="middle" font-size="10" fill="var(--muted)">${g.label}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">
    <line x1="${padSide}" y1="${padTop + plotH}" x2="${width - padSide}" y2="${padTop + plotH}" stroke="#e5e7eb"/>
    ${barsHtml}
  </svg>`;
}

function svgLineChart(series, xLabels, opts) {
  opts = opts || {};
  const width = opts.width || 340, height = opts.height || 160;
  const padLeft = 30, padBottom = 22, padTop = 12, padRight = 10;
  const plotW = width - padLeft - padRight, plotH = height - padTop - padBottom;
  const maxVal = Math.max(1, ...series.flatMap(s => s.values));
  const n = xLabels.length;
  const xAt = i => padLeft + (n <= 1 ? 0 : (i / (n - 1)) * plotW);
  const yAt = v => padTop + plotH - (v / maxVal) * plotH;
  const gridLines = [0, 0.5, 1].map(f => `<line x1="${padLeft}" y1="${padTop + plotH * (1 - f)}" x2="${width - padRight}" y2="${padTop + plotH * (1 - f)}" stroke="#f1f5f9"/>`).join("");
  const linesHtml = series.map((s, si) => {
    const color = s.color || CHART_PALETTE[si % CHART_PALETTE.length];
    const points = s.values.map((v, i) => `${xAt(i)},${yAt(v)}`).join(" ");
    const dots = s.values.map((v, i) => `<circle cx="${xAt(i)}" cy="${yAt(v)}" r="3" fill="${color}"><title>${s.label} \u2013 ${xLabels[i]}: ${v}</title></circle>`).join("");
    return `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5"/>${dots}`;
  }).join("");
  const xLabelsHtml = xLabels.map((l, i) => i % Math.ceil(n / 6 || 1) === 0 ? `<text x="${xAt(i)}" y="${height - 6}" text-anchor="middle" font-size="9" fill="var(--muted)">${l}</text>` : "").join("");
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">${gridLines}${linesHtml}${xLabelsHtml}</svg>`;
}

function progressBar(pct, opts) {
  opts = opts || {};
  pct = Math.round(pct * 10) / 10;
  const color = pct >= 80 ? "#16a34a" : pct >= 50 ? "#d97706" : "#dc2626";
  return `<div class="pbar-track" ${opts.onclick ? `onclick="${opts.onclick}" style="cursor:pointer;"` : ""}>
    <div class="pbar-fill" style="width:${pct}%;background:${color};"></div>
    <div class="pbar-label">${pct}%</div>
  </div>`;
}