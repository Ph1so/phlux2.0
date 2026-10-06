const test = require('node:test');
const assert = require('node:assert');
const {
  MAX_BODY_CHARS,
  buildRequest,
  parseResponse,
  formatApplied,
  isDuplicate,
  rowMatchesCompany,
  isRolelessDuplicate,
  isUnambiguousRow,
  shouldUpdateStatus,
} = require('../extract.js');

const email = {
  from: 'no-reply@us.greenhouse-mail.io',
  subject: 'Thank You for Applying to Waymo!',
  date: '2026-09-14T19:38:06Z',
  body: 'Hi Phi, Thank you for applying to our 2027 Summer Intern, BS/MS, Software Engineer position.',
};

const tracker = [
  { row: 2, applied: 'Waymo - 2027 Summer Intern, BS/MS, Scenes' },
  { row: 3, applied: 'Bosch - ADAS Software Engineering Intern' },
];

function apiResponse(obj, stopReason = 'end_turn') {
  return { stop_reason: stopReason, content: [{ type: 'text', text: JSON.stringify(obj) }] };
}

test('buildRequest asks for structured output and includes the tracker rows and email', () => {
  const req = buildRequest(email, tracker);
  assert.strictEqual(req.model, 'claude-haiku-4-5');
  assert.strictEqual(req.output_config.format.type, 'json_schema');
  const content = req.messages[0].content;
  assert.match(content, /2\. Waymo - 2027 Summer Intern, BS\/MS, Scenes/);
  assert.match(content, /From: no-reply@us\.greenhouse-mail\.io/);
  assert.match(content, /Subject: Thank You for Applying to Waymo!/);
  assert.match(content, /BS\/MS, Software Engineer position/);
});

test('buildRequest caps very long bodies', () => {
  const req = buildRequest({ ...email, body: 'x'.repeat(MAX_BODY_CHARS * 3) }, []);
  assert.ok(req.messages[0].content.length < MAX_BODY_CHARS + 500);
  assert.match(req.messages[0].content, /\[truncated\]\n<\/email>$/);
});

test('parseResponse returns trimmed fields', () => {
  const result = parseResponse(apiResponse({ type: 'rejection', company: ' Waymo ', role: 'Intern ', row: 2 }));
  assert.deepStrictEqual(result, { type: 'rejection', company: 'Waymo', role: 'Intern', row: 2 });
});

test('parseResponse rejects refusals, truncation, and missing text', () => {
  assert.throws(() => parseResponse(apiResponse({}, 'refusal')), /declined/);
  assert.throws(() => parseResponse(apiResponse({}, 'max_tokens')), /max_tokens/);
  assert.throws(() => parseResponse({ stop_reason: 'end_turn', content: [] }), /no text block/);
});

test('formatApplied matches the sheet convention', () => {
  assert.strictEqual(formatApplied('Zipline', 'Maps Intern (Summer 2027)'), 'Zipline - Maps Intern (Summer 2027)');
  assert.strictEqual(formatApplied('Hudson River Trading', ''), 'Hudson River Trading');
});

test('isDuplicate ignores spacing, punctuation, and case', () => {
  const sheet = [
    'Johnson&Johnson - Robotics Controls & Autonomy Intern - Robotics R&D',
    'Symbotic - Intern- Bot Controls',
    'General Motors - 2027 Summer Intern – Software Engineer, AV/AI Platform',
  ];
  assert.ok(isDuplicate('Johnson & Johnson', 'Robotics Controls & Autonomy Intern - Robotics R&D', sheet));
  assert.ok(isDuplicate('Symbotic', 'Intern - Bot Controls', sheet));
  assert.ok(isDuplicate('General Motors', '2027 Summer Intern - Software Engineer, AV/AI Platform', sheet));
});

test('isDuplicate tolerates company name variants', () => {
  const sheet = [
    'Niantic Spatial - Software Engineering Intern (Summer 2027)',
    'Bosch - ADAS Software Engineering Intern',
    'NVIDIA 2027 Internships: Autonomous Vehicles and Robotics',
  ];
  assert.ok(isDuplicate('Niantic', 'Software Engineering Intern (Summer 2027)', sheet));
  assert.ok(isDuplicate('Robert Bosch', 'ADAS Software Engineering Intern', sheet));
  assert.ok(isDuplicate('NVIDIA', 'NVIDIA 2027 Internships: Autonomous Vehicles and Robotics', sheet));
  assert.ok(!isDuplicate('Zoox', 'ADAS Software Engineering Intern', sheet));
});

test('isDuplicate keeps different roles at the same company apart', () => {
  const sheet = ['Waymo - 2027 Summer Intern, BS/MS, Scenes'];
  assert.ok(!isDuplicate('Waymo', '2027 Summer Intern, BS/MS, Software Engineer', sheet));
  assert.ok(!isDuplicate('Waymo', '', sheet));
});

test('rowMatchesCompany accepts name variants and rejects other companies', () => {
  assert.ok(rowMatchesCompany('Bosch - ADAS Software Engineering Intern', 'Robert Bosch LLC'));
  assert.ok(rowMatchesCompany('NVIDIA 2027 Internships: Autonomous Vehicles and Robotics', 'NVIDIA'));
  assert.ok(rowMatchesCompany('Johnson&Johnson - Robotics Controls & Autonomy Intern', 'Johnson & Johnson'));
  assert.ok(!rowMatchesCompany('Waymo - 2027 Summer Intern, BS/MS, Scenes', 'Zoox'));
  assert.ok(!rowMatchesCompany('Waymo - Intern', ''));
});

test('statuses only move forward', () => {
  assert.ok(shouldUpdateStatus('Applied', 'OA'));
  assert.ok(shouldUpdateStatus('OA', 'Interview (Round 1)'));
  assert.ok(shouldUpdateStatus('Interview (Round 1)', 'Rejected'));
  assert.ok(shouldUpdateStatus('Recruiter Reachout', 'Interview (Round 1)'));
  assert.ok(shouldUpdateStatus('', 'Rejected'));
  assert.ok(!shouldUpdateStatus('Interview (Round 2)', 'OA'));
  assert.ok(!shouldUpdateStatus('Rejected', 'Interview (Round 1)'));
  assert.ok(!shouldUpdateStatus('Offer (Internship)', 'Rejected'));
  assert.ok(!shouldUpdateStatus('Interview (Round 1)', 'Interview (Round 1)'));
});

test('a role-less confirmation is a duplicate only near an existing row for that company', () => {
  const rows = [{ applied: 'Lab37 - Robotics Software Engineer Intern', date: new Date('2026-09-28T12:00:00') }];
  const day = 24 * 60 * 60 * 1000;
  const sent = new Date('2026-09-28T10:42:01').getTime();
  assert.ok(isRolelessDuplicate('Lab37', '', sent, rows));
  assert.ok(!isRolelessDuplicate('Lab37', '', sent + 10 * day, rows), 'a new application weeks later');
  assert.ok(!isRolelessDuplicate('Lab37', 'Controls Intern', sent, rows), 'role named: exact check applies instead');
  assert.ok(!isRolelessDuplicate('Zipline', '', sent, rows));
  assert.ok(!isRolelessDuplicate('Lab37', '', sent, [{ applied: 'Lab37', date: '' }]), 'undated rows are ignored');
});

test('status updates need a matching role when a company has several rows', () => {
  const rows = [
    { applied: 'SpaceX - Fall 2026 Software Engineering Internship/Co-op' },
    { applied: 'SpaceX - Summer 2027 Software Engineering Internship/Co-op' },
    { applied: 'Citadel - Software Engineer Intern 2027' },
  ];
  assert.ok(!isUnambiguousRow(rows[0], 'SpaceX', '', rows));
  assert.ok(!isUnambiguousRow(rows[0], 'SpaceX', 'Satellite Engineering Role Internship', rows));
  assert.ok(isUnambiguousRow(rows[1], 'SpaceX', 'Summer 2027 Software Engineering Internship/Co-op', rows));
  assert.ok(isUnambiguousRow(rows[2], 'Citadel', '', rows), 'single row: no role needed');
});
