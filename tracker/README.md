# Application tracker

Watches Gmail and keeps the newest `PhiNN` tab of the Internship List
spreadsheet up to date:

- **Application confirmations** ("thanks for applying") add a row:
  `Company - Role` | email date | `Applied` | `Role not in email` when the
  email doesn't name one.
- **Rejections, online assessments, interview requests, and offers** update
  the Status of the matching row to `Rejected`, `OA`, `Interview (Round 1)`,
  or `Offer (Internship)`. Statuses only move forward: nothing overwrites an
  offer, and an OA reminder never overwrites an interview. If the email
  could match several rows (e.g. "your Waymo application" with five Waymo
  rows) or none, the row is left for you.

Runs as a Google Apps Script bound to the spreadsheet, every 15 minutes.
Each new matching email goes to Claude Haiku 4.5 with the list of rows in the
tab; it classifies the email and pulls out the company, role, and row.
Cost is about $0.002–0.003 per email.

If the Anthropic API stops accepting requests (no credits, revoked key), the
script emails you, at most once a day, and catches up on the last 3 days of
email once it's fixed.

## Install

1. In the spreadsheet: **Extensions → Apps Script**.
2. Create two script files named `TrackerExtract` and `Tracker` and paste in
   `extract.js` and `Code.js`. (Any names work; these avoid clashing with an
   existing `Code.gs`, such as the date auto-fill script already in the
   Internship List project.)
3. **Project Settings**: check "Show appsscript.json", then replace its
   contents with `appsscript.json`.
4. **Project Settings → Script properties**: add `ANTHROPIC_API_KEY`. If the
   key isn't scoped to a workspace, also add `ANTHROPIC_WORKSPACE_ID`.
5. Run `dryRun` from the editor and approve the permissions. The log shows
   what would change over the last 14 days without touching the sheet.
6. Run `setup` once. This installs the 15-minute trigger. Only emails that
   arrive after this point are picked up; run `backfill` to also apply
   older ones (safe to re-run: existing rows are skipped).

A new season needs no changes as long as its tab is named like `Phi28`. To
pin a specific tab instead, set `CONFIG.SHEET_NAME` in `Code.js`.

## Tests

```bash
npm test       # unit tests + Code.js against fake Gmail/Sheets, no network
npm run eval   # real API over test/fixtures; reads ANTHROPIC_API_KEY from the repo .env
```

The eval grades the extractor against rows already in the sheet. The
fixtures are real emails and are gitignored, so don't commit them.
