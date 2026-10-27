# ERS O&M Ticketing Portal (demo for handover)

A working prototype of the ticket flow, role rules and pages. It is for the digital team to study and rebuild properly. It is not a production system.

## Start here

Read the three PDFs in the `Need to review this first` folder, in this order:

1. **ERS O&M - Read Me First.pdf**: what the system is, how to run it, what is simulated, what is not built, decisions still open.
2. **ERS O&M - Data Dictionary.pdf**: every field in `db.json`.
3. **ERS O&M - API Reference.pdf**: every endpoint, the role rules and the order of checks.

This README is only a short pointer. If anything here differs from the PDFs, the PDFs are right.

## Run it

Needs Python 3.8 or newer. No other packages.

```
cd om-ticket-demo
python3 server.py
```

Open http://localhost:8000/ and pick an account. There is no password in this demo (login is not built yet).

## What is in this folder

| Item | What it is |
| --- | --- |
| `server.py` | The whole backend (Python standard library only). |
| `db.json` | All demo data (tickets, clients, calendar events, accounts, settings). |
| `static/` | All pages (HTML, CSS, JS), icons, Knowledge Base images, `manifest.json` and `sw.js` for the phone app. |
| `Need to review this first` | The three handover PDFs. |

The server creates a `backups/` folder by itself (one copy of `db.json` per day, newest 14 kept) and writes two log files. These are not part of the handover.

## Not built yet (short list)

Real login, real email and push notifications, real photo and file storage, a real database, and four of the six planned report formats. The Read Me First PDF has the full list.
