# Developer guide: test data and shared-repo rules

For anyone working on this prototype (Steve, colleagues). Read this once before your first test run.

## 1. Why the test data needs resetting

The demo database is a fixed snapshot. Checklists are date-gated: they can only be started, edited or
submitted on the exact visit day. After a few days every visit in the snapshot is in the past, so
nothing can be tested. `tools/reset_demo.py` rebuilds `db.json` so the data is "fresh" again, relative to today.

## 2. How to reset

From the project folder:

```
python3 tools/reset_demo.py          # Windows: python tools/reset_demo.py
```

Then start the server (`python server.py`) and log in as usual. Needs Python 3.8+, nothing else.

| Option | What it does |
| --- | --- |
| `--today 2026-12-01` | Pretend today is another date (dates and scenarios are built around it). |
| `--no-scenarios` | Only shift the old data, do not add test tickets. |
| `--out some/path.json` | Write somewhere else instead of `db.json` (the server will not see it). |
| `--seed some/seed.json` | Use another seed file. It must contain `_seed_ref_date`. |

"Today" means Malaysia time (UTC+8), the same as the server.

## 3. What the script does

1. Loads `tools/seed/db.seed.json` (a frozen copy of the data as it stood on 26 Oct 2026, key `_seed_ref_date`).
2. Moves every date and timestamp by the same number of days (today minus the seed date), so history keeps its shape.
3. Adds test scenarios by calling the real functions in `server.py`, so they obey the real rules.
4. Copies your old `db.json` to `db.before-reset.json` (only the latest copy is kept), then writes the new `db.json`.

Scenarios added (ticket numbers continue from the seed, so they are usually TCK-0110 onwards):

| Scenario | What to test with it |
| --- | --- |
| Visit **today**, Team 1 | Start, fill and submit a checklist; Team 2 technicians must be refused. |
| Visit in **3 days**, Team 2 | The checklist must be refused until that day. |
| **3-day** visit from tomorrow | One visit day and one checklist per date. |
| Engineer **solo** visit in 2 days | The engineer fills the checklist themselves. |
| **Unscheduled for 9 days** | Dashboard "unscheduled more than 7 days" and inactivity alerts. |
| **Fresh unscheduled** ticket + 3 free calendar events (+1, +5, +7 days) | Practise linking events to a ticket. |

## 4. Rules for sharing the repo

- `db.json`, `backups/`, `om_actions.log` and `om_email_outbox.log` are git-ignored. **Never commit them.**
  Each person has their own local `db.json`; run the reset to get one.
- A reset wipes your test data. If you want to keep a particular state, copy `db.json` aside first.
- Do not edit `tools/seed/db.seed.json` by hand. To change the baseline, edit `tools/reset_demo.py`
  (`build_scenarios`), or ask before replacing the seed: everyone's reset results change with it.
- Role rules exist in two places: `ACTION_ROLES` in `server.py` and in `static/shared.js`. Change both
  together, in the same commit.
- Test date-gated features (checklists, visit days) right after a reset. Later in the day or week the
  scenarios drift into the past.

## 5. Troubleshooting

| Problem | Fix |
| --- | --- |
| `db.json not found` when starting the server | Run the reset first. |
| `ModuleNotFoundError: server` | Run the script from the project folder, as in section 2. |
| Pages show old data after a reset | Hard refresh (Ctrl+F5); clear the `om_session` login if the account list changed. |
| A visit you expected "today" shows as past | The reset ran on an earlier day. Run it again. |
