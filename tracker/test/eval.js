// Runs the real extractor over the email fixtures and grades it against the
// rows already in the sheet. Needs ANTHROPIC_API_KEY (read from the repo .env).
// Usage: npm run eval
const fs = require('node:fs');
const path = require('node:path');
const {
  buildRequest, parseResponse, needsRetry, needsRowLookup, normalizeKey, formatApplied, isDuplicate, isRolelessDuplicate, isUnambiguousRow, rowMatchesCompany,
} = require('../extract.js');

// Haiku 4.5, $ per token.
const INPUT_PRICE = 1 / 1e6;
const OUTPUT_PRICE = 5 / 1e6;

async function callClaude(email, tracker) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
      // Only needed for keys that aren't scoped to a workspace.
      ...(process.env.ANTHROPIC_WORKSPACE_ID && { 'anthropic-workspace-id': process.env.ANTHROPIC_WORKSPACE_ID }),
    },
    body: JSON.stringify(buildRequest(email, tracker)),
  });
  const json = await res.json();
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}: ${json.error ? json.error.message : JSON.stringify(json).slice(0, 300)}`);
    err.status = res.status;
    throw err;
  }
  return json;
}

async function main() {
  // The repo's gitignored .env, if present.
  try {
    process.loadEnvFile(path.join(__dirname, '..', '..', '.env'));
  } catch {}
  // `KEY = "value"` (spaces around =) keeps the quotes; strip them.
  for (const k of ['ANTHROPIC_API_KEY', 'ANTHROPIC_WORKSPACE_ID']) {
    if (process.env[k]) process.env[k] = process.env[k].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  if (!process.env.ANTHROPIC_API_KEY) {
    console.error('Add ANTHROPIC_API_KEY to the repo .env (or export it) first.');
    process.exit(1);
  }
  const fixturesDir = path.join(__dirname, 'fixtures');
  const tracker = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'sheet.json'), 'utf8'));
  const sheetCells = tracker.map((r) => r.applied);
  const emailsDir = path.join(fixturesDir, 'emails');
  const fixtures = fs.readdirSync(emailsDir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(fs.readFileSync(path.join(emailsDir, f), 'utf8')));

  const t = { type: 0, company: 0, role: 0, roleNamed: 0, positives: 0, deduped: 0, withRow: 0, rows: 0, statusEmails: 0 };
  let cost = 0;
  let retries = 0;
  const failures = [];

  for (const fx of fixtures) {
    let response, got;
    try {
      // Same steps as classify_ in Code.js.
      response = await callClaude(fx, []);
      got = parseResponse(response);
      if (needsRetry(got)) {
        cost += response.usage.input_tokens * INPUT_PRICE + response.usage.output_tokens * OUTPUT_PRICE;
        retries++;
        response = await callClaude(fx, []);
        got = parseResponse(response);
      }
      if (needsRowLookup(got)) {
        cost += response.usage.input_tokens * INPUT_PRICE + response.usage.output_tokens * OUTPUT_PRICE;
        response = await callClaude(fx, tracker);
        got.row = parseResponse(response).row;
      }
    } catch (err) {
      // A bad key or request shape fails every email the same way; stop at the first one.
      if (err.status >= 400 && err.status < 500 && err.status !== 429) {
        console.error(err.message);
        process.exit(1);
      }
      failures.push(`ERROR ${fx.subject}: ${err.message}`);
      continue;
    }
    cost += response.usage.input_tokens * INPUT_PRICE + response.usage.output_tokens * OUTPUT_PRICE;
    const want = fx.expected;
    const label = `${fx.subject} (${fx.id})`;

    if (got.type === want.type) t.type++;
    else failures.push(`TYPE ${label}: expected ${want.type}, got ${got.type}`);

    if (want.type === 'confirmation') {
      t.positives++;
      if (normalizeKey(got.company) === normalizeKey(want.company)) t.company++;
      else failures.push(`COMPANY ${label}: expected "${want.company}", got "${got.company}"`);
      if (normalizeKey(got.role) === normalizeKey(want.role)) t.role++;
      else failures.push(`ROLE ${label}:\n    expected "${want.role}"\n    got      "${got.role}"`);
      if (got.role) t.roleNamed++;
      // Would the script have skipped this email because the row already exists?
      if (fx.sheet_row) {
        t.withRow++;
        if (isDuplicate(got.company, got.role, sheetCells) ||
            isRolelessDuplicate(got.company, got.role, new Date(fx.date).getTime(), tracker)) t.deduped++;
        else failures.push(`DUPLICATE ${label}: would add "${formatApplied(got.company, got.role)}" next to "${fx.sheet_row}"`);
      }
    } else if (want.type !== 'other') {
      // Status emails: did it pick the right row (or correctly decline to pick one)?
      t.statusEmails++;
      const target = tracker.find((r) => r.row === got.row);
      const picked = target && rowMatchesCompany(target.applied, got.company) &&
        isUnambiguousRow(target, got.company, got.role, tracker) ? target.applied : '';
      if (picked === want.row_text) t.rows++;
      else failures.push(`ROW ${label}: expected "${want.row_text || 'none'}", got "${picked || 'none'}" (model row ${got.row})`);
    }
  }

  console.log(failures.join('\n') || 'No mismatches.');
  console.log('');
  console.log(`Type:           ${t.type}/${fixtures.length}`);
  console.log(`Company:        ${t.company}/${t.positives} confirmations`);
  console.log(`Role:           ${t.role}/${t.positives} confirmations (${t.roleNamed} had a role extracted)`);
  console.log(`Deduped:        ${t.deduped}/${t.withRow} confirmations whose row already exists`);
  console.log(`Status row:     ${t.rows}/${t.statusEmails} rejection/OA/interview emails`);
  console.log(`Retries:        ${retries}`);
  console.log(`Cost:           $${cost.toFixed(4)} total, $${(cost / fixtures.length).toFixed(5)} per email`);
}

main();
