// Apps Script entry points. Bound to the "Internship List" spreadsheet.
// Run setup() once; after that, run() fires every 15 minutes on a trigger.

const CONFIG = {
  // Empty means the highest-numbered "PhiNN" tab, so a new season's tab is picked up automatically.
  SHEET_NAME: '',
  // Cheap Gmail pre-filter; Claude makes the real call on each new message that matches.
  SEARCH_TERMS: '{"thank you for applying" "thanks for applying" "received your application" ' +
    '"application received" "your application" "applying to" "applying for" "your candidacy" ' +
    '"move forward" "moving forward" "online assessment" "coding challenge" hackerrank codesignal ' +
    'interview "offer letter" "pleased to offer"}',
  LOOKBACK_DAYS: 3,
  MAX_THREADS: 100,
  TRIGGER_MINUTES: 15,
  ALERT_EVERY_HOURS: 24,
};

const DAY_MS = 24 * 60 * 60 * 1000;

function setup() {
  if (!getProp_('ANTHROPIC_API_KEY')) {
    throw new Error('Set the ANTHROPIC_API_KEY script property first (Project Settings > Script properties).');
  }
  ScriptApp.getProjectTriggers()
    .filter((t) => t.getHandlerFunction() === 'run')
    .forEach((t) => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('run').timeBased().everyMinutes(CONFIG.TRIGGER_MINUTES).create();
  // Only emails after install are picked up automatically; use backfill() for older ones.
  setProp_('START_TIME', String(Date.now()));
  Logger.log('Installed: run() every %s minutes, writing to "%s".', CONFIG.TRIGGER_MINUTES, getTrackerSheet_().getName());
}

function run() {
  processInbox_({ days: CONFIG.LOOKBACK_DAYS, respectStartTime: true, dryRun: false });
}

// Logs what would change over the last 14 days without touching the sheet.
function dryRun() {
  processInbox_({ days: 14, respectStartTime: false, dryRun: true });
}

// Applies the last N days of emails. Rows that already exist are skipped and
// statuses only move forward, so re-running is safe.
function backfill(days) {
  processInbox_({ days: days || 14, respectStartTime: false, dryRun: false });
}

function processInbox_(opts) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    processInboxLocked_(opts);
  } catch (err) {
    if (!opts.dryRun) alert_(err.message);
    throw err;
  } finally {
    lock.releaseLock();
  }
}

function processInboxLocked_(opts) {
  const sheet = getTrackerSheet_();
  const lastRow = sheet.getLastRow();
  const tracker = lastRow > 1
    ? sheet.getRange(2, 1, lastRow - 1, 3).getValues()
      .map((r, i) => ({ row: i + 2, applied: String(r[0]).trim(), date: r[1], status: String(r[2]).trim() }))
      .filter((r) => r.applied)
    : [];

  const now = Date.now();
  const startTime = opts.respectStartTime ? Number(getProp_('START_TIME') || 0) : 0;
  const floor = Math.max(now - opts.days * DAY_MS, startTime);
  const seen = JSON.parse(getProp_('SEEN_THREADS') || '{}');
  const me = myAddresses_();

  const query = `${CONFIG.SEARCH_TERMS} newer_than:${opts.days}d -from:me`;
  const threads = GmailApp.search(query, 0, CONFIG.MAX_THREADS);
  const newRows = [];
  let checked = 0;

  threadLoop:
  for (const thread of threads) {
    const id = thread.getId();
    const since = Math.max(floor, seen[id] || 0);
    const all = thread.getMessages();
    const fromMe = (m) => me.some((addr) => m.getFrom().toLowerCase().includes(addr));
    // Once you've replied, it's a conversation you're handling yourself;
    // reading it as status updates is where wrong rows come from.
    if (all.some(fromMe)) {
      seen[id] = Math.max(seen[id] || 0, all[all.length - 1].getDate().getTime());
      continue;
    }
    const messages = all.filter((m) => m.getDate().getTime() > since);

    for (const message of messages) {
      const sentAt = message.getDate().getTime();

      let result;
      try {
        result = classify_(message, tracker);
      } catch (err) {
        if (err.fatal) throw err;
        // Rate limits and outages: stop here and let the next run retry from this message.
        Logger.log('Stopping early on "%s": %s', message.getSubject(), err.message);
        break threadLoop;
      }
      checked++;
      applyResult_(result, message, sheet, tracker, newRows, opts.dryRun);
      seen[id] = Math.max(seen[id] || 0, sentAt);
    }
  }

  if (newRows.length && !opts.dryRun) {
    // Oldest first, so rows stay in date order.
    newRows.sort((a, b) => a[1] - b[1]);
    sheet.getRange(sheet.getLastRow() + 1, 1, newRows.length, 4).setValues(newRows);
  }
  if (!opts.dryRun) {
    // Threads untouched for longer than any lookback can't come back, so forget them.
    const keepAfter = now - (Math.max(opts.days, CONFIG.LOOKBACK_DAYS) + 1) * DAY_MS;
    Object.keys(seen).forEach((id) => { if (seen[id] < keepAfter) delete seen[id]; });
    setProp_('SEEN_THREADS', JSON.stringify(seen));
  }
  Logger.log('Checked %s new emails in "%s"; %s rows %s.',
    checked, sheet.getName(), newRows.length, opts.dryRun ? 'would be added' : 'added');
}

function applyResult_(result, message, sheet, tracker, newRows, dryRun) {
  const prefix = dryRun ? '[dry run] ' : '';
  if (result.type === 'other' || !result.company) return;

  if (result.type === 'confirmation') {
    const applied = formatApplied(result.company, result.role);
    const existing = tracker.map((r) => r.applied).concat(newRows.map((r) => r[0]));
    const datedRows = tracker.concat(newRows.map((r) => ({ applied: r[0], date: r[1] })));
    if (isDuplicate(result.company, result.role, existing) ||
        isRolelessDuplicate(result.company, result.role, message.getDate().getTime(), datedRows)) {
      Logger.log('%sAlready in sheet: %s', prefix, applied);
      return;
    }
    const d = message.getDate();
    newRows.push([
      applied,
      new Date(d.getFullYear(), d.getMonth(), d.getDate()),
      STATUS_FOR_TYPE.confirmation,
      result.role ? '' : 'Role not in email',
    ]);
    Logger.log('%sAdding: %s', prefix, applied);
    return;
  }

  const status = STATUS_FOR_TYPE[result.type];
  const target = tracker.find((r) => r.row === result.row);
  if (!target || !rowMatchesCompany(target.applied, result.company) ||
      !isUnambiguousRow(target, result.company, result.role, tracker)) {
    Logger.log('%sNo single row for %s email from %s (%s); left for you to update.',
      prefix, result.type, result.company, result.role || 'role not named');
    return;
  }
  if (!shouldUpdateStatus(target.status, status)) {
    Logger.log('%sKeeping "%s" on %s (email says %s).', prefix, target.status, target.applied, result.type);
    return;
  }
  if (!dryRun) sheet.getRange(target.row, 3).setValue(status);
  Logger.log('%s%s: %s -> %s', prefix, target.applied, target.status || '(blank)', status);
  target.status = status;
}

function classify_(message, tracker) {
  let result = callClaude_(message, []);
  if (needsRetry(result)) result = callClaude_(message, []);
  if (needsRowLookup(result)) result.row = callClaude_(message, tracker).row;
  return result;
}

function callClaude_(message, tracker) {
  const email = {
    from: message.getFrom(),
    subject: message.getSubject(),
    date: message.getDate().toISOString(),
    body: message.getPlainBody(),
  };
  const headers = { 'x-api-key': getProp_('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01' };
  // Only needed for keys that aren't scoped to a workspace.
  const workspaceId = getProp_('ANTHROPIC_WORKSPACE_ID');
  if (workspaceId) headers['anthropic-workspace-id'] = workspaceId;

  const res = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    contentType: 'application/json',
    headers: headers,
    payload: JSON.stringify(buildRequest(email, tracker)),
    muteHttpExceptions: true,
  });
  const status = res.getResponseCode();
  if (status === 200) return parseResponse(JSON.parse(res.getContentText()));

  let detail = res.getContentText().slice(0, 300);
  try { detail = JSON.parse(res.getContentText()).error.message; } catch (e) {}
  const err = new Error(`Anthropic API returned HTTP ${status}: ${detail}`);
  // 429 and 5xx clear up on their own; anything else (no credits, bad key) needs you.
  err.fatal = status !== 429 && status < 500;
  throw err;
}

// Emails you about a problem the script can't fix itself, at most once a day.
function alert_(problem) {
  const last = Number(getProp_('LAST_ALERT') || 0);
  if (Date.now() - last < CONFIG.ALERT_EVERY_HOURS * 60 * 60 * 1000) return;
  setProp_('LAST_ALERT', String(Date.now()));
  MailApp.sendEmail(
    Session.getEffectiveUser().getEmail(),
    'Application tracker stopped',
    `The application tracker couldn't process new emails:\n\n${problem}\n\n` +
      'It keeps retrying every 15 minutes and will catch up on missed emails from the last ' +
      `${CONFIG.LOOKBACK_DAYS} days once this is fixed. For anything older, run backfill() ` +
      'from the Apps Script editor.\n\n' + SpreadsheetApp.getActiveSpreadsheet().getUrl()
  );
}

function getTrackerSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (CONFIG.SHEET_NAME) {
    const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
    if (!sheet) throw new Error(`No tab named "${CONFIG.SHEET_NAME}".`);
    return sheet;
  }
  const seasons = ss.getSheets()
    .map((s) => ({ sheet: s, match: /^Phi(\d+)$/.exec(s.getName()) }))
    .filter((s) => s.match)
    .sort((a, b) => Number(b.match[1]) - Number(a.match[1]));
  if (!seasons.length) throw new Error('No tab named like "Phi27" found.');
  return seasons[0].sheet;
}

function myAddresses_() {
  return [Session.getEffectiveUser().getEmail()].concat(GmailApp.getAliases())
    .filter(Boolean)
    .map((a) => a.toLowerCase());
}

function getProp_(key) {
  return PropertiesService.getScriptProperties().getProperty(key);
}

function setProp_(key, value) {
  PropertiesService.getScriptProperties().setProperty(key, value);
}
