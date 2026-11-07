#!/usr/bin/env python3
"""
Rebuild a fresh, self-consistent db.json whose dates are relative to TODAY.

Why: the demo data is a fixed snapshot, so after a few days every visit is in the past
and nothing can be tested (checklists are date-gated to the exact day). This script
takes the frozen seed (tools/seed/db.seed.json), shifts EVERY date and timestamp in it
by the same number of days (so "26 Oct" becomes "today" and the history keeps its
shape), then adds a few fresh test scenarios at fixed offsets from today.

Usage (from the project folder, with the server STOPPED):
    python3 tools/reset_demo.py
    python3 tools/reset_demo.py --today 2026-12-01     # pretend today is another day
    python3 tools/reset_demo.py --out /tmp/test_db.json # write somewhere else

"Today" is Malaysia time (UTC+8), same as the server (OM_TZ_OFFSET_HOURS).
The old db.json is copied to db.before-reset.json first (git-ignored).
Scenario tickets are built by calling server.py's own functions, so they obey every
real rule (roles, technician checks, visit-day creation) instead of hand-written JSON.
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import server  # noqa: E402  (importing does not start the server)

SEED_PATH = os.path.join(HERE, "seed", "db.seed.json")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(T\d{2}:\d{2}:\d{2}\+00:00)?")


def shift_date(s, days):
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def shift_value(o, days):
    """Shift every YYYY-MM-DD (also inside ISO timestamps and inside note text)."""
    if isinstance(o, dict):
        return {k: shift_value(v, days) for k, v in o.items()}
    if isinstance(o, list):
        return [shift_value(v, days) for v in o]
    if isinstance(o, str):
        return DATE_RE.sub(lambda m: shift_date(m.group(1), days) + (m.group(2) or ""), o)
    return o


def iso_days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- scenarios
def build_scenarios(db, today):
    d = lambda n: shift_date(today, n)
    cs = "CS - Alice"
    clients = [c["name"] for c in db["clients"]]
    made = []

    def event(title, date, end=None, time="09:00", end_time="12:00", all_day=False):
        return server.action_create_calendar_event(db, {
            "actor": cs, "title": title, "date": date, "end_date": end or date,
            "time": time, "end_time": end_time, "all_day": all_day})

    def ticket(label, client, ttype, desc, priority="medium"):
        t = server.action_create(db, {
            "actor": cs, "client": client, "type": ttype, "priority": priority,
            "title": f"[TEST] {label}", "description": desc})
        return t

    def schedule(t, evs, engineer, techs):
        server.action_link_events(db, t, {
            "actor": cs, "calendar_event_ids": [e["id"] for e in evs],
            "engineer": engineer, "technicians": techs})

    # A. visit TODAY, Team 1  -> checklist can be tested right now
    t = ticket("Visit today (Team 1)", clients[0], "residential_servicing", "Routine servicing - test the checklist today.")
    schedule(t, [event("Test: servicing today", d(0))], "Engineer - Wardah", ["Technician - Ali", "Technician - Bala"])
    made.append((t["id"], t["title"], f"visit {d(0)} (today), Team 1"))

    # B. visit in 3 days, Team 2 -> checklist must be refused until that day
    t = ticket("Visit in 3 days (Team 2)", clients[1], "residential_troubleshooting", "Inverter alarm - future visit, gating test.", "high")
    schedule(t, [event("Test: troubleshooting +3d", d(3))], "Engineer - Faisal", ["Technician - Chong", "Technician - Devi"])
    made.append((t["id"], t["title"], f"visit {d(3)} (+3 days), Team 2"))

    # C. multi-day visit, tomorrow .. +3  -> three visit days, one checklist each
    t = ticket("3-day visit starting tomorrow", clients[2], "site_survey", "Multi-day survey - one checklist per day.")
    schedule(t, [event("Test: 3-day survey", d(1), d(3), all_day=True, time="", end_time="")],
             "Engineer - Wardah", ["Technician - Chong", "Technician - Devi"])
    made.append((t["id"], t["title"], f"visit {d(1)} to {d(3)}, Team 2"))

    # D. engineer-only (solo) visit in 2 days
    t = ticket("Engineer solo visit (+2 days)", clients[3], "ci_servicing", "Engineer goes alone - engineer fills the checklist.")
    schedule(t, [event("Test: solo visit +2d", d(2), time="10:00", end_time="13:00")], "Engineer - Faisal", [])
    made.append((t["id"], t["title"], f"visit {d(2)} (+2 days), engineer only"))

    # E. unscheduled for 9 days -> trips the 'unscheduled more than 7 days' / stale alerts
    t = ticket("Unscheduled for 9 days", clients[4], "ci_troubleshooting", "Nobody has booked this - should show on HOD/CS alerts.", "critical")
    old = iso_days_ago(9)
    t["created_at"] = t["updated_at"] = old
    for e in t["event_log"]:
        e["ts"] = old
    made.append((t["id"], t["title"], "created 9 days ago, never scheduled"))

    # F. fresh unscheduled ticket + free calendar events to practise linking
    t = ticket("Fresh ticket, link it yourself", clients[5 % len(clients)], "dere", "Unscheduled - pick one of the free events.")
    made.append((t["id"], t["title"], "unscheduled"))
    free = [event("Free slot +1d", d(1), time="14:00", end_time="16:00"),
            event("Free slot +5d", d(5), time="09:30", end_time="11:30"),
            event("Free slot +7d (all day)", d(7), all_day=True, time="", end_time="")]
    made.append(("EVT", "3 unlinked calendar events", f"{d(1)}, {d(5)}, {d(7)}"))
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default=SEED_PATH)
    ap.add_argument("--out", default=os.path.join(ROOT, "db.json"))
    ap.add_argument("--today", help="YYYY-MM-DD (default: today, Malaysia time)")
    ap.add_argument("--no-scenarios", action="store_true", help="only shift the seed, add nothing")
    args = ap.parse_args()

    today = args.today or server.today_str()
    with open(args.seed) as f:
        db = json.load(f)
    ref = db.pop("_seed_ref_date", None)
    if not ref:
        sys.exit("Seed file has no _seed_ref_date - cannot tell how far to shift.")
    delta = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(ref, "%Y-%m-%d")).days
    db = shift_value(db, delta)

    made = [] if args.no_scenarios else build_scenarios(db, today)

    if os.path.exists(args.out):
        shutil.copy2(args.out, os.path.join(os.path.dirname(os.path.abspath(args.out)), "db.before-reset.json"))
    tmp = args.out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, args.out)

    print(f"db.json rebuilt for {today}  (seed {ref} shifted by {delta:+d} days)")
    print(f"{len(db['tickets'])} tickets, {len(db['calendar_events'])} calendar events -> {args.out}")
    for tid, title, note in made:
        print(f"  {tid:9} {title}  [{note}]")
    print("Start the server now: python server.py")


if __name__ == "__main__":
    main()
