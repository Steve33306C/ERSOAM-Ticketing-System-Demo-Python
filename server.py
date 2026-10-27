#!/usr/bin/env python3
"""
O&M Ticketing Demo — local prototype server.

PROTOTYPE, NOT PRODUCTION:
- Single-process, single-threaded, no auth (actor name is typed, not verified).
- db.json is the "shared database" every view (admin/engineer/cs/technician) reads
  and writes through this server, so an action taken in one view is visible in
  the others as soon as they refresh/poll.
- All lifecycle gates (the blueprint's structural rules) are enforced HERE, in the
  data layer, not in the HTML/JS. That's deliberate: it's the point of the demo.

Run:  python3 server.py   (Python 3.8+, no dependencies)
Then open http://localhost:8000/ in four browser tabs (or windows).

CONFIG: PORT / DB_PATH / STATIC_DIR below can be overridden with the
OM_PORT / OM_DB_PATH / OM_STATIC_DIR environment variables, without editing
this file — e.g. for a staging/production environment that needs a
different port or a db.json living somewhere else.
"""

import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# Setiap request API buat load_db() -> ubah dalam memory -> save_db() tulis
# balik SELURUH fail. Server ni ThreadingHTTPServer (setiap request dapat
# thread sendiri) dan sengaja dibuka dalam banyak tab/role serentak, jadi
# tanpa lock, dua request yang jatuh serentak boleh "lost update" — satu
# overwrite perubahan yang lain tanpa sebarang error. Lock ni buat setiap
# request API diproses satu-satu (atomic read-modify-write), tak ubah
# sebarang logic/business-rule.
DB_LOCK = threading.Lock()

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("OM_DB_PATH") or os.path.join(ROOT, "db.json")
STATIC_DIR = os.environ.get("OM_STATIC_DIR") or os.path.join(ROOT, "static")
PORT = int(os.environ.get("OM_PORT", 8000))
LOG_PATH = os.environ.get("OM_LOG_PATH") or os.path.join(ROOT, "om_actions.log")
# Mock email outbox for @mention notifications (no real SMTP in this prototype —
# see queue_mock_email()). Override with OM_EMAIL_LOG_PATH for a production-like
# path; digital team swaps this for a real email send later.
EMAIL_LOG_PATH = os.environ.get("OM_EMAIL_LOG_PATH") or os.path.join(ROOT, "om_email_outbox.log")

ACTIVE_STATES_FOR_EARLY_CLOSE = {"created", "scheduled", "site_visit", "report_drafting", "engineer_review"}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)


MAX_REQUEST_BYTES = 5 * 1024 * 1024
BACKUP_KEEP_DAYS = 14


def backup_db_daily():
    """Once per (Malaysia) day, copy db.json into a 'backups' folder next to it and keep the
    newest 14. It lives on the same disk as the data, so it protects against a bad edit or
    a corrupted file — NOT against losing the machine; copy that folder off-machine too."""
    try:
        if not os.path.exists(DB_PATH):
            return
        folder = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "backups")
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, f"db-{business_now().strftime('%Y%m%d')}.json")
        if not os.path.exists(target):
            shutil.copy2(DB_PATH, target)
            old = sorted(f for f in os.listdir(folder) if re.match(r"^db-\d{8}\.json$", f))
            for f in old[:-BACKUP_KEEP_DAYS]:
                os.remove(os.path.join(folder, f))
    except Exception:
        pass  # a backup problem must never stop a save


def save_db(db):
    backup_db_daily()  # copy of the file as it stood BEFORE this write (first write of each day)
    # Tulis ke fail sementara dulu, pastikan data betul-betul sampai ke disk
    # (flush + fsync), baru gantikan db.json dalam SATU langkah atomic
    # (os.replace). Kalau server terhenti bila-bila masa semasa proses ni,
    # db.json yang sedia ada tak akan pernah jadi separuh tertulis/corrupt —
    # ia kekal versi lama yang lengkap sehingga gantian penuh berjaya.
    tmp_path = DB_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(db, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, DB_PATH)


def neutralize_html(value):
    """Stop typed text from being run as code. Almost every page builds its screen with
    innerHTML, so a name, remark or message such as <img onerror=...> would execute for
    whoever opens it (stored XSS). Every text value coming IN from a request has < > and "
    swapped for their harmless HTML codes; the browser still SHOWS them as normal characters
    (e.g. "voltage <200V" reads the same). Long term the pages themselves should escape
    their output (see README); this closes the hole at the one place all input passes through."""
    if isinstance(value, str):
        return value.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    if isinstance(value, list):
        return [neutralize_html(v) for v in value]
    if isinstance(value, dict):
        return {k: neutralize_html(v) for k, v in value.items()}
    return value


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def find_ticket(db, ticket_id):
    for t in db["tickets"]:
        if t["id"] == ticket_id:
            migrate_report_format(db, t)
            migrate_checklist_template(db, t)
            return t
    raise ApiError("This ticket could not be found — it may have been deleted.", 404)


def log_action(actor, action, ticket_id, result, error=""):
    """Append-only, one-line-per-call log for every /api/tickets/<id>/<action>
    request — separate from event_log (which lives inside each ticket and
    only records what SUCCEEDED). This one also captures failed attempts,
    which is what's most useful when debugging after a production move.
    Best-effort: a logging failure must never break the actual request."""
    try:
        with open(LOG_PATH, "a") as f:
            entry = {"ts": now_iso(), "actor": actor, "action": action,
                      "ticket_id": ticket_id, "result": result}
            if error:
                entry["error"] = error
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def queue_mock_email(to_name, ticket, from_actor, snippet):
    """Mock email notification for an @mention (no real SMTP in this prototype
    — see EMAIL_LOG_PATH). Appends one JSON line per recipient to the outbox
    log; digital team wires this up to a real email send (SMTP/SES/SendGrid/
    etc.) in production. Best-effort, same as log_action() — a logging
    failure must never break the actual request."""
    try:
        with open(EMAIL_LOG_PATH, "a") as f:
            entry = {
                "ts": now_iso(), "to": to_name, "from": from_actor,
                "ticket_id": ticket["id"], "ticket_title": ticket["title"],
                "snippet": snippet[:140],
            }
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def log_event(ticket, actor, action, from_state, to_state, note=""):
    ticket["event_log"].append({
        "ts": now_iso(),
        "actor": actor or "unknown",
        "action": action,
        "from": from_state,
        "to": to_state,
        "note": note,
    })
    ticket["updated_at"] = now_iso()


def add_days_str(date_str, n):
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=n)
    return d.strftime("%Y-%m-%d")


# "Today" for visit days / checklists follows Malaysia time (UTC+8), not UTC, so a day
# rolls over at midnight in Malaysia. Must match BUSINESS_UTC_OFFSET_HOURS in static/shared.js.
BUSINESS_UTC_OFFSET_HOURS = float(os.environ.get("OM_TZ_OFFSET_HOURS", 8))


def business_now():
    return datetime.now(timezone.utc) + timedelta(hours=BUSINESS_UTC_OFFSET_HOURS)


def today_str():
    return business_now().strftime("%Y-%m-%d")


def expand_event_dates(event):
    """Every calendar date an event covers, inclusive — a 3-day event becomes
    3 separate dates, each of which gets its own visit day and checklist."""
    dates = []
    d = event["date"]
    end = event["end_date"]
    guard = 0
    while d <= end and guard < 366:  # guard: a malformed event should never hang the server
        dates.append(d)
        d = add_days_str(d, 1)
        guard += 1
    return dates


def find_visit_day(ticket, day_id):
    return next((d for d in ticket.get("visit_days", []) if d["id"] == day_id), None)


def visit_day_for_today(ticket):
    """The day entry matching today's date, if this ticket has one scheduled today."""
    today = today_str()
    return next((d for d in ticket.get("visit_days", []) if d["date"] == today), None)


def reconcile_visit_days(ticket):
    """Stands in for a nightly cron job, since this server is purely request-driven:
    called whenever a ticket is read or acted on. Marks any day whose date has
    passed without a submitted checklist as 'unfinished', and once every day is
    resolved one way or another, advances the ticket into Report Drafting. Also
    keeps the ticket's own engineer_date/time in sync with the earliest day, for
    the older code paths (dashboards, ticket lists) that still read those directly."""
    days = ticket.get("visit_days", [])
    changed = False
    today = today_str()

    for d in days:
        if d["date"] < today and not d["checklist"]["checklist_completed_at"] and d["status"] == "pending":
            d["status"] = "unfinished"
            changed = True
            log_event(ticket, "system", "day_unfinished", ticket["state"], ticket["state"],
                      f"day {d['date']} passed without a submitted checklist")

    if days:
        earliest = min(days, key=lambda d: d["date"])
        if ticket.get("engineer_date") != earliest["date"]:
            ticket["engineer_date"] = earliest["date"]
            changed = True

    if ticket["state"] in ("scheduled", "site_visit") and days and all(d["status"] in ("submitted", "unfinished") for d in days):
        was_state = ticket["state"]
        if was_state == "scheduled":
            log_event(ticket, "system", "site_visit_started", "scheduled", "site_visit",
                      "every visit day passed without anyone opening a checklist")
        ticket["state"] = "report_drafting"
        log_event(ticket, "system", "auto_advance", "site_visit", "report_drafting",
                  "every visit day resolved (submitted or unfinished)")
        changed = True

    if changed:
        ticket["updated_at"] = now_iso()
    return changed


def next_ticket_id(db):
    db["_seq"] += 1
    return "TCK-%04d" % db["_seq"]


def next_client_id(db):
    db["_client_seq"] = db.get("_client_seq", 0) + 1
    return "CLI-%04d" % db["_client_seq"]


def find_client(db, client_id):
    for c in db.get("clients", []):
        if c["id"] == client_id:
            return c
    return None


def find_client_by_name(db, name):
    norm = name.strip().lower()
    for c in db.get("clients", []):
        if c["name"].strip().lower() == norm:
            return c
    return None


def action_create_client(db, data):
    require_role(db, (data.get("actor") or "").strip(), "create_client")
    name = (data.get("name") or "").strip()
    ctype = (data.get("type") or "").strip()
    if not name or ctype not in ("individual", "company"):
        raise ApiError("Name and a valid client type (individual/company) are required.")
    if find_client_by_name(db, name):
        raise ApiError(f"A client named '{name}' already exists — check for typos or use the existing record.")
    client = {
        "id": next_client_id(db),
        "name": name,
        "type": ctype,
        "contact_person": (data.get("contact_person") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "address": (data.get("address") or "").strip(),
        "city": (data.get("city") or "").strip(),
        "state": (data.get("state") or "").strip(),
        "postcode": (data.get("postcode") or "").strip(),
        "created_by": (data.get("actor") or "").strip(),
        "sites": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db.setdefault("clients", []).append(client)
    return client


def next_kb_article_id(db):
    db["_kb_article_seq"] = db.get("_kb_article_seq", 0) + 1
    return "KB-%04d" % db["_kb_article_seq"]


def next_calendar_event_id(db):
    db["_calendar_seq"] = db.get("_calendar_seq", 0) + 1
    return "EVT-%04d" % db["_calendar_seq"]


def action_create_calendar_event(db, data):
    """This stands in for the one-way Google Calendar -> site sync. In the real
    system, CS creates the job in Google Calendar and it appears here automatically;
    since this demo has no live Google integration, this endpoint is how a new
    'synced' event is simulated arriving."""
    require_role(db, (data.get("actor") or "").strip(), "create_calendar_event")
    title = (data.get("title") or "").strip()
    date = (data.get("date") or "").strip()
    time = (data.get("time") or "").strip()
    end_time = (data.get("end_time") or "").strip()
    all_day = bool(data.get("all_day"))
    end_date = (data.get("end_date") or "").strip() or date
    if not title or not date:
        raise ApiError("Title and date are required.")
    if end_date < date:
        raise ApiError("End date cannot be before the start date.")
    if not all_day and time and end_time and end_time < time and end_date == date:
        raise ApiError("End time cannot be before the start time on the same day.")
    event = {
        "id": next_calendar_event_id(db),
        "title": title,
        "date": date,
        "end_date": end_date,
        "all_day": all_day,
        "time": "" if all_day else time,
        # end_time only matters for a same-day timed event's visual duration in the week
        # grid; a multi-day event's span is already carried by date/end_date.
        "end_time": "" if all_day else (end_time or time),
        "linked_ticket_id": None,
        "created_at": now_iso(),
    }
    db.setdefault("calendar_events", []).append(event)
    return event


def next_report_id(db):
    db["_report_seq"] = db.get("_report_seq", 0) + 1
    today = business_now().strftime("%Y%m%d")
    return f"RPT-{today}-{db['_report_seq']:04d}"


# Categories and items for the "Corrective & Preventive Maintenance Checklist"
# (Section 2 of the residential report). A few items carry an extra free-text
# field (data period, firmware version) alongside accept/reject/remarks.
REPORT_MAINTENANCE_TEMPLATE = [
    ("PV Module & Structure", [
        ("Visual inspection", None),
        ("Structure visual inspection", None),
        ("Cleaning", None),
    ]),
    ("PV Inverter", [
        ("Visual inspection", None),
        ("Grounding", None),
        ("Download inverter log", "Data Period"),
        ("Firmware check and update", "Ver."),
        ("Cleaning", None),
    ]),
    ("AJB, Trunking, Earth Chamber", [
        ("Visual inspection", None),
        ("Grounding/earthing check", None),
        ("Connection check and tightening", None),
        ("AJB cleaning", None),
    ]),
    ("PV Meter", [
        ("Visual Inspection", None),
        ("Grounding (if necessary)", None),
        ("Connection check and tightening", None),
        ("Exported energy reading", None),
    ]),
]


def build_maintenance_checklist():
    items = []
    n = 0
    for category, entries in REPORT_MAINTENANCE_TEMPLATE:
        for name, extra_label in entries:
            n += 1
            items.append({
                "id": f"chk-{n}", "category": category, "name": name, "extra_label": extra_label,
                "result": None, "remarks": "", "extra": "",
            })
    return items


# Ticket types that use the troubleshooting report format (Format B) instead
# of the residential maintenance report (Format A). Residential and C&I
# Troubleshoot/Rectification share the exact same report shape.
TROUBLESHOOTING_TYPES = ("residential_troubleshooting", "ci_troubleshooting")


def build_report(db, ticket):
    """Dispatches to the report shape for this ticket's type. Every ticket
    always has a report, created with the ticket itself (not just at
    scheduling). Kept inside the ticket (not a separate collection) since
    this system always ties a report to the job it came from. The report's
    own status (draft -> submitted -> approved) is now what drives the
    ticket into Engineer Review and Approved — see action_submit_report /
    action_report_approve / action_report_reject (shared by every format)."""
    if ticket.get("type") in TROUBLESHOOTING_TYPES:
        return build_report_troubleshooting(db, ticket)
    return build_report_residential(db, ticket)


def migrate_report_format(db, ticket):
    """Self-heals a ticket whose stored report shape no longer matches its
    type — e.g. a Residential/C&I Troubleshoot ticket created before Format
    B existed, whose report is still frozen in the old Format A (residential)
    shape. Runs on every ticket lookup (find_ticket), so it's a no-op for
    tickets whose report already matches; it only rebuilds (replacing the
    stale, wrong-shape report) when there's a genuine mismatch."""
    report = ticket.get("report")
    expects_troubleshooting = ticket.get("type") in TROUBLESHOOTING_TYPES
    is_troubleshooting = bool(report) and report.get("format") == "troubleshooting"
    if report is None or expects_troubleshooting != is_troubleshooting:
        ticket["report"] = build_report(db, ticket)
        return True  # Fasa 6 audit (3 Okt): lets callers know to save_db().
    return False


def build_report_residential(db, ticket):
    """Format A: the original rich residential report — periodic maintenance
    checklist + electrical measurements. Used for every ticket type except
    the troubleshooting ones (see build_report_troubleshooting) until
    Formats C-F are built."""
    client = find_client_by_name(db, ticket.get("client", ""))
    return {
        "id": next_report_id(db),
        "format": "residential",
        "status": "draft",
        "submitted_by": "", "submitted_at": None,
        "approved_by": "", "approved_at": None,
        "report_rejections": [],
        "general": {
            "date_of_inspection": ticket.get("engineer_date", "") or "",
            "system_owner": ticket.get("client", ""),
            "system_location": (client.get("address", "") if client else ""),
            "contact_no": (client.get("phone", "") if client else ""),
            "system_size_kwp": "",
            "inverter_model": "",
            "inverter_sn": "",
        },
        "maintenance_checklist": build_maintenance_checklist(),
        "electrical": {
            "ac_phase_type": "",
            "ac_measurements": {
                "single": {"line_to_neutral_v": "", "line_to_ground_v": "", "neutral_to_ground_v": ""},
                "three": {
                    "l1_l2_v": "", "l2_l3_v": "", "l3_l1_v": "",
                    "l1_n_v": "", "l2_n_v": "", "l3_n_v": "",
                    "l1_g_v": "", "l2_g_v": "", "l3_g_v": "", "n_g_v": "",
                },
            },
            "inverters": [],
        },
        "media": {
            "pv_before": [], "pv_after": [], "inverter": [], "ac_photo": [], "dc_photo": [], "fit_meter": [],
        },
        "summary": {
            "psh": "", "overall_status": "", "yearly_generation_kwh": "", "avg_monthly_generation_kwh": "",
            "engineer_comments": "", "performance_graph": [],
        },
        "report_notes": {
            "performance_report_result": None,  # "accept" | "reject" | None
            "remarks": "",
            "additional_notes": "",
        },
        "installation_improvement": {
            "site_improvement_performed": None,  # "yes" | "no" | None
            "engineer_comments": "",
        },
        "additional_media": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


# ---------- Format B: Troubleshoot/Rectification report ----------
# Transcribed from the existing ERS system's troubleshooting report
# (screenshots, 2 Okt) — diagnostic measurements + narrative issue/root
# cause/action/conclusion lines, instead of Format A's periodic maintenance
# checklist. Shared by Residential and C&I Troubleshoot/Rectification.

INSPECTION_AC_THREE_PHASE_FIELDS = (
    ("red_yellow", "Red to Yellow (Voltage)"),
    ("red_blue", "Red to Blue (Voltage)"),
    ("yellow_blue", "Yellow to Blue (Voltage)"),
    ("red_neutral", "Red to Neutral (Voltage)"),
    ("yellow_neutral", "Yellow to Neutral (Voltage)"),
    ("blue_neutral", "Blue to Neutral (Voltage)"),
    ("red_ground", "Red to Ground (Voltage)"),
    ("yellow_ground", "Yellow to Ground (Voltage)"),
    ("blue_ground", "Blue to Ground (Voltage)"),
    ("neutral_ground", "Neutral to Ground (Voltage)"),
)

INSPECTION_AC_SINGLE_PHASE_FIELDS = (
    ("live_neutral", "Live to Neutral (Voltage)"),
    ("live_ground", "Live to Ground (Voltage)"),
    ("neutral_ground", "Neutral to Ground (Voltage)"),
)

# The 7 standalone diagnostic tests (items 4-10 in the ERS screenshot),
# each its own {value, remark} row — not grouped under AC/DC like the
# voltage measurements above.
INSPECTION_LINE_ITEMS = (
    ("solar_panel_visual", "Solar Panel Visual Inspection"),
    ("grounding", "Grounding Inspection"),
    ("ac_dc_junction_box", "AC and DC Junction Box Inspection"),
    ("yield_psh", "Yield PSH"),
    ("capture_irradiance", "Capture Irradance"),
    ("iv_curve_test", "IV Curve Test"),
    ("insulation_test", "Insulation Test"),
)


def build_dc_string(string_id):
    return {
        "id": string_id, "label": f"String {string_id}",
        "voltage_v": "", "voltage_remark": None,  # remark: "ok" | "not_ok" | None
        "positive_ground_v": "", "positive_ground_remark": None,
        "negative_ground_v": "", "negative_ground_remark": None,
    }


def build_inspection_checklist():
    return {
        "ac_three_phase": {key: {"value": "", "remark": None} for key, _ in INSPECTION_AC_THREE_PHASE_FIELDS},
        "ac_single_phase": {key: {"value": "", "remark": None} for key, _ in INSPECTION_AC_SINGLE_PHASE_FIELDS},
        # DC string count varies per installation — technician adds/removes
        # strings to match the real system; starts with 4 (the ERS default).
        "dc_strings": [build_dc_string(n) for n in range(1, 5)],
        "line_items": [{"id": key, "label": label, "value": "", "remark": None} for key, label in INSPECTION_LINE_ITEMS],
    }


def build_report_troubleshooting(db, ticket):
    client = find_client_by_name(db, ticket.get("client", ""))
    return {
        "id": next_report_id(db),
        "format": "troubleshooting",
        "status": "draft",
        "submitted_by": "", "submitted_at": None,
        "approved_by": "", "approved_at": None,
        "report_rejections": [],
        "checklist_info": {
            "owner": ticket.get("client", ""),
            "system_capacity": "",
            "contact_no": (client.get("phone", "") if client else ""),
            "inverter_model_sn": "",
            "panel_model": "",
        },
        "inspection_checklist": build_inspection_checklist(),
        "intake": {
            "date_report_received": "",
            "time_report_received": "",
            "received_by": "",
            "date_attended_site": "",
            "time_attended_site": "",
            "affected_components": "",
        },
        "reported_issues": [],
        "root_causes": [],
        "actions_taken": [],
        "conclusions": [],
        "remarks": [],
        "installation_improvement": {
            "site_improvement_performed": None,  # "yes" | "no" | None
            "engineer_comments": "",
        },
        "additional_media": [],
        "signatures": {"customer_name": "", "ers_pic": ""},
        "site_photos": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


# ---------- Actions (every gate lives here) ----------

TYPE_LABELS = {
    "site_survey": "Site Survey",
    "servicing": "Servicing",  # legacy value — kept so older tickets still show a label, no longer offered when creating a new ticket
    "troubleshooting": "Troubleshooting",  # legacy value — same as above
    "dere": "DERE",
    "residential_servicing": "Residential Servicing",
    "residential_troubleshooting": "Residential Troubleshoot/Rectification",
    "ci_servicing": "C&I Servicing",
    "ci_troubleshooting": "C&I Troubleshoot/Rectification",
    "ntp_phase_1": "NTP Phase 1",
    "ntp_phase_2": "NTP Phase 2",
    "ntp_phase_3": "NTP Phase 3",
    "ntp_phase_4": "NTP Phase 4",
}

PRIORITIES = ("low", "medium", "high", "critical")
# Old values kept so existing tickets still display, but no longer accepted for a NEW ticket.
LEGACY_TICKET_TYPES = ("servicing", "troubleshooting")

# Residential safety checklist, transcribed from ERS Energy's PDF form.
# **bold markers** highlight the key term the technician should focus on;
# the frontend renders them as bold, not literal asterisks.
CHECKLIST_TEMPLATE = [
    {"stage": "pre", "section": "Personal Protective Equipment (PPE)",
     "text": "All **PPE** (helmet, vest, boots, gloves) worn and in good condition."},
    {"stage": "pre", "section": "Working at Height & Fall Protection",
     "text": "**Full body harness**, lanyard, and anchor points inspected and used."},
    {"stage": "pre", "section": "Working at Height & Fall Protection",
     "text": "**Ladder inspected**, set at a 4:1 angle, secured, and extends 1m above the roof."},
    {"stage": "pre", "section": "Site & Roof Structure Assessment",
     "text": "Inspect roof for **cracks, damage, moss, or sagging** before stepping."},
    {"stage": "pre", "section": "Site & Roof Structure Assessment",
     "text": "Check weather: ensure **no rain, wet roof, strong wind (>20km/h), or lightning**."},

    {"stage": "during", "section": "Electrical Isolation & LOTO",
     "text": "**Switch OFF** AC and DC isolators and apply **LOTO** before electrical work."},
    {"stage": "during", "section": "Electrical Isolation & LOTO",
     "text": "Verify **zero voltage** using a calibrated multimeter / voltage detector."},
    {"stage": "during", "section": "Inverter & Isolator Area",
     "text": "Inverter and DC isolator location has **sufficient space** for heat release and **no flammable items** nearby."},
    {"stage": "during", "section": "Inverter & Isolator Area",
     "text": "Inverter casing, seals, and cable entries are **intact and sealed** against moisture and pests."},
    {"stage": "during", "section": "DC Strings & Module Integrity",
     "text": "Check **open-circuit voltage (Voc)** and string polarity against design specs."},
    {"stage": "during", "section": "DC Strings & Module Integrity",
     "text": "Inspect **MC4 connectors**: properly crimped, fully locked, undamaged, and matching brands."},
    {"stage": "during", "section": "Grounding & Earthing Safety",
     "text": "Ensure PV frames, mounting rails, and inverter casing are **properly grounded**."},
    {"stage": "during", "section": "Grounding & Earthing Safety",
     "text": "Verify **earth pit resistance** is below safe limits (< 10 Ohms)."},
    {"stage": "during", "section": "Cable Routing & Mechanical Protection",
     "text": "DC/AC cables properly protected in **trunking or conduits** with no sharp edges."},
    {"stage": "during", "section": "AC Distribution Board (DB) Safety",
     "text": "Main switchboard/DB connections secure; **RCBO/RCD and AC breakers** operational and labeled."},
    {"stage": "during", "section": "AC Distribution Board (DB) Safety",
     "text": "AC and DC **Surge Protection Devices (SPD)** checked; indicators are green."},
    {"stage": "during", "section": "Fire Safety & Emergency Preparedness",
     "text": "**Fire extinguisher** available on site and within validity date."},
    {"stage": "during", "section": "Fire Safety & Emergency Preparedness",
     "text": "**First aid kit** accessible and emergency contacts briefed."},

    {"stage": "post", "section": "Housekeeping & Public Safety",
     "text": "Place **safety cones and warning signs** around the ladder base and roof perimeter."},
    {"stage": "post", "section": "Site Demobilization & Handover",
     "text": "**Clear tools and scrap** from roof, and brief client on operation and shutdown."},
]

# C&I / DERE / Site Survey safety checklist — a separate, larger form from
# the residential one above (18 sections, 22 items vs. 12/20), transcribed
# from ERS Energy's own C&I PTW-style checklist. Covers substation/HV work,
# PTW (Permit To Work) closure, and other commercial-site-specific steps
# the residential form doesn't have.
CHECKLIST_TEMPLATE_CI = [
    {"stage": "pre", "section": "Work Permits & Statutory Compliance",
     "text": "Have an approved work permit and go over the safety check before starting work."},
    {"stage": "pre", "section": "Personal Protective Equipment (PPE)",
     "text": "All PPE (helmet, vest, boots, gloves) worn and in good condition."},
    {"stage": "pre", "section": "Working at Height & Lifelines",
     "text": "Full body harness, lanyard, and anchor points inspected and used."},
    {"stage": "pre", "section": "Working at Height & Lifelines",
     "text": "Ladder inspected, set at a 4:1 angle, secured, and extends 1m above the roof."},

    {"stage": "during", "section": "Roof Integrity & Skylight Protection",
     "text": "Mark and cover fragile roof areas, skylights, and asbestos zones with safety boards or mesh."},
    {"stage": "during", "section": "Roof Integrity & Skylight Protection",
     "text": "Ensure roof edge guardrails are at least 1.1m high, or set up warning lines 2m from the edge."},
    {"stage": "during", "section": "Environmental & Weather Monitoring",
     "text": "Monitor weather: wind below 20 km/h, temperature, and lightning warnings."},
    {"stage": "during", "section": "High/Low Voltage Lockout Tagout (LOTO)",
     "text": "Lock and tag all switchgear, isolators, and central inverters with a multi-lock box, and verify with the client."},
    {"stage": "during", "section": "High/Low Voltage Lockout Tagout (LOTO)",
     "text": "Verify dead circuits using a Live-Dead-Live test with a calibrated high-voltage tester before starting work."},
    {"stage": "during", "section": "Substation & Transformer Safety",
     "text": "Restrict substation entry, use rubber insulation mats, keep ventilation running, and maintain required safety clearances."},
    {"stage": "during", "section": "Central & String Inverter Station",
     "text": "Isolate inverters and use a thermal camera to check DC combiner boxes for hot spots."},
    {"stage": "during", "section": "Central & String Inverter Station",
     "text": "Clean inverter fans, filters, and heat sinks, and confirm DC busbar torque marks are intact."},
    {"stage": "during", "section": "DC String Testing & Insulation (Megger)",
     "text": "Record DC string polarity and Voc, and ensure insulation resistance passes the Megger test."},
    {"stage": "during", "section": "Earthing & Lightning Protection System",
     "text": "Check that earth grid and lightning protection system (LPS) conductors have low resistance (<10 Ohm)."},

    {"stage": "post", "section": "Cable Trays & Heavy Conduit Support",
     "text": "Secure heavy cable trays, ground metallic channels, and seal wall openings with fire stops."},
    {"stage": "post", "section": "Hazardous Chemical Handling",
     "text": "Store chemicals, coolants, and cleaning agents safely with Safety Data Sheets (SDS) available on site."},
    {"stage": "post", "section": "Emergency Alarms & Response Plan",
     "text": "Evacuation point identified, alarm system tested, and emergency plan shared with everyone."},
    {"stage": "post", "section": "Fire Protection Systems & Hydrants",
     "text": "Ensure all fire extinguishers, hose reels, and fire suppression systems are clear and easy to reach."},
    {"stage": "post", "section": "Certified First Aider & Medical Kit",
     "text": "Certified first aid present on site with an accessible eyewash station and trauma kit."},
    {"stage": "post", "section": "Noise & Hearing Conservation",
     "text": "Wear hearing protection in high-noise areas like transformer, generator, or compressor rooms."},
    {"stage": "post", "section": "Waste Segregation & Environmental Care",
     "text": "Separate electronic waste, broken solar cells, and hazardous materials for licensed disposal."},
    {"stage": "post", "section": "De-Mobilization, PTW Closure & Handover",
     "text": "Remove temporary grounds and locks, sign off the work permit, and clean up the site."},
]

# Ticket types that use the C&I checklist above instead of the residential
# one. Anything not listed here (including legacy/unknown types) falls back
# to "residential" unless it's an NTP type (see CHECKLIST_NTP_TYPES below).
CHECKLIST_CI_TYPES = ("ci_servicing", "ci_troubleshooting", "dere", "site_survey")

# NTP Phase 1-4 don't use a Pass/Fail/N/A checklist at all — they use a
# single PDF upload instead (see build_checklist's "ntp" branch). Mapped to
# an empty item template ([]) so it flows through the exact same
# build_checklist/migrate_checklist_template machinery as the other two.
CHECKLIST_NTP_TYPES = ("ntp_phase_1", "ntp_phase_2", "ntp_phase_3", "ntp_phase_4")

CHECKLIST_TEMPLATES = {"residential": CHECKLIST_TEMPLATE, "ci": CHECKLIST_TEMPLATE_CI, "ntp": []}


def checklist_template_key(ticket_type):
    if ticket_type in CHECKLIST_CI_TYPES:
        return "ci"
    if ticket_type in CHECKLIST_NTP_TYPES:
        return "ntp"
    return "residential"


def build_checklist(template_key="residential"):
    """A fresh, unanswered checklist instance for a new visit — every visit
    gets its own independent copy, never shared or carried over answered.
    `template_key` picks which question set (see CHECKLIST_TEMPLATES);
    stored on the result so migrate_checklist_template can later tell
    whether a visit day's checklist still matches its ticket's type.
    "ntp" maps to an empty item template, so `items` naturally comes out
    as [] — the NTP visit day is driven by `pdf_file` instead (set via
    action_checklist_pdf), with Pass/Fail/N/A logic simply having nothing
    to iterate over for that template."""
    template = CHECKLIST_TEMPLATES[template_key]
    return {
        "template": template_key,
        "checklist_started_at": None,
        "checklist_completed_at": None,
        "submitted_by": None,
        "general_remarks": "",
        "general_media": [],
        "pdf_file": None,
        "items": [
            {
                "id": f"item-{i+1}",
                "stage": tmpl["stage"],
                "section": tmpl["section"],
                "text": tmpl["text"],
                "status": None,
                "note": "",
                "attachments": [],
            }
            for i, tmpl in enumerate(template)
        ],
    }


def build_visit_day(day_id, date_str, event_id, default_engineer, ticket_type=None):
    return {
        "id": day_id,
        "date": date_str,
        "source_event_id": event_id,
        "engineer": default_engineer or "",
        "technicians": [],
        "checklist": build_checklist(checklist_template_key(ticket_type)),
        "status": "pending",  # pending | submitted | unfinished
    }


def migrate_checklist_template(db, ticket):
    """Self-heals visit days built before CHECKLIST_TEMPLATE_CI existed (or
    before a ticket's type was accounted for) — e.g. a C&I Servicing ticket
    whose visit day still carries the residential checklist content. Only
    rebuilds a day's checklist when none of its items have actually been
    answered yet, so it never discards real field answers; a day with at
    least one real Pass/Fail/N/A on the wrong template is left alone rather
    than silently wiped.

    Deliberately does NOT key off checklist_started_at: that timestamp gets
    auto-stamped the moment a technician merely opens today's checklist
    (action_start_checklist), before they've answered a single item — so
    using it as the guard would permanently lock a never-answered checklist
    onto a stale template just because the page was opened once."""
    expected = checklist_template_key(ticket.get("type"))
    changed = False
    for day in ticket.get("visit_days", []):
        cl = day.get("checklist")
        if not cl or cl.get("template") == expected:
            continue
        has_answers = (any(item.get("status") is not None for item in cl.get("items", []))
                       or bool(cl.get("pdf_file")))
        if not has_answers:
            day["checklist"] = build_checklist(expected)
            changed = True
    return changed  # Fasa 6 audit (3 Okt): lets callers know to save_db().



def find_account_by_name(db, name):
    for a in db.get("accounts", []):
        if a["name"] == name:
            return a
    return None


# ---------------------------------------------------------------------------
# WHO MAY DO WHAT  (role matrix agreed with the HOD, 14 Oct)
# Roles in db.json: admin = HOD, engineer, cs, technician.
# IMPORTANT: this stops a person using the wrong role's buttons or calling the
# API for an action their role doesn't own. It does NOT prove who is calling —
# the "actor" name still comes from the browser. Real security needs a proper
# login (session/token), which the digital team must add. Keep this table in
# sync with ACTION_ROLES in static/shared.js (the UI hides what the server refuses).
# ---------------------------------------------------------------------------
_ALL = ("admin", "engineer", "cs", "technician")
_HOD_ENG_CS = ("admin", "engineer", "cs")
_HOD_CS = ("admin", "cs")
_TECH_ENG = ("technician", "engineer")
_HOD_ENG = ("admin", "engineer")
ACTION_ROLES = {
    "create_ticket": _HOD_ENG_CS,
    "assign": _HOD_ENG_CS,
    "update_ticket_details": _HOD_ENG_CS,
    "snooze": _HOD_ENG_CS,
    "link_events": _HOD_CS, "unlink_event": _HOD_CS, "set_day_people": _HOD_CS, "clear_reschedule": _HOD_CS,
    "reschedule": _TECH_ENG,
    "start_checklist": _TECH_ENG, "checklist_item": _TECH_ENG, "checklist_general": _TECH_ENG,
    "checklist_pdf": _TECH_ENG, "submit_checklist": _TECH_ENG,
    "submit_report": _TECH_ENG,
    "report_approve": _HOD_ENG, "report_reject": _HOD_ENG,
    "close": _HOD_CS, "early_close": _HOD_CS,
    "delete_ticket": _HOD_CS,
    "message": _ALL, "mark_ticket_read": _ALL,
    "override_report_timestamp": ("admin",),
    "create_client": _HOD_ENG_CS,          # ticket-new lets whoever creates a ticket add a missing client
    "create_calendar_event": _HOD_CS,      # same people who schedule
    "update_settings": ("admin",),
}
# Every report-content edit belongs to whoever fills in the report: technician or engineer.
for _a in ("report_section", "report_checklist_item", "report_add_inverter", "report_remove_inverter",
           "report_add_mppt", "report_remove_mppt", "report_add_string", "report_remove_string",
           "report_update_string", "report_add_media", "report_remove_media", "report_inspection_measurement",
           "report_add_dc_string", "report_remove_dc_string", "report_update_dc_string",
           "report_narrative_add_line", "report_narrative_update_line", "report_narrative_remove_line",
           "report_narrative_add_photo", "report_narrative_remove_photo"):
    ACTION_ROLES[_a] = _TECH_ENG
ROLE_LABELS = {"admin": "HOD", "engineer": "Engineer", "cs": "CS", "technician": "Technician"}


CHECKLIST_ACTIONS = {"start_checklist", "checklist_item", "checklist_general", "checklist_pdf", "submit_checklist"}


def require_checklist_access(db, ticket, actor, data):
    """A technician may fill a checklist only for a visit day their own team is on
    (themselves, or a technician with the same team). An engineer may fill it only on
    an engineer-only day they are the engineer for. Same rule the phone pages use."""
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        return  # the action reports the missing day itself
    account = find_account_by_name(db, actor)
    if not account:
        return
    techs = day.get("technicians") or []
    if account["role"] == "engineer":
        ok = not techs and day.get("engineer") == actor
        why = "an engineer can fill the checklist only on a visit with no technician, where they are the engineer"
    else:
        team = account.get("team")
        ok = actor in techs or (bool(team) and any((find_account_by_name(db, n) or {}).get("team") == team for n in techs))
        why = "this visit isn't assigned to your team"
    if not ok:
        raise ApiError(f"You can't fill this checklist — {why}.", 403)


def require_role(db, actor, action):
    """Reject the call unless `actor` is a real account whose role may do `action`."""
    allowed = ACTION_ROLES.get(action)
    if allowed is None:
        return  # an action not in the table is not role-restricted
    account = find_account_by_name(db, actor)
    if not account:
        raise ApiError("Unknown user — please log in again.", 403)
    if account["role"] not in allowed:
        who = " / ".join(ROLE_LABELS[r] for r in allowed)
        raise ApiError(f"Your role ({ROLE_LABELS.get(account['role'], account['role'])}) can't do this. Allowed: {who}.", 403)


def validate_assignable(db, name):
    """Shared gate: an assignee must be a real account, and must not be a technician.
    Used both when adding an assignee later and when creating a ticket with
    initial assignees, so the rule can't be bypassed via either path."""
    account = find_account_by_name(db, name)
    if not account:
        raise ApiError(f"'{name}' is not a known account.")
    if account["role"] == "technician":
        raise ApiError("Technicians are not assigned to tickets — they see jobs via the shared job board instead.")
    return account


def action_create(db, data):
    title = (data.get("title") or "").strip()
    client = (data.get("client") or "").strip()
    ttype = (data.get("type") or "").strip()
    description = (data.get("description") or "").strip()
    priority = (data.get("priority") or "").strip().lower()
    actor = (data.get("actor") or "").strip()
    site = (data.get("site") or "").strip()
    require_role(db, actor, "create_ticket")

    if not description or not ttype or not client:
        raise ApiError("Client, ticket type, and description are all required to create a ticket.")
    if priority not in PRIORITIES:
        raise ApiError("A valid priority level is required.")
    if ttype not in TYPE_LABELS or ttype in LEGACY_TICKET_TYPES:
        raise ApiError("Please choose a valid ticket type.")
    known_client = find_client_by_name(db, client)
    if not known_client:
        raise ApiError(f"Client '{client}' is not in Clients & Sites. Pick an existing client or add it first.")
    client = known_client["name"]  # use the stored spelling

    if not title:
        title = f"{client} - {TYPE_LABELS.get(ttype, ttype)}"

    initial_assignees = [actor] if actor else []
    for name in data.get("initial_assignees", []) or []:
        name = (name or "").strip()
        if not name or name in initial_assignees:
            continue
        validate_assignable(db, name)
        initial_assignees.append(name)

    equipment = data.get("equipment") or {}
    commercial = data.get("commercial") or {}
    additional = data.get("additional") or {}

    ticket = {
        "id": next_ticket_id(db),
        "title": title,
        "client": client,
        "site": site,
        "type": ttype,
        "priority": priority,
        "description": description,
        "state": "created",
        "assignees": initial_assignees,
        "engineer_date": None,
        "visit_days": [],
        "calendar_event_ids": [],
        "default_engineer": "",
        "report": {"status": "draft"},
        "closure": {"type": None, "reason": None, "closed_at": None},
        "snooze_until": None,
        "snooze_reason": "",
        "snoozed_at": None,
        "messages": [],
        "equipment": {
            "panels": (equipment.get("panels") or "").strip(),
            "inverter_brand": (equipment.get("inverter_brand") or "").strip(),
            "inverter_model": (equipment.get("inverter_model") or "").strip(),
            "nemcd_ref": (equipment.get("nemcd_ref") or "").strip(),
        },
        "commercial": {
            "dlp_end_date": (commercial.get("dlp_end_date") or "").strip(),
            "chargeable_service_call": bool(commercial.get("chargeable_service_call")),
        },
        "additional": {
            "so_number": (additional.get("so_number") or "").strip(),
            "premium_care_status": (additional.get("premium_care_status") or "").strip(),
            "system_size": (additional.get("system_size") or "").strip(),
            "assigned_team": (additional.get("assigned_team") or "").strip(),
            "contact_phone": (additional.get("contact_phone") or "").strip(),
            "client_remarks": (additional.get("client_remarks") or "").strip(),
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "event_log": [],
    }
    log_event(ticket, actor, "create", None, "created")
    ticket["report"] = build_report(db, ticket)
    db["tickets"].insert(0, ticket)
    return ticket


def action_assign(db, ticket, data):
    name = (data.get("name") or "").strip()
    act = data.get("action")
    actor = data.get("actor")
    if not name or act not in ("add", "remove"):
        raise ApiError("A name and action ('add' or 'remove') are required.")
    if act == "add":
        validate_assignable(db, name)
        if name not in ticket["assignees"]:
            ticket["assignees"].append(name)
            log_event(ticket, actor, "assign_add", ticket["state"], ticket["state"], name)
    else:
        if name in ticket["assignees"]:
            if len(ticket["assignees"]) == 1:
                raise ApiError("Cannot remove the last assignee — add a replacement first.")
            ticket["assignees"].remove(name)
            log_event(ticket, actor, "assign_remove", ticket["state"], ticket["state"], name)
        else:
            # Fasa 6 audit (3 Okt) — this used to silently return 200 with the
            # ticket unchanged when `name` was already not assigned, which
            # looked exactly like a successful removal to the caller (no error,
            # no change). Now it says plainly that there was nothing to remove.
            raise ApiError(f"'{name}' is not assigned to this ticket.")
    return ticket


def find_calendar_event(db, event_id):
    for e in db.get("calendar_events", []):
        if e["id"] == event_id:
            return e
    return None


def validate_technicians(db, names, engineer=""):
    """Every name must be a real technician account. Returns the cleaned list.
    Used by both scheduling and editing a visit, so the rule can't be bypassed
    via either path. An empty list is allowed only when an engineer is set for
    the visit: that is an "engineer-only visit" (the engineer goes to site alone
    and fills the safety checklist and report themselves)."""
    cleaned = []
    for name in names or []:
        name = (name or "").strip()
        if not name or name in cleaned:
            continue
        account = find_account_by_name(db, name)
        if not account or account["role"] != "technician":
            raise ApiError(f"'{name}' is not a known technician account.")
        cleaned.append(name)
    if not cleaned and not (engineer or "").strip():
        raise ApiError("At least one technician is required for the visit (or an engineer, for an engineer-only visit).")
    return cleaned


def action_link_events(db, ticket, data):
    """Links one or more calendar events to this ticket. Used for the very first
    scheduling of a ticket (requires an engineer) and for adding more days later
    from the Site Visit card (reuses the ticket's existing engineer as the
    default for the new days). Each event is expanded into one visit day per
    calendar date it covers, each with its own fresh checklist — a 3-day event
    becomes 3 separate days, not one."""
    actor = data.get("actor")
    event_ids = data.get("calendar_event_ids")
    if not event_ids:
        single = (data.get("calendar_event_id") or "").strip()
        event_ids = [single] if single else []
    event_ids = [e.strip() for e in event_ids if e and e.strip()]
    if not event_ids:
        raise ApiError("Select at least one calendar event to link.")

    first_time = ticket["state"] == "created"
    if first_time:
        engineer = (data.get("engineer") or "").strip()
        if not engineer:
            raise ApiError("An engineer is required to schedule a visit.")
        account = find_account_by_name(db, engineer)
        if not account or account["role"] != "engineer":
            raise ApiError(f"'{engineer}' is not a known engineer account.")
        ticket["default_engineer"] = engineer
        if engineer not in ticket["assignees"]:
            ticket["assignees"].append(engineer)
    else:
        if ticket["state"] == "closed":
            raise ApiError("Cannot link new visit days to a closed ticket.")
        engineer = ticket.get("default_engineer", "")

    technicians = validate_technicians(db, data.get("technicians"), engineer)

    events = []
    for eid in event_ids:
        event = find_calendar_event(db, eid)
        if not event:
            raise ApiError(f"Calendar event '{eid}' no longer exists — it may have been re-synced.")
        if event.get("linked_ticket_id") and event["linked_ticket_id"] != ticket["id"]:
            raise ApiError(f"'{event['title']}' is already linked to another ticket.")
        events.append(event)

    next_day_id = max((d["id"] for d in ticket["visit_days"]), default=0) + 1
    added_dates = []
    for event in events:
        event["linked_ticket_id"] = ticket["id"]
        if event["id"] not in ticket["calendar_event_ids"]:
            ticket["calendar_event_ids"].append(event["id"])
        for date_str in expand_event_dates(event):
            day = build_visit_day(next_day_id, date_str, event["id"], engineer, ticket["type"])
            day["technicians"] = list(technicians)
            ticket["visit_days"].append(day)
            added_dates.append(date_str)
            next_day_id += 1

    # Defensive fallback for very old data saved before reports existed at
    # all — Format B reports never have maintenance_checklist, so this must
    # not fire for them (migrate_report_format, run on every find_ticket,
    # already keeps Format B reports correctly shaped).
    if not ticket.get("report"):
        ticket["report"] = build_report(db, ticket)
    elif ticket["report"].get("format") != "troubleshooting" and not ticket["report"].get("maintenance_checklist"):
        ticket["report"] = build_report(db, ticket)

    was_state = ticket["state"]
    if first_time or ticket["state"] not in ("created", "scheduled"):
        # new/added days mean there's fresh unstarted work — the timeline steps
        # back to Scheduled even if it had already progressed further
        ticket["state"] = "scheduled"

    ticket["visit_days"].sort(key=lambda d: d["date"])
    log_event(ticket, actor, "link_events", was_state, ticket["state"],
              f"engineer={engineer}, technicians={','.join(technicians)}, days_added={','.join(added_dates)}")
    return ticket


def action_unlink_event(db, ticket, data):
    actor = data.get("actor")
    event_id = (data.get("calendar_event_id") or "").strip()
    if not event_id:
        raise ApiError("A calendar event id is required to unlink.")
    if event_id not in ticket.get("calendar_event_ids", []):
        raise ApiError("That event isn't linked to this ticket.")
    removed_days = [d for d in ticket["visit_days"] if d["source_event_id"] == event_id]
    if any(d["status"] == "submitted" for d in removed_days):
        raise ApiError("Can't unlink an event that already has a submitted checklist — that record has to stay.")
    ticket["visit_days"] = [d for d in ticket["visit_days"] if d["source_event_id"] != event_id]
    ticket["calendar_event_ids"].remove(event_id)
    event = find_calendar_event(db, event_id)
    if event and event.get("linked_ticket_id") == ticket["id"]:
        event["linked_ticket_id"] = None
    was_state = ticket["state"]
    if not ticket["calendar_event_ids"] and ticket["state"] not in ("created", "closed"):
        ticket["state"] = "created"
    log_event(ticket, actor, "unlink_event", was_state, ticket["state"], f"event={event_id}")
    return ticket


def action_set_day_people(db, ticket, data):
    actor = data.get("actor")
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        raise ApiError("Couldn't find that visit day — try refreshing the page.")
    if "engineer" in data:
        engineer = (data["engineer"] or "").strip()
        if engineer:
            account = find_account_by_name(db, engineer)
            if not account or account["role"] != "engineer":
                raise ApiError(f"'{engineer}' is not a known engineer account.")
        day["engineer"] = engineer
        if engineer and engineer not in ticket["assignees"]:
            ticket["assignees"].append(engineer)
    if "technicians" in data:
        day["technicians"] = validate_technicians(db, data["technicians"], day.get("engineer", ""))
    if not day.get("technicians") and not (day.get("engineer") or "").strip():
        raise ApiError("A visit needs at least one technician, or an engineer for an engineer-only visit.")
    ticket["updated_at"] = now_iso()
    log_event(ticket, actor, "day_people", ticket["state"], ticket["state"], f"day={day['id']}")
    return ticket


def action_start_checklist(db, ticket, data):
    actor = data.get("actor")
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        raise ApiError("Couldn't find that visit day — try refreshing the page.")
    today = today_str()
    if day["date"] > today:
        raise ApiError(f"This checklist opens on {day['date']} — not yet.")
    if day["date"] < today:
        raise ApiError(f"This checklist was for {day['date']} and is now past due.")
    cl = day["checklist"]
    if not cl["checklist_started_at"]:
        cl["checklist_started_at"] = now_iso()
        log_event(ticket, actor, "checklist_started", ticket["state"], ticket["state"], f"day={day['date']}")
        # Which report field gets auto-filled with the visit date depends on
        # the report format (Format B has no "general.date_of_inspection").
        report = ticket["report"]
        if report.get("format") == "troubleshooting":
            if not report.get("intake", {}).get("date_attended_site"):
                report.setdefault("intake", {})["date_attended_site"] = day["date"]
        else:
            if not report["general"].get("date_of_inspection"):
                report["general"]["date_of_inspection"] = day["date"]
    if ticket["state"] == "scheduled":
        was_state = ticket["state"]
        ticket["state"] = "site_visit"
        log_event(ticket, actor, "site_visit_started", was_state, "site_visit", f"first checklist opened on {day['date']}")
    return ticket


def action_checklist_item(db, ticket, data):
    actor = data.get("actor")
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        raise ApiError("Couldn't find that visit day — try refreshing the page.")
    if day["date"] != today_str():
        raise ApiError(f"This checklist can only be edited on {day['date']}.")
    item_id = (data.get("item_id") or "").strip()
    status = (data.get("status") or "").strip()
    if status not in ("pass", "fail", "na"):
        raise ApiError("Status must be Pass, Fail, or N/A.")
    cl = day["checklist"]
    if cl["checklist_completed_at"]:
        raise ApiError("This checklist has already been submitted and can't be edited.")
    item = next((i for i in cl["items"] if i["id"] == item_id), None)
    if not item:
        raise ApiError("Couldn't find that checklist item — try refreshing the page.")
    if status == "fail" and not (data.get("note") or "").strip() and not data.get("attachments"):
        raise ApiError("Document what's wrong (note, photo, video, or voice note) before marking a fail.")
    item["status"] = status
    item["note"] = (data.get("note") or "").strip()
    item["attachments"] = data.get("attachments") or []
    log_event(ticket, actor, "checklist_item", ticket["state"], ticket["state"], f"day={day['date']} {item_id}={status}")
    return ticket


def action_checklist_general(db, ticket, data):
    actor = data.get("actor")
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        raise ApiError("Couldn't find that visit day — try refreshing the page.")
    if day["date"] != today_str():
        raise ApiError(f"This checklist can only be edited on {day['date']}.")
    cl = day["checklist"]
    if cl["checklist_completed_at"]:
        raise ApiError("This checklist has already been submitted and can't be edited.")
    cl["general_remarks"] = (data.get("remarks") or "").strip()
    cl["general_media"] = data.get("media") or []
    log_event(ticket, actor, "checklist_general", ticket["state"], ticket["state"], f"day={day['date']}")
    return ticket


def action_checklist_pdf(db, ticket, data):
    """Sets (or clears, when pdf_file is blank/omitted) the single PDF upload
    for an NTP visit day's checklist — the NTP equivalent of
    action_checklist_item/action_checklist_general for the item-based
    templates. Uploading a new file simply replaces the previous one (one
    slot only, per the simplified NTP flow)."""
    actor = data.get("actor")
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        raise ApiError("Couldn't find that visit day — try refreshing the page.")
    if day["date"] != today_str():
        raise ApiError(f"This checklist can only be edited on {day['date']}.")
    cl = day["checklist"]
    if cl["checklist_completed_at"]:
        raise ApiError("This checklist has already been submitted and can't be edited.")
    if cl.get("template") != "ntp":
        raise ApiError("This visit day doesn't use a PDF upload.")
    pdf_file = (data.get("pdf_file") or "").strip() or None
    cl["pdf_file"] = pdf_file
    log_event(ticket, actor, "checklist_pdf", ticket["state"], ticket["state"],
              f"day={day['date']} file={pdf_file or '(removed)'}")
    return ticket


def action_submit_checklist(db, ticket, data):
    actor = data.get("actor")
    day = find_visit_day(ticket, data.get("day_id"))
    if not day:
        raise ApiError("Couldn't find that visit day — try refreshing the page.")
    if day["date"] != today_str():
        raise ApiError(f"This checklist can only be submitted on {day['date']}.")
    if ticket.get("reschedule_requested"):
        raise ApiError("A reschedule has been requested for this ticket — the visit isn't proceeding as scheduled, "
                        "so this checklist can't be submitted until CS books a new date and clears the request.")
    cl = day["checklist"]
    if cl.get("template") == "ntp":
        if not cl.get("pdf_file"):
            raise ApiError("Upload the PDF document before submitting.")
    else:
        unanswered = [i["id"] for i in cl["items"] if i["status"] is None]
        if unanswered:
            raise ApiError(f"{len(unanswered)} item(s) still need an answer before submitting.")
    cl["checklist_completed_at"] = now_iso()
    cl["submitted_by"] = actor
    day["status"] = "submitted"
    duration_note = ""
    if cl["checklist_started_at"]:
        mins = round((datetime.fromisoformat(cl["checklist_completed_at"]) -
                      datetime.fromisoformat(cl["checklist_started_at"])).total_seconds() / 60, 1)
        duration_note = f"took {mins} min"
    log_event(ticket, actor, "checklist_submitted", ticket["state"], ticket["state"], f"day={day['date']} {duration_note}".strip())
    reconcile_visit_days(ticket)  # may advance straight to report_drafting if this was the last unresolved day
    return ticket


REPORT_SECTIONS = (
    "general", "electrical", "summary", "report_notes", "installation_improvement",
    # Format B (troubleshooting) flat sections — same generic patch action.
    "checklist_info", "intake", "signatures",
)


def action_report_section(db, ticket, data):
    """Generic patch for the report's flat sub-sections (general info, summary,
    etc.) — one action instead of a dozen near-identical ones."""
    actor = data.get("actor")
    section = data.get("section")
    if section not in REPORT_SECTIONS:
        raise ApiError("Couldn't find that report section — try refreshing the page.")
    patch = data.get("patch") or {}
    ticket["report"].setdefault(section, {}).update(patch)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_section", ticket["state"], ticket["state"], section)
    return ticket


def action_report_checklist_item(db, ticket, data):
    actor = data.get("actor")
    item_id = data.get("item_id")
    result = data.get("result")
    if result not in (None, "accept", "reject"):
        raise ApiError("Result must be Accept, Reject, or cleared.")
    item = next((i for i in ticket["report"]["maintenance_checklist"] if i["id"] == item_id), None)
    if not item:
        raise ApiError("Couldn't find that checklist item — try refreshing the page.")
    item["result"] = result
    item["remarks"] = (data.get("remarks") or "").strip()
    item["extra"] = (data.get("extra") or "").strip()
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_checklist_item", ticket["state"], ticket["state"], f"{item_id}={result}")
    return ticket


def _find_inverter(ticket, inverter_id):
    inv = next((i for i in ticket["report"]["electrical"]["inverters"] if i["id"] == inverter_id), None)
    if not inv:
        raise ApiError("Couldn't find that inverter — try refreshing the page.")
    return inv


def _find_mppt(inverter, mppt_id):
    m = next((m for m in inverter["mppts"] if m["id"] == mppt_id), None)
    if not m:
        raise ApiError("Couldn't find that MPPT — try refreshing the page.")
    return m


def action_report_add_inverter(db, ticket, data):
    actor = data.get("actor")
    inverters = ticket["report"]["electrical"].setdefault("inverters", [])
    new_id = (max([i["id"] for i in inverters], default=0)) + 1
    label = (data.get("label") or "").strip() or f"Inverter {new_id}"
    inverters.append({"id": new_id, "label": label, "mppts": []})
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_inverter_add", ticket["state"], ticket["state"], label)
    return ticket


def action_report_remove_inverter(db, ticket, data):
    actor = data.get("actor")
    inverters = ticket["report"]["electrical"].setdefault("inverters", [])
    inv = _find_inverter(ticket, data.get("inverter_id"))
    inverters.remove(inv)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_inverter_remove", ticket["state"], ticket["state"], inv["label"])
    return ticket


def action_report_add_mppt(db, ticket, data):
    actor = data.get("actor")
    inv = _find_inverter(ticket, data.get("inverter_id"))
    new_id = (max([m["id"] for m in inv["mppts"]], default=0)) + 1
    label = (data.get("label") or "").strip() or f"MPPT {new_id}"
    inv["mppts"].append({"id": new_id, "label": label, "strings": []})
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_mppt_add", ticket["state"], ticket["state"], f"{inv['label']} / {label}")
    return ticket


def action_report_remove_mppt(db, ticket, data):
    actor = data.get("actor")
    inv = _find_inverter(ticket, data.get("inverter_id"))
    m = _find_mppt(inv, data.get("mppt_id"))
    inv["mppts"].remove(m)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_mppt_remove", ticket["state"], ticket["state"], f"{inv['label']} / {m['label']}")
    return ticket


def action_report_add_string(db, ticket, data):
    actor = data.get("actor")
    inv = _find_inverter(ticket, data.get("inverter_id"))
    m = _find_mppt(inv, data.get("mppt_id"))
    new_id = (max([s["id"] for s in m["strings"]], default=0)) + 1
    label = (data.get("label") or "").strip() or f"String {new_id}"
    m["strings"].append({"id": new_id, "label": label, "voltage_v": "", "pos_to_ground_v": "", "neg_to_ground_v": "", "status": ""})
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_string_add", ticket["state"], ticket["state"], f"{inv['label']} / {m['label']} / {label}")
    return ticket


def action_report_remove_string(db, ticket, data):
    actor = data.get("actor")
    inv = _find_inverter(ticket, data.get("inverter_id"))
    m = _find_mppt(inv, data.get("mppt_id"))
    s = next((s for s in m["strings"] if s["id"] == data.get("string_id")), None)
    if not s:
        raise ApiError("Couldn't find that string — try refreshing the page.")
    m["strings"].remove(s)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_string_remove", ticket["state"], ticket["state"], f"{inv['label']} / {m['label']} / {s['label']}")
    return ticket


def action_report_update_string(db, ticket, data):
    actor = data.get("actor")
    inv = _find_inverter(ticket, data.get("inverter_id"))
    m = _find_mppt(inv, data.get("mppt_id"))
    s = next((s for s in m["strings"] if s["id"] == data.get("string_id")), None)
    if not s:
        raise ApiError("Couldn't find that string — try refreshing the page.")
    for field in ("voltage_v", "pos_to_ground_v", "neg_to_ground_v", "status"):
        if field in data:
            s[field] = (data[field] or "").strip()
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_string_update", ticket["state"], ticket["state"], "")
    return ticket


# ---------- Format B actions: inspection checklist, DC strings, narrative lines ----------

INSPECTION_GROUPS = ("ac_three_phase", "ac_single_phase")
INSPECTION_REMARKS = (None, "ok", "not_ok")


def action_report_inspection_measurement(db, ticket, data):
    """Updates one reading in the Format B diagnostic checklist — either an
    AC phase measurement (ac_three_phase / ac_single_phase) or one of the 7
    standalone line items (Solar Panel Visual Inspection, Grounding
    Inspection, etc.)."""
    actor = data.get("actor")
    group = data.get("group")
    key = data.get("key")
    value = (data.get("value") or "").strip()
    remark = data.get("remark")
    if remark not in INSPECTION_REMARKS:
        raise ApiError("Remark must be OK, Not OK, or cleared.")
    checklist = ticket["report"].setdefault("inspection_checklist", {})
    if group in INSPECTION_GROUPS:
        entries = checklist.setdefault(group, {})
        if key not in entries:
            raise ApiError("Couldn't find that measurement — try refreshing the page.")
        entries[key]["value"] = value
        entries[key]["remark"] = remark
    elif group == "line_items":
        item = next((i for i in checklist.get("line_items", []) if i["id"] == key), None)
        if not item:
            raise ApiError("Couldn't find that inspection item — try refreshing the page.")
        item["value"] = value
        item["remark"] = remark
    else:
        raise ApiError("Couldn't find that inspection group — try refreshing the page.")
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_inspection_measurement", ticket["state"], ticket["state"], f"{group}.{key}")
    return ticket


def action_report_add_dc_string(db, ticket, data):
    actor = data.get("actor")
    strings = ticket["report"].setdefault("inspection_checklist", {}).setdefault("dc_strings", [])
    new_id = (max([s["id"] for s in strings], default=0)) + 1
    strings.append(build_dc_string(new_id))
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_dc_string_add", ticket["state"], ticket["state"], f"String {new_id}")
    return ticket


def action_report_remove_dc_string(db, ticket, data):
    actor = data.get("actor")
    strings = ticket["report"].setdefault("inspection_checklist", {}).setdefault("dc_strings", [])
    s = next((s for s in strings if s["id"] == data.get("string_id")), None)
    if not s:
        raise ApiError("Couldn't find that string — try refreshing the page.")
    if len(strings) <= 1:
        raise ApiError("At least one DC string is required.")
    strings.remove(s)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_dc_string_remove", ticket["state"], ticket["state"], s["label"])
    return ticket


def action_report_update_dc_string(db, ticket, data):
    actor = data.get("actor")
    strings = ticket["report"].setdefault("inspection_checklist", {}).setdefault("dc_strings", [])
    s = next((s for s in strings if s["id"] == data.get("string_id")), None)
    if not s:
        raise ApiError("Couldn't find that string — try refreshing the page.")
    for field in ("voltage_v", "positive_ground_v", "negative_ground_v"):
        if field in data:
            s[field] = (data[field] or "").strip()
    for field in ("voltage_remark", "positive_ground_remark", "negative_ground_remark"):
        if field in data:
            remark = data[field]
            if remark not in INSPECTION_REMARKS:
                raise ApiError("Remark must be OK, Not OK, or cleared.")
            s[field] = remark
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_dc_string_update", ticket["state"], ticket["state"], s["label"])
    return ticket


# "Reported Issues", "Root Causes", "Actions Taken", "Conclusions", "Remarks" —
# five sections in the Format B report, all the same shape: a repeatable list
# of {id, text, photos[]} lines. One set of generic actions handles all five.
NARRATIVE_SECTIONS = ("reported_issues", "root_causes", "actions_taken", "conclusions", "remarks")


def _find_narrative_line(ticket, section, line_id):
    if section not in NARRATIVE_SECTIONS:
        raise ApiError("Couldn't find that report section — try refreshing the page.")
    lines = ticket["report"].setdefault(section, [])
    line = next((l for l in lines if l["id"] == line_id), None)
    if not line:
        raise ApiError("Couldn't find that line — try refreshing the page.")
    return lines, line


def action_report_narrative_add_line(db, ticket, data):
    actor = data.get("actor")
    section = data.get("section")
    if section not in NARRATIVE_SECTIONS:
        raise ApiError("Couldn't find that report section — try refreshing the page.")
    lines = ticket["report"].setdefault(section, [])
    new_id = (max([l["id"] for l in lines], default=0)) + 1
    lines.append({"id": new_id, "text": "", "photos": []})
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_narrative_add_line", ticket["state"], ticket["state"], section)
    return ticket


def action_report_narrative_update_line(db, ticket, data):
    actor = data.get("actor")
    section = data.get("section")
    _, line = _find_narrative_line(ticket, section, data.get("line_id"))
    line["text"] = (data.get("text") or "").strip()
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_narrative_update_line", ticket["state"], ticket["state"], f"{section}:{line['id']}")
    return ticket


def action_report_narrative_remove_line(db, ticket, data):
    actor = data.get("actor")
    section = data.get("section")
    lines, line = _find_narrative_line(ticket, section, data.get("line_id"))
    lines.remove(line)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_narrative_remove_line", ticket["state"], ticket["state"], f"{section}:{line['id']}")
    return ticket


def action_report_narrative_add_photo(db, ticket, data):
    actor = data.get("actor")
    section = data.get("section")
    _, line = _find_narrative_line(ticket, section, data.get("line_id"))
    label = (data.get("label") or "").strip()
    if not label:
        raise ApiError("A label is required for the mock upload.")
    if len(line["photos"]) >= 10:
        raise ApiError("A maximum of 10 photos per line is allowed.")
    line["photos"].append(label)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_narrative_add_photo", ticket["state"], ticket["state"], f"{section}:{line['id']}")
    return ticket


def action_report_narrative_remove_photo(db, ticket, data):
    actor = data.get("actor")
    section = data.get("section")
    _, line = _find_narrative_line(ticket, section, data.get("line_id"))
    index = data.get("index")
    if not isinstance(index, int) or not (0 <= index < len(line["photos"])):
        raise ApiError("Couldn't find that photo to remove — try refreshing the page.")
    line["photos"].pop(index)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_narrative_remove_photo", ticket["state"], ticket["state"], f"{section}:{line['id']}")
    return ticket


REPORT_MEDIA_CATEGORIES = ("pv_before", "pv_after", "inverter", "ac_photo", "dc_photo", "fit_meter")


def action_report_add_media(db, ticket, data):
    """Mock upload, same pattern used for visit/report photos elsewhere in
    this demo — a label stands in for a real file since there's no media
    capture in this environment."""
    actor = data.get("actor")
    category = data.get("category")
    label = (data.get("label") or "").strip()
    if not label:
        raise ApiError("A label is required for the mock upload.")
    if category in REPORT_MEDIA_CATEGORIES:
        ticket["report"]["media"].setdefault(category, []).append(label)
    elif category == "performance_graph":
        ticket["report"]["summary"].setdefault("performance_graph", []).append(label)
    elif category == "additional":
        ticket["report"].setdefault("additional_media", []).append(label)
    elif category == "site_photos":  # Format B's standalone gallery (separate from Additional Media)
        ticket["report"].setdefault("site_photos", []).append(label)
    else:
        raise ApiError("Couldn't find that media category — try refreshing the page.")
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_media_add", ticket["state"], ticket["state"], category)
    return ticket


def action_report_remove_media(db, ticket, data):
    actor = data.get("actor")
    category = data.get("category")
    index = data.get("index")
    if category in REPORT_MEDIA_CATEGORIES:
        lst = ticket["report"]["media"].setdefault(category, [])
    elif category == "performance_graph":
        lst = ticket["report"]["summary"].setdefault("performance_graph", [])
    elif category == "additional":
        lst = ticket["report"].setdefault("additional_media", [])
    elif category == "site_photos":
        lst = ticket["report"].setdefault("site_photos", [])
    else:
        raise ApiError("Couldn't find that media category — try refreshing the page.")
    if not isinstance(index, int) or not (0 <= index < len(lst)):
        raise ApiError("Couldn't find that photo to remove — try refreshing the page.")
    removed = lst.pop(index)
    ticket["report"]["updated_at"] = now_iso()
    log_event(ticket, actor, "report_media_remove", ticket["state"], ticket["state"], f"{category}: {removed}")
    return ticket


def action_submit_report(db, ticket, data):
    actor = data.get("actor")
    report = ticket["report"]
    if report["status"] == "submitted":
        raise ApiError("This report has already been submitted.")
    # The "required before submit" field differs per report format.
    if report.get("format") == "troubleshooting":
        if not report.get("intake", {}).get("date_attended_site"):
            raise ApiError("Date Attended Site is required before submitting.")
    else:
        if not report["general"]["date_of_inspection"]:
            raise ApiError("Date of Inspection is required before submitting.")
    unresolved = [d for d in ticket.get("visit_days", []) if d["status"] not in ("submitted", "unfinished")]
    if unresolved:
        raise ApiError(f"{len(unresolved)} visit day(s) still have a pending safety checklist — complete those before submitting the report.")
    ticket["report"]["status"] = "submitted"
    ticket["report"]["submitted_by"] = actor
    ticket["report"]["submitted_at"] = now_iso()
    ticket["report"]["updated_at"] = now_iso()
    was_state = ticket["state"]
    if ticket["state"] == "report_drafting":
        ticket["state"] = "engineer_review"
    log_event(ticket, actor, "report_submitted", was_state, ticket["state"], "")
    return ticket


def action_report_approve(db, ticket, data):
    actor = data.get("actor")
    if ticket["report"]["status"] != "submitted":
        raise ApiError("Only a submitted report can be approved.")
    ticket["report"]["status"] = "approved"
    ticket["report"]["approved_by"] = actor
    ticket["report"]["approved_at"] = now_iso()
    ticket["report"]["updated_at"] = now_iso()
    was_state = ticket["state"]
    if ticket["state"] == "engineer_review":
        ticket["state"] = "approved"
    log_event(ticket, actor, "report_approved", was_state, ticket["state"], "")
    return ticket


def action_report_reject(db, ticket, data):
    actor = data.get("actor")
    reason = (data.get("reason") or "").strip()
    if ticket["report"]["status"] != "submitted":
        raise ApiError("Only a submitted report can be rejected.")
    if not reason:
        raise ApiError("A reason is required to reject a report.")
    ticket["report"]["status"] = "draft"
    ticket["report"].setdefault("report_rejections", []).append({"reason": reason, "actor": actor, "at": now_iso()})
    ticket["report"]["updated_at"] = now_iso()
    was_state = ticket["state"]
    if ticket["state"] == "engineer_review":
        ticket["state"] = "report_drafting"
    log_event(ticket, actor, "report_rejected", was_state, ticket["state"], reason)
    return ticket



def action_close(db, ticket, data):
    actor = data.get("actor")
    if ticket["state"] != "approved":
        raise ApiError("Ticket must be Approved before it can be closed.")
    ticket["state"] = "closed"
    ticket["closure"] = {"type": "resolved", "reason": None, "closed_at": now_iso()}
    log_event(ticket, actor, "close", "approved", "closed", "resolved")
    return ticket


def action_early_close(db, ticket, data):
    actor = data.get("actor")
    reason = (data.get("reason") or "").strip()
    if ticket["state"] not in ACTIVE_STATES_FOR_EARLY_CLOSE:
        raise ApiError("Early closure is not available once a report has been approved — use normal closure.")
    if not reason:
        raise ApiError("A reason is required for early closure.")
    prev = ticket["state"]
    ticket["state"] = "closed"
    ticket["closure"] = {"type": "early", "reason": reason, "closed_at": now_iso()}
    log_event(ticket, actor, "early_close", prev, "closed", reason)
    return ticket

def action_delete_ticket(db, ticket, data):
    """CS/Admin removes a ticket created by mistake. Only allowed while the
    ticket is still 'Created' (nothing scheduled/visited/reported yet) — once
    real work has started, use Close Early instead so the record is kept."""
    if ticket["state"] != "created":
        raise ApiError("Only a ticket that hasn't been scheduled yet can be deleted. Use Close Early for one already in progress.")
    db["tickets"].remove(ticket)
    return ticket

def action_snooze(db, ticket, data):
    actor = data.get("actor")
    until = (data.get("until") or "").strip()
    reason = (data.get("reason") or "").strip()
    if not until:
        raise ApiError("A resurface date is required to snooze a ticket.")
    ticket["snooze_until"] = until
    ticket["snooze_reason"] = reason
    ticket["snoozed_at"] = now_iso()
    log_event(ticket, actor, "snooze", ticket["state"], ticket["state"], reason or f"until {until}")
    return ticket

def action_reschedule(db, ticket, data):
    """Technician-initiated: whole ticket can't proceed as scheduled (e.g. tech
    is sick, site inaccessible). Doesn't touch ticket['state'] — just flags the
    ticket so CS sees it and re-plans. CS clears the flag once they've booked
    a new date (see action_clear_reschedule)."""
    actor = data.get("actor")
    reason = (data.get("reason") or "").strip()
    if not reason:
        raise ApiError("A reason is required to request a reschedule.")
    if ticket.get("reschedule_requested"):
        raise ApiError("A reschedule has already been requested for this ticket.")
    ticket["reschedule_requested"] = True
    ticket["reschedule_reason"] = reason
    ticket["reschedule_requested_at"] = now_iso()
    log_event(ticket, actor, "reschedule_request", ticket["state"], ticket["state"], reason)
    return ticket


def action_clear_reschedule(db, ticket, data):
    """CS acknowledges the reschedule request — e.g. after rebooking the visit
    date. Clears the flag so it drops off the dashboard."""
    actor = data.get("actor")
    if not ticket.get("reschedule_requested"):
        raise ApiError("This ticket has no pending reschedule request.")
    ticket["reschedule_requested"] = False
    log_event(ticket, actor, "reschedule_cleared", ticket["state"], ticket["state"], "")
    return ticket

def action_update_ticket_details(db, ticket, data):
    """Fills in the equipment/commercial/additional-info fields that exist on
    every ticket but previously had no edit UI anywhere — CS could set them at
    creation but never come back to fill in what they didn't know yet."""
    actor = data.get("actor")
    if "site" in data:
        ticket["site"] = (data["site"] or "").strip()
    equipment = data.get("equipment") or {}
    for key in ("panels", "inverter_brand", "inverter_model", "nemcd_ref"):
        if key in equipment:
            ticket["equipment"][key] = (equipment[key] or "").strip()
    commercial = data.get("commercial") or {}
    if "dlp_end_date" in commercial:
        ticket["commercial"]["dlp_end_date"] = (commercial["dlp_end_date"] or "").strip()
    if "chargeable_service_call" in commercial:
        ticket["commercial"]["chargeable_service_call"] = bool(commercial["chargeable_service_call"])
    additional = data.get("additional") or {}
    for key in ("so_number", "premium_care_status", "system_size", "assigned_team", "contact_phone", "client_remarks"):
        if key in additional:
            ticket["additional"][key] = (additional[key] or "").strip()
    ticket["updated_at"] = now_iso()
    log_event(ticket, actor, "update_ticket_details", ticket["state"], ticket["state"], "")
    return ticket


def action_message(db, ticket, data):
    actor = (data.get("actor") or "").strip()
    text = (data.get("text") or "").strip()
    if not text:
        raise ApiError("Message text is required.")
    account = find_account_by_name(db, actor)
    if account and account["role"] == "technician":
        raise ApiError("Technicians communicate through their engineer, not the ticket thread.")

    # @mentions (Notification system): each name is validated the same way an
    # assignee is (real account, not a technician — validate_assignable raises
    # otherwise), deduped, and self-mentions are dropped (no point notifying
    # yourself about your own message).
    mentions = []
    for name in data.get("mentions", []) or []:
        name = (name or "").strip()
        if not name or name == actor or name in mentions:
            continue
        validate_assignable(db, name)
        mentions.append(name)

    message = {
        "id": len(ticket.get("messages", [])) + 1,
        "author": actor or "unknown",
        "ts": now_iso(),
        "text": text,
        "mentions": mentions,
    }
    ticket.setdefault("messages", []).append(message)
    ticket["updated_at"] = now_iso()
    for name in mentions:
        queue_mock_email(name, ticket, actor or "unknown", text)
    return ticket


def action_mark_ticket_read(db, ticket, data):
    """Lets the current user "clear" their @mention notifications for this
    ticket — called whenever they open the ticket's detail page. Records a
    per-account high-water-mark (how many messages they've seen) rather than
    touching event_log, since viewing a ticket isn't a business event worth
    auditing."""
    actor = (data.get("actor") or "").strip()
    if not actor:
        raise ApiError("An actor is required.")
    ticket.setdefault("mention_reads", {})[actor] = len(ticket.get("messages", []))
    return ticket


def action_override_report_timestamp(db, ticket, data):
    """HOD/Admin-only safeguard (Fasa 5, Item 22): lets the HOD correct a
    wrong "Report Started" or "Report Submitted" time used for duration
    tracking, WITHOUT touching the original event_log — that stays an
    honest record of what actually happened. The correction is layered on
    top as an override, with who/when/why recorded for audit."""
    actor = (data.get("actor") or "").strip()
    account = find_account_by_name(db, actor)
    if not account or account["role"] != "admin":
        raise ApiError("Only the HOD/Admin can correct a report timestamp.")

    field = (data.get("field") or "").strip()
    if field not in ("report_started_at", "report_submitted_at"):
        raise ApiError("Couldn't tell which timestamp to correct — try reopening this ticket and trying again.")

    value = (data.get("value") or "").strip()
    if not value:
        raise ApiError("A corrected date/time is required.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError("That doesn't look like a valid date/time — please try again.")

    reason = (data.get("reason") or "").strip()
    if not reason:
        raise ApiError("A reason is required when correcting a report timestamp.")

    overrides = ticket.setdefault("report", {}).setdefault("duration_overrides", {})
    old = (overrides.get(field) or {}).get("value")
    overrides[field] = {"value": value, "reason": reason, "by": actor, "at": now_iso()}
    log_event(ticket, actor, "report_timestamp_override", ticket["state"], ticket["state"],
              f"{field}: {old or '(none)'} -> {value} ({reason})")
    return ticket


def action_set_technician_team(db, data):
    """HOD/Admin or CS: assigns a technician to Team 1 or Team 2. Enforced
    here, server-side — not just hidden in the UI."""
    actor = (data.get("actor") or "").strip()
    actor_account = find_account_by_name(db, actor)
    if not actor_account or actor_account["role"] not in ("admin", "cs"):
        raise ApiError("Only HOD/Admin or CS can change a technician's team.")

    name = (data.get("name") or "").strip()
    team = (data.get("team") or "").strip()
    if team not in ("Team 1", "Team 2"):
        raise ApiError("Team must be 'Team 1' or 'Team 2'.")

    account = find_account_by_name(db, name)
    if not account or account["role"] != "technician":
        raise ApiError(f"'{name}' is not a known technician account.")

    account["team"] = team
    return account


# ---------- Knowledge Base Articles (staff-authored, 5 Okt) ----------
# Separate from the hardcoded reference guides (PPE Guide, Intern Guide, etc.
# — those stay hand-coded in knowledge-base.html). This is a real, persisted
# collection (db.json "kb_articles") so staff can add/edit/publish their own
# articles without a developer touching code. Not ticket-scoped, so these
# don't go through the /api/tickets/<id>/<action> dispatcher — they get their
# own flat endpoints (see do_GET/do_POST), same pattern as /api/clients.

KB_ARTICLE_CATEGORIES = ("Customer Guides", "General Knowledge", "Intern Resources", "Flowcharts", "Emergency Response")

# Matches the 4-tier visibility already used for the hardcoded reference
# guides in knowledge-base.html (KB_VISIBILITY_META) — kept identical so a
# staff-authored article and a built-in guide behave the same way in the
# "Preview as customer" toggle.
KB_VISIBILITY_LEVELS = ("internal", "intern_admin", "customer", "public")

# Roles allowed to author Knowledge Base articles — same roles that get
# assigned to tickets (technicians use the job board instead, see
# validate_assignable); matches Jarvis's decision (5 Okt) that any staff
# role, not just admin/HOD, can contribute articles.
KB_ARTICLE_AUTHOR_ROLES = ("admin", "engineer", "cs")


def validate_kb_author(db, actor):
    account = find_account_by_name(db, actor)
    if not account or account["role"] not in KB_ARTICLE_AUTHOR_ROLES:
        raise ApiError("Only admin, engineer, or CS accounts can manage Knowledge Base articles.")
    return account


def find_kb_article(db, article_id):
    for a in db.get("kb_articles", []):
        if a["id"] == article_id:
            return a
    raise ApiError("This article could not be found — it may have been deleted.", 404)


def action_kb_article_create(db, data):
    actor = (data.get("actor") or "").strip()
    validate_kb_author(db, actor)

    title = (data.get("title") or "").strip()
    category = (data.get("category") or "").strip()
    visibility = (data.get("visibility") or "internal").strip()
    body = (data.get("body") or "").strip()
    attachments = [a.strip() for a in (data.get("attachments") or []) if (a or "").strip()]

    if not title:
        raise ApiError("Article title is required.")
    if category not in KB_ARTICLE_CATEGORIES:
        raise ApiError("A valid category is required.")
    if visibility not in KB_VISIBILITY_LEVELS:
        raise ApiError("A valid visibility scope is required.")
    if len(attachments) > 10:
        raise ApiError("A maximum of 10 attachments is allowed.")

    article = {
        "id": next_kb_article_id(db),
        "title": title,
        "category": category,
        "visibility": visibility,
        "body": body,
        # New articles always start as a draft, regardless of what the
        # client sends — publishing is a separate, deliberate step
        # (action_kb_article_toggle_status), per Jarvis's decision (5 Okt).
        "status": "draft",
        "attachments": attachments,  # mock upload: filename labels only, no real file storage (same pattern as report media)
        "created_by": actor,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db.setdefault("kb_articles", []).insert(0, article)
    return article


def action_kb_article_update(db, article, data):
    actor = (data.get("actor") or "").strip()
    validate_kb_author(db, actor)

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            raise ApiError("Article title is required.")
        article["title"] = title
    if "category" in data:
        category = (data.get("category") or "").strip()
        if category not in KB_ARTICLE_CATEGORIES:
            raise ApiError("A valid category is required.")
        article["category"] = category
    if "visibility" in data:
        visibility = (data.get("visibility") or "").strip()
        if visibility not in KB_VISIBILITY_LEVELS:
            raise ApiError("A valid visibility scope is required.")
        article["visibility"] = visibility
    if "body" in data:
        article["body"] = (data.get("body") or "").strip()
    if "attachments" in data:
        attachments = [a.strip() for a in (data.get("attachments") or []) if (a or "").strip()]
        if len(attachments) > 10:
            raise ApiError("A maximum of 10 attachments is allowed.")
        article["attachments"] = attachments

    article["updated_at"] = now_iso()
    return article


def action_kb_article_toggle_status(db, article, data):
    actor = (data.get("actor") or "").strip()
    validate_kb_author(db, actor)
    article["status"] = "draft" if article["status"] == "published" else "published"
    article["updated_at"] = now_iso()
    return article


def action_kb_article_delete(db, article, data):
    actor = (data.get("actor") or "").strip()
    validate_kb_author(db, actor)
    db["kb_articles"].remove(article)
    return article


KB_ARTICLE_ACTIONS = {
    "update": action_kb_article_update,
    "toggle_status": action_kb_article_toggle_status,
    "delete": action_kb_article_delete,
}


# Fasa 6 audit (3 Okt) — once a ticket is "closed" (normal close OR early
# close), nothing about its actual work (checklist, report, assignment,
# schedule) should be able to change any more — a closed ticket is a
# terminal/historical record. Before this set existed, almost every action
# below had NO check for ticket["state"] == "closed" at all, so (confirmed by
# live test) a technician could still submit a checklist/report on a ticket
# that was already closed, silently corrupting what "closed" is supposed to
# mean for the audit trail.
#
# This set is the SHORT list of actions that are still legitimately allowed
# on a closed ticket — everything else gets blocked centrally in do_POST
# (see the `fn.__name__ not in ACTIONS_ALLOWED_ON_CLOSED_TICKET` check below):
#   - "message"/"mark_ticket_read": a closed ticket can still receive a
#     follow-up note or be marked as read — that's not "work", just audit.
#   - "override_report_timestamp": HOD correcting a historical timestamp on
#     a report AFTER the ticket is closed is the exact use-case this exists
#     for (see Fasa 5, Item 22).
#   - "delete_ticket": admin removing a mistaken ticket must still work
#     regardless of state (it has its own state check already).
#   - "close"/"early_close": these already raise their own, more specific
#     error ("must be Approved first" / "early closure not available") when
#     called on an already-closed ticket, via their own state checks above —
#     exempting them here just keeps that clearer message instead of the
#     generic one below.
ACTIONS_ALLOWED_ON_CLOSED_TICKET = {
    "message", "mark_ticket_read", "override_report_timestamp",
    "delete_ticket", "close", "early_close",
}

# Fasa 8 audit (5 Okt) — central guard: once a report has been submitted
# (status "submitted" or "approved"), its content must be frozen — only
# submit_report/report_approve/report_reject (which have their own status
# checks) and the read-only GET are allowed to touch it. Before this guard,
# every report_* content-edit action below had NO check on report["status"]
# at all, so (confirmed by live test) an admin/engineer/CS could still
# silently overwrite an already-APPROVED report's data via report_section
# etc., with no error, no re-review, and no trace that it happened after
# approval — the approval step meant nothing. A report goes back to "draft"
# (and becomes editable again) only via report_reject.
REPORT_EDIT_ACTIONS = {
    "report_section", "report_checklist_item",
    "report_add_inverter", "report_remove_inverter",
    "report_add_mppt", "report_remove_mppt",
    "report_add_string", "report_remove_string", "report_update_string",
    "report_add_media", "report_remove_media",
    "report_inspection_measurement",
    "report_add_dc_string", "report_remove_dc_string", "report_update_dc_string",
    "report_narrative_add_line", "report_narrative_update_line", "report_narrative_remove_line",
    "report_narrative_add_photo", "report_narrative_remove_photo",
}
REPORT_LOCKED_STATUSES = {"submitted", "approved"}

ACTIONS = {
    "assign": action_assign,
    "link_events": action_link_events,
    "unlink_event": action_unlink_event,
    "set_day_people": action_set_day_people,
    "start_checklist": action_start_checklist,
    "checklist_item": action_checklist_item,
    "checklist_general": action_checklist_general,
    "checklist_pdf": action_checklist_pdf,
    "submit_checklist": action_submit_checklist,
    "report_section": action_report_section,
    "report_checklist_item": action_report_checklist_item,
    "report_add_inverter": action_report_add_inverter,
    "report_remove_inverter": action_report_remove_inverter,
    "report_add_mppt": action_report_add_mppt,
    "report_remove_mppt": action_report_remove_mppt,
    "report_add_string": action_report_add_string,
    "report_remove_string": action_report_remove_string,
    "report_update_string": action_report_update_string,
    "report_add_media": action_report_add_media,
    "report_remove_media": action_report_remove_media,
    "report_inspection_measurement": action_report_inspection_measurement,
    "report_add_dc_string": action_report_add_dc_string,
    "report_remove_dc_string": action_report_remove_dc_string,
    "report_update_dc_string": action_report_update_dc_string,
    "report_narrative_add_line": action_report_narrative_add_line,
    "report_narrative_update_line": action_report_narrative_update_line,
    "report_narrative_remove_line": action_report_narrative_remove_line,
    "report_narrative_add_photo": action_report_narrative_add_photo,
    "report_narrative_remove_photo": action_report_narrative_remove_photo,
    "submit_report": action_submit_report,
    "report_approve": action_report_approve,
    "report_reject": action_report_reject,
    "message": action_message,
    "mark_ticket_read": action_mark_ticket_read,
    "update_ticket_details": action_update_ticket_details,
    "close": action_close,
    "early_close": action_early_close,
    "snooze": action_snooze,
    "delete_ticket": action_delete_ticket,
    "reschedule": action_reschedule,
    "clear_reschedule": action_clear_reschedule,
    "override_report_timestamp": action_override_report_timestamp,
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep console quiet

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
        # Every handler expects a JSON object. A list / null / plain string used to crash the
        # request thread and drop the connection with no reply.
        return body if isinstance(body, dict) else {}

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        # Strip any leading slash of either kind BEFORE joining — on Windows,
        # os.path.join silently discards the base directory if the second
        # argument still starts with a separator, which normpath alone does
        # not guarantee to remove.
        rel = path.replace("\\", "/").lstrip("/")
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        static_dir_norm = os.path.normpath(STATIC_DIR)
        if not full.startswith(static_dir_norm) or not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        with DB_LOCK:
            return self._handle_get()

    def _handle_get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/accounts":
            db = load_db()
            self._send_json({"accounts": db.get("accounts", [])})
            return
        if path == "/api/clients":
            db = load_db()
            self._send_json({"clients": db.get("clients", [])})
            return
        if path == "/api/calendar_events":
            db = load_db()
            self._send_json({"calendar_events": db.get("calendar_events", [])})
            return
        if path == "/api/kb_articles":
            db = load_db()
            self._send_json({"kb_articles": db.get("kb_articles", [])})
            return
        m = re.match(r"^/api/clients/([^/]+)$", path)
        if m:
            db = load_db()
            c = find_client(db, m.group(1))
            if not c:
                self._send_json({"error": "Client not found"}, 404)
            else:
                self._send_json(c)
            return
        if path == "/api/tickets":
            db = load_db()
            changed = False
            for t in db["tickets"]:
                # Fasa 6 audit (3 Okt) — this list endpoint used to skip the
                # same self-heal that find_ticket() (the single-ticket GET)
                # always runs, so a ticket with report=None/wrong-format or a
                # stale checklist template could reach this list un-migrated.
                # Nothing crashes today only because every page that reads
                # t.report here happens to also guard on t.state !== "created"
                # — but that's incidental, not guaranteed. Run the same
                # self-heal here too, so the list endpoint gives the same
                # guarantee ("ticket always has a correctly-shaped report")
                # as the single-ticket one.
                if migrate_report_format(db, t):
                    changed = True
                if migrate_checklist_template(db, t):
                    changed = True
                if reconcile_visit_days(t):
                    changed = True
            if changed:
                save_db(db)
            self._send_json({"tickets": db["tickets"], "settings": db.get("settings", {})})
            return
        m = re.match(r"^/api/tickets/([^/]+)$", path)
        if m:
            db = load_db()
            try:
                t = find_ticket(db, m.group(1))
                if reconcile_visit_days(t):
                    save_db(db)
                self._send_json(t)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            return
        if path == "/api/settings":
            db = load_db()
            self._send_json(db.get("settings", {}))
            return
        self._serve_static(path)

    def do_POST(self):
        # Refuse absurdly large requests before reading them (db.json itself is only a few MB).
        try:
            too_big = int(self.headers.get("Content-Length", 0) or 0) > MAX_REQUEST_BYTES
        except ValueError:
            too_big = True
        if too_big:
            self.close_connection = True
            self._send_json({"error": "That request is too large."}, 413)
            return
        with DB_LOCK:
            return self._handle_post()

    def _handle_post(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json_body()
        # Knowledge Base pages already escape their own output, so leave KB text as typed.
        if not path.startswith("/api/kb_articles"):
            data = neutralize_html(data)

        if path == "/api/clients":
            db = load_db()
            try:
                c = action_create_client(db, data)
                save_db(db)
                self._send_json(c, 201)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            except Exception as e:
                # Fasa 7 audit (3 Okt) — safety net: any unexpected error
                # (not an ApiError) used to escape as a raw traceback, which
                # just drops the connection instead of a clean JSON error.
                self._send_json({"error": "Something went wrong creating this client. Please try again."}, 500)
            return

        if path == "/api/calendar_events":
            db = load_db()
            try:
                e = action_create_calendar_event(db, data)
                save_db(db)
                self._send_json(e, 201)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            except Exception as e:
                # Fasa 7 audit (3 Okt) — see note on /api/clients above.
                self._send_json({"error": "Something went wrong creating this event. Please try again."}, 500)
            return

        if path == "/api/kb_articles":
            db = load_db()
            try:
                a = action_kb_article_create(db, data)
                save_db(db)
                self._send_json(a, 201)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            except Exception as e:
                # Fasa 7 audit pattern (3 Okt) — see note on /api/clients above.
                self._send_json({"error": "Something went wrong creating this article. Please try again."}, 500)
            return

        if path == "/api/tickets":
            db = load_db()
            try:
                t = action_create(db, data)
                save_db(db)
                self._send_json(t, 201)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            except Exception as e:
                # Fasa 7 audit (3 Okt) — see note on /api/clients above.
                self._send_json({"error": "Something went wrong creating this ticket. Please try again."}, 500)
            return

        if path == "/api/settings":
            db = load_db()
            try:
                require_role(db, (data.get("actor") or "").strip(), "update_settings")
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
                return
            db.setdefault("settings", {})
            if "stale_minutes" in data:
                try:
                    db["settings"]["stale_minutes"] = int(data["stale_minutes"])
                except (TypeError, ValueError):
                    self._send_json({"error": "stale_minutes must be a number"}, 400)
                    return
            save_db(db)
            self._send_json(db["settings"])
            return

        if path == "/api/technicians/set_team":
            db = load_db()
            try:
                account = action_set_technician_team(db, data)
                save_db(db)
                self._send_json(account)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            except Exception as e:
                # Fasa 7 audit (3 Okt) — see note on /api/clients above.
                self._send_json({"error": "Something went wrong updating the team. Please try again."}, 500)
            return

        m = re.match(r"^/api/kb_articles/([^/]+)/([a-z_]+)$", path)
        if m:
            article_id, action = m.group(1), m.group(2)
            fn = KB_ARTICLE_ACTIONS.get(action)
            if not fn:
                self._send_json({"error": f"Unknown action '{action}'"}, 404)
                return
            db = load_db()
            try:
                a = find_kb_article(db, article_id)
                fn(db, a, data)
                save_db(db)
                self._send_json(a)
            except ApiError as e:
                self._send_json({"error": e.message}, e.status)
            except Exception as e:
                # Fasa 7 audit pattern (3 Okt) — see note on /api/clients above.
                self._send_json({"error": "Something went wrong processing this action. Please try again."}, 500)
            return

        m = re.match(r"^/api/tickets/([^/]+)/([a-z_]+)$", path)
        if m:
            ticket_id, action = m.group(1), m.group(2)
            actor = (data.get("actor") or "unknown").strip() or "unknown"
            fn = ACTIONS.get(action)
            if not fn:
                self._send_json({"error": f"Unknown action '{action}'"}, 404)
                return
            db = load_db()
            try:
                t = find_ticket(db, ticket_id)
                # Role check first: wrong role -> 403 before anything else is looked at.
                require_role(db, actor, action)
                if action in CHECKLIST_ACTIONS:
                    require_checklist_access(db, t, actor, data)
                # Fasa 6 audit (3 Okt) — central guard: block every action on a
                # closed ticket except the short allow-list above. Without this,
                # checklist/report actions kept succeeding on closed tickets.
                if t["state"] == "closed" and action not in ACTIONS_ALLOWED_ON_CLOSED_TICKET:
                    raise ApiError("This ticket is closed — it can no longer be changed.")
                # Fasa 8 audit (5 Okt) — central guard: block report content
                # edits once the report has been submitted or approved. See
                # note on REPORT_EDIT_ACTIONS above.
                if action in REPORT_EDIT_ACTIONS and t["report"]["status"] in REPORT_LOCKED_STATUSES:
                    raise ApiError("This report has already been submitted and can no longer be edited. Reject it to reopen for edits.")
                fn(db, t, data)
                reconcile_visit_days(t)
                save_db(db)
                log_action(actor, action, ticket_id, "success")
                self._send_json(t)
            except ApiError as e:
                log_action(actor, action, ticket_id, "failed", e.message)
                self._send_json({"error": e.message}, e.status)
            except (TypeError, AttributeError, ValueError) as e:
                # A value of the wrong kind (a number or list where text is expected, etc.).
                # Nothing was saved (save_db comes after the action), so say so plainly.
                log_action(actor, action, ticket_id, "failed", f"invalid input: {type(e).__name__}: {e}")
                self._send_json({"error": "Some of the values sent were not valid. Nothing was saved."}, 400)
            except Exception as e:
                # Fasa 7 audit (3 Okt) — this is the important one: a few
                # report_* actions (e.g. report_add_media) index into a
                # field (like report["media"]) that only exists on ONE of
                # the two report formats. Calling one of those on a ticket
                # whose report is the OTHER format raises a raw KeyError
                # that nothing used to catch — the connection just dropped
                # with no response at all, instead of a clean error. The
                # real fix is making every report_* action format-aware,
                # but this safety net means ANY future bug in ANY action
                # (not just this one) fails safely with a proper JSON
                # response instead of silently dropping the connection.
                # The real exception (type + message) is still written to
                # om_actions.log for debugging — just not shown to the caller.
                log_action(actor, action, ticket_id, "failed", f"{type(e).__name__}: {e}")
                self._send_json({"error": "Something went wrong processing this action. Please try again or contact support."}, 500)
            return

        self._send_json({"error": "Unknown endpoint"}, 404)


def ensure_db():
    if not os.path.exists(DB_PATH):
        raise SystemExit("db.json not found — run this from the om-ticket-demo folder.")


if __name__ == "__main__":
    ensure_db()
    # Default listen backlog is 5, so a burst of ~20+ simultaneous requests had
    # some connections reset. 128 handled 60 simultaneous writes in testing.
    ThreadingHTTPServer.request_queue_size = 128
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"O&M Ticketing demo running at http://localhost:{PORT}/")
    print("Open that link, then pick a view (Admin / Engineer / CS / Technician).")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass