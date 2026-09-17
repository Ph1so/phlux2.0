# Company lists

A company list is a JSON file naming a subset of the companies in
`companies.csv`. `companies.csv` stays the single source of truth for *how* to
scrape a company — its URL and action string. A list only says *which*
companies to visit, so one scraper can serve people who care about different
companies.

## Using a list

Point `COMPANY_LIST` in `config.json` at the file:

```json
{ "COMPANY_LIST": "robotics" }
```

The value may be a bare stem (`robotics`), a file name (`robotics.json`), or a
path. Leave it empty, `null`, or omit it entirely to scrape every company in
`companies.csv` — the original behaviour.

Names are matched against `companies.csv` case-insensitively, and the scrape
order follows the CSV, not the list. A name with no matching CSV row is logged
and skipped, so renaming a company in the CSV degrades a stale list instead of
breaking the run.

## Building a list

```bash
python -m phlux.picker
```

No virtualenv needed — the picker only reads `companies.csv`, `icons.json` and
`industries.csv`, so it deliberately avoids importing the scraping stack and
runs on a bare Python 3. (`main.py` still needs the venv.)

This serves a card UI on `127.0.0.1:8777` and opens it. Swipe through every
company with `←` (skip) and `→` (keep) — or drag the card — then save. The next
four companies stay visible above the live card so you can read ahead while
clicking quickly, and `U` undoes the last call. "Start from" pre-answers *keep*
for everything already in an existing list, which is the quick way to amend one.

The review screen that follows shows two columns — left out on the left, in the
list on the right. Drag a company from one to the other, or use the arrow on its
row, to fix anything you mis-swiped before saving. The filter box narrows both
columns, which is how you find one company among the couple of hundred you left
out.

Saving writes the file here and, if the box is ticked, sets `COMPANY_LIST` in
`config.json` for you.

## Format

```json
{
  "name": "Robotics",
  "description": "Hardware and robotics companies only",
  "created": "2026-09-17",
  "companies": ["Nvidia", "Tesla", "Figure"]
}
```

A bare array of names is also accepted. Commit these files — the GitHub Actions
scrape reads `config.json` from the repo, so the list it points at has to be
there too.
