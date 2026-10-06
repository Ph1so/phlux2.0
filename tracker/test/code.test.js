// Runs Code.js against fake Gmail / Sheets / Properties services, with canned
// Claude responses, to check the glue that only runs inside Apps Script.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SOURCE = ['extract.js', 'Code.js']
  .map((f) => fs.readFileSync(path.join(__dirname, '..', f), 'utf8'))
  .join('\n');
const NOW = Date.now();
const HOUR = 60 * 60 * 1000;

function fakeSheet(name, rows) {
  // rows: [[applied, date, status, notes]], header added automatically.
  const data = [['Applied', 'Date', 'Status', 'Notes'], ...rows];
  return {
    data,
    getName: () => name,
    getLastRow: () => data.length,
    getRange(row, col, numRows = 1, numCols = 1) {
      return {
        getValues: () => data.slice(row - 1, row - 1 + numRows).map((r) => r.slice(col - 1, col - 1 + numCols)),
        setValues(values) {
          values.forEach((v, i) => {
            data[row - 1 + i] = data[row - 1 + i] || ['', '', '', ''];
            v.forEach((cell, j) => { data[row - 1 + i][col - 1 + j] = cell; });
          });
        },
        setValue(value) { data[row - 1][col - 1] = value; },
      };
    },
  };
}

function fakeMessage(subject, hoursAgo, from = 'no-reply@ats.example') {
  return {
    subject,
    getSubject: () => subject,
    getFrom: () => from,
    getDate: () => new Date(NOW - hoursAgo * HOUR),
    getPlainBody: () => `body of ${subject}`,
  };
}

// classifications: subject -> parsed result, or a number for an HTTP error status.
function makeEnv({ sheets, threads, classifications, props = {} }) {
  const env = { apiCalls: [], sawRows: [], mails: [], props: { ANTHROPIC_API_KEY: 'test-key', ...props } };
  const context = {
    console,
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock() {} }) },
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ({
        getSheets: () => sheets,
        getSheetByName: (n) => sheets.find((s) => s.getName() === n) || null,
        getUrl: () => 'https://sheet',
      }),
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (k) => (k in env.props ? env.props[k] : null),
        setProperty: (k, v) => { env.props[k] = v; },
      }),
    },
    GmailApp: {
      search: () => threads,
      getAliases: () => ['phi.alias@example.com'],
    },
    Session: { getEffectiveUser: () => ({ getEmail: () => 'phi@example.com' }) },
    UrlFetchApp: {
      fetch(url, options) {
        const content = JSON.parse(options.payload).messages[0].content;
        const subject = /Subject: (.*)/.exec(content)[1];
        env.apiCalls.push(subject);
        env.sawRows.push(!content.includes('<tracker_rows>\n(empty)'));
        // An array gives a different response per call, in order.
        const c = Array.isArray(classifications[subject]) ? classifications[subject].shift() : classifications[subject];
        if (typeof c === 'number') {
          return {
            getResponseCode: () => c,
            getContentText: () => JSON.stringify({ error: { message: `error ${c}` } }),
          };
        }
        const body = { stop_reason: 'end_turn', content: [{ type: 'text', text: JSON.stringify({ row: 0, role: '', ...c }) }] };
        return { getResponseCode: () => 200, getContentText: () => JSON.stringify(body) };
      },
    },
    MailApp: { sendEmail: (to, subject, body) => env.mails.push({ to, subject, body }) },
    Logger: { log() {} },
    ScriptApp: {},
  };
  vm.createContext(context);
  vm.runInContext(SOURCE, context);
  env.run = () => vm.runInContext('run()', context);
  env.dryRun = () => vm.runInContext('dryRun()', context);
  return env;
}

function thread(id, ...messages) {
  return { getId: () => id, getMessages: () => messages };
}

test('adds new confirmations, skips duplicates, and updates statuses', () => {
  const sheet = fakeSheet('Phi27', [
    ['Waymo - 2027 Summer Intern, BS/MS, Scenes', new Date(), 'Applied', ''],
    ['Citadel - Software Engineer Intern 2027', new Date(), 'Applied', ''],
    ['SpaceX - Summer 2027 Software Engineering Internship/Co-op', new Date(), 'Offer (Internship)', 'Declined'],
  ]);
  const env = makeEnv({
    sheets: [sheet],
    threads: [
      thread('t1', fakeMessage('Thanks for applying to Zipline', 5)),
      thread('t2', fakeMessage('Thank You for Applying to Waymo!', 4)),
      thread('t3', fakeMessage('Your Citadel Application', 3)),
      thread('t4', fakeMessage('SpaceX update', 2)),
      thread('t5', fakeMessage('Thank you for applying to Lab37', 1)),
    ],
    classifications: {
      'Thanks for applying to Zipline': { type: 'confirmation', company: 'Zipline', role: 'Maps Intern (Summer 2027)' },
      'Thank You for Applying to Waymo!': { type: 'confirmation', company: 'Waymo', role: '2027 Summer Intern, BS/MS, Scenes' },
      'Your Citadel Application': { type: 'rejection', company: 'Citadel', role: 'Software Engineering', row: 3 },
      'SpaceX update': { type: 'rejection', company: 'SpaceX', row: 4 },
      'Thank you for applying to Lab37': { type: 'confirmation', company: 'Lab37', role: '' },
    },
  });
  env.run();

  assert.strictEqual(sheet.data.length, 6);
  assert.deepStrictEqual(sheet.data[4].slice(0, 4).map(String).filter((_, i) => i !== 1),
    ['Zipline - Maps Intern (Summer 2027)', 'Applied', '']);
  // Date from the vm sandbox, so instanceof doesn't work across realms.
  assert.strictEqual(Object.prototype.toString.call(sheet.data[4][1]), '[object Date]');
  assert.deepStrictEqual([sheet.data[5][0], sheet.data[5][3]], ['Lab37', 'Role not in email']);
  assert.strictEqual(sheet.data[2][2], 'Rejected');
  assert.strictEqual(sheet.data[3][2], 'Offer (Internship)', 'an offer is never overwritten');
});

test('a second run makes no API calls for messages it already handled', () => {
  const env = makeEnv({
    sheets: [fakeSheet('Phi27', [])],
    threads: [thread('t1', fakeMessage('Thanks for applying to Zipline', 5))],
    classifications: { 'Thanks for applying to Zipline': { type: 'confirmation', company: 'Zipline', role: 'Maps Intern' } },
  });
  env.run();
  env.run();
  assert.deepStrictEqual(env.apiCalls, ['Thanks for applying to Zipline']);
});

test('a reply in an already-handled thread is still classified', () => {
  const confirmation = fakeMessage('Thank you for applying to Jane Street', 48);
  const threads = [thread('t1', confirmation)];
  const sheet = fakeSheet('Phi27', [['Jane Street - Software Engineer Intern 2027', new Date(), 'Applied', '']]);
  const env = makeEnv({
    sheets: [sheet],
    threads,
    classifications: {
      'Thank you for applying to Jane Street': { type: 'confirmation', company: 'Jane Street', role: 'Software Engineer Intern 2027' },
      'Re: Thank you for applying to Jane Street': { type: 'rejection', company: 'Jane Street', row: 2 },
    },
  });
  env.run();
  threads[0] = thread('t1', confirmation, fakeMessage('Re: Thank you for applying to Jane Street', 1));
  env.run();
  // The rejection takes two calls: classify, then pick the row.
  assert.deepStrictEqual(env.apiCalls, ['Thank you for applying to Jane Street',
    'Re: Thank you for applying to Jane Street', 'Re: Thank you for applying to Jane Street']);
  assert.strictEqual(sheet.data[1][2], 'Rejected');
});

test('skips messages sent by the user without calling the API', () => {
  const env = makeEnv({
    sheets: [fakeSheet('Phi27', [])],
    threads: [thread('t1', fakeMessage('Re: interview', 1, 'Phi <phi.alias@example.com>'))],
    classifications: {},
  });
  env.run();
  assert.deepStrictEqual(env.apiCalls, []);
});

test('ignores emails from before setup', () => {
  const env = makeEnv({
    sheets: [fakeSheet('Phi27', [])],
    threads: [thread('t1', fakeMessage('Old confirmation', 10))],
    classifications: {},
    props: { START_TIME: String(NOW - 2 * HOUR) },
  });
  env.run();
  assert.deepStrictEqual(env.apiCalls, []);
});

test('writes to the newest PhiNN tab', () => {
  const phi27 = fakeSheet('Phi27', []);
  const phi28 = fakeSheet('Phi28', []);
  const env = makeEnv({
    sheets: [fakeSheet('2026-2027', []), phi27, phi28, fakeSheet('Phi9', [])],
    threads: [thread('t1', fakeMessage('Thanks for applying to Zipline', 1))],
    classifications: { 'Thanks for applying to Zipline': { type: 'confirmation', company: 'Zipline', role: 'Maps Intern' } },
  });
  env.run();
  assert.strictEqual(phi28.data.length, 2);
  assert.strictEqual(phi27.data.length, 1);
});

test('emails once a day when the API needs attention, and retries the message later', () => {
  const env = makeEnv({
    sheets: [fakeSheet('Phi27', [])],
    threads: [thread('t1', fakeMessage('Thanks for applying to Zipline', 1))],
    classifications: { 'Thanks for applying to Zipline': 400 },
  });
  assert.throws(() => env.run(), /HTTP 400: error 400/);
  assert.throws(() => env.run(), /HTTP 400/);
  assert.strictEqual(env.mails.length, 1);
  assert.strictEqual(env.mails[0].to, 'phi@example.com');
  assert.match(env.mails[0].body, /HTTP 400: error 400/);
  assert.strictEqual(env.apiCalls.length, 2, 'the failed message is retried on the next run');
});

test('an outage stops the run quietly and the message is retried', () => {
  const classifications = { 'Thanks for applying to Zipline': 529 };
  const sheet = fakeSheet('Phi27', []);
  const env = makeEnv({
    sheets: [sheet],
    threads: [thread('t1', fakeMessage('Thanks for applying to Zipline', 1))],
    classifications,
  });
  env.run();
  assert.strictEqual(env.mails.length, 0);
  classifications['Thanks for applying to Zipline'] = { type: 'confirmation', company: 'Zipline', role: 'Maps Intern' };
  env.run();
  assert.strictEqual(sheet.data.length, 2);
});

test('dryRun changes nothing', () => {
  const sheet = fakeSheet('Phi27', [['Citadel - Software Engineer Intern 2027', new Date(), 'Applied', '']]);
  const env = makeEnv({
    sheets: [sheet],
    threads: [
      thread('t1', fakeMessage('Thanks for applying to Zipline', 1)),
      thread('t2', fakeMessage('Your Citadel Application', 1)),
    ],
    classifications: {
      'Thanks for applying to Zipline': { type: 'confirmation', company: 'Zipline', role: 'Maps Intern' },
      'Your Citadel Application': { type: 'rejection', company: 'Citadel', row: 2 },
    },
  });
  env.dryRun();
  assert.strictEqual(sheet.data.length, 2);
  assert.strictEqual(sheet.data[1][2], 'Applied');
  assert.strictEqual(env.props.SEEN_THREADS, undefined);
});

test('asks again when the model returns a blank company', () => {
  const sheet = fakeSheet('Phi27', []);
  const env = makeEnv({
    sheets: [sheet],
    threads: [thread('t1', fakeMessage('Successfully submitted application', 1))],
    classifications: {
      'Successfully submitted application': [
        { type: 'confirmation', company: '', role: '' },
        { type: 'confirmation', company: 'Qualcomm', role: 'Automotive Engineering Internship' },
      ],
    },
  });
  env.run();
  assert.strictEqual(env.apiCalls.length, 2);
  assert.strictEqual(sheet.data[1][0], 'Qualcomm - Automotive Engineering Internship');
});

test('skips whole threads you have replied to', () => {
  const sheet = fakeSheet('Phi27', [['SpaceX - Fall 2026 Software Engineering Internship/Co-op', new Date(), 'Applied', '']]);
  const env = makeEnv({
    sheets: [sheet],
    threads: [thread('t1',
      fakeMessage('SpaceX Interview Follow-Up Call', 3, 'Christina <c@spacex.com>'),
      fakeMessage('Re: SpaceX Interview Follow-Up Call', 2, 'Phi <phi@example.com>'),
      fakeMessage('RE: SpaceX Interview Follow-Up Call', 1, 'Christina <c@spacex.com>'))],
    classifications: {},
  });
  env.run();
  assert.deepStrictEqual(env.apiCalls, []);
  assert.strictEqual(sheet.data[1][2], 'Applied');
});

test('does not add a role-less confirmation already logged by hand', () => {
  const sheet = fakeSheet('Phi27', [['Lab37 - Robotics Software Engineer Intern', new Date(NOW), 'Applied', '']]);
  const env = makeEnv({
    sheets: [sheet],
    threads: [thread('t1', fakeMessage('Thank you for applying to Lab37!', 2))],
    classifications: { 'Thank you for applying to Lab37!': { type: 'confirmation', company: 'Lab37', role: '' } },
  });
  env.run();
  assert.strictEqual(sheet.data.length, 2);
});

test('leaves the status alone when the email could match several rows', () => {
  const sheet = fakeSheet('Phi27', [
    ['SpaceX - Fall 2026 Software Engineering Internship/Co-op', new Date(), 'Applied', ''],
    ['SpaceX - Summer 2027 Software Engineering Internship/Co-op', new Date(), 'Applied', ''],
  ]);
  const env = makeEnv({
    sheets: [sheet],
    threads: [thread('t1', fakeMessage('SpaceX Interview - Availability Request', 1))],
    classifications: { 'SpaceX Interview - Availability Request': { type: 'interview', company: 'SpaceX', role: 'Satellite Engineering Internship', row: 2 } },
  });
  env.run();
  assert.strictEqual(sheet.data[1][2], 'Applied');
  assert.strictEqual(sheet.data[2][2], 'Applied');
});

test('classifies without the tracker rows and looks the row up only for status emails', () => {
  const sheet = fakeSheet('Phi27', [['Citadel - Software Engineer Intern 2027', new Date(), 'Applied', '']]);
  const env = makeEnv({
    sheets: [sheet],
    threads: [
      thread('t1', fakeMessage('Thanks for applying to Zipline', 2)),
      thread('t2', fakeMessage('Your Citadel Application', 1)),
    ],
    classifications: {
      'Thanks for applying to Zipline': { type: 'confirmation', company: 'Zipline', role: 'Maps Intern' },
      'Your Citadel Application': { type: 'rejection', company: 'Citadel', row: 2 },
    },
  });
  env.run();
  assert.deepStrictEqual(env.apiCalls, ['Thanks for applying to Zipline', 'Your Citadel Application', 'Your Citadel Application']);
  assert.deepStrictEqual(env.sawRows, [false, false, true]);
  assert.strictEqual(sheet.data[1][2], 'Rejected');
});
