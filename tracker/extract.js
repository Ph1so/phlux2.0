// Pure logic for the application tracker: prompt, request shape, response
// parsing, row matching, and status ordering. Shared by Apps Script (Code.js)
// and the Node tests, so it must not touch any Google or Node APIs.

const TRACKER_MODEL = 'claude-haiku-4-5';
// Confirmation details sit at the top of the email; the cap keeps a long
// HTML-heavy email from costing more than a fraction of a cent.
const MAX_BODY_CHARS = 8000;

const EMAIL_TYPES = ['confirmation', 'rejection', 'assessment', 'interview', 'offer', 'other'];

// Sheet status written for each email type.
const STATUS_FOR_TYPE = {
  confirmation: 'Applied',
  rejection: 'Rejected',
  assessment: 'OA',
  interview: 'Interview (Round 1)',
  offer: 'Offer (Internship)',
};

const SYSTEM_PROMPT = `You read one email from a job applicant's inbox and sort it into exactly one type:

- confirmation: an automated acknowledgement that an application was submitted, e.g. "Thank you for applying", "We've received your application", "Your application to X is in".
- rejection: the company is not moving forward with an application, including "the position has been filled".
- assessment: an invitation to an online assessment, coding challenge, or take-home test.
- interview: an invitation to an interview or a request for interview availability for a role the applicant applied for, including a founder or hiring manager asking to talk about that role.
- offer: a job or internship offer.
- other: everything else, including cold recruiter outreach, recruiter updates that aren't an interview invitation (e.g. "I'll share your resume with the team", team matching, offer logistics), job alerts and recommendations, newsletters, event marketing, notices that a posting closed and asking the applicant to reapply, and emails written by the applicant.

Some rejections open with "Thank you for applying"; classify by what the email is actually telling the applicant.

For every type except other:
- company: the hiring company's common name. Always fill this in, even when the application already appears in the tracker rows ("General Motors", not "GM"; "Johnson & Johnson"). Never the applicant-tracking vendor (Greenhouse, Lever, Ashby, Workday, iCIMS).
- role: the job title as written in the email, keeping season, year, level, and team text, but removing requisition or job IDs such as "R7965", "R-099654", "C314330", "3095747", or "(ID: 10529525)". Use an empty string if the email names no specific role.
For other, company and role are empty strings.

The user message also lists the rows in the applicant's tracker, numbered. For rejection, assessment, interview, and offer, set row to the number of the tracker row this email is about. Set row to 0 if no row is for this company and role, or if several rows at the company could match and the email doesn't say which one. For confirmation and other, row is 0.`;

const OUTPUT_SCHEMA = {
  type: 'object',
  properties: {
    type: { type: 'string', enum: EMAIL_TYPES },
    company: { type: 'string' },
    role: { type: 'string' },
    row: { type: 'integer' },
  },
  required: ['type', 'company', 'role', 'row'],
  additionalProperties: false,
};

// rows: [{ row: <sheet row number>, applied: <"Applied" cell> }]
function emailToText(email, rows) {
  let body = (email.body || '').trim();
  if (body.length > MAX_BODY_CHARS) {
    body = body.slice(0, MAX_BODY_CHARS) + '\n[truncated]';
  }
  const tracker = rows.length
    ? rows.map((r) => `${r.row}. ${r.applied}`).join('\n')
    : '(empty)';
  return `<tracker_rows>\n${tracker}\n</tracker_rows>\n\n<email>\nFrom: ${email.from}\nSubject: ${email.subject}\nDate: ${email.date}\n\n${body}\n</email>`;
}

function buildRequest(email, rows) {
  return {
    model: TRACKER_MODEL,
    max_tokens: 1024,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: emailToText(email, rows || []) }],
    output_config: { format: { type: 'json_schema', schema: OUTPUT_SCHEMA } },
  };
}

// Takes the parsed JSON body of a /v1/messages response.
function parseResponse(response) {
  if (response.stop_reason === 'refusal') {
    throw new Error('Claude declined to classify this email');
  }
  if (response.stop_reason === 'max_tokens') {
    throw new Error('Response hit max_tokens before finishing');
  }
  const textBlock = (response.content || []).find((b) => b.type === 'text');
  if (!textBlock) throw new Error('Response had no text block');
  const result = JSON.parse(textBlock.text);
  return {
    type: EMAIL_TYPES.includes(result.type) ? result.type : 'other',
    company: (result.company || '').trim(),
    role: (result.role || '').trim(),
    row: Number.isInteger(result.row) ? result.row : 0,
  };
}

// The model occasionally returns a non-"other" type with blank fields; the
// caller asks again once when this is true.
function needsRetry(result) {
  return result.type !== 'other' && !result.company;
}

// Seeing its own row in the tracker list makes the model blank the company
// about 40% of the time, so emails are classified without the rows first and
// only status emails get a second call, with the rows, to pick one.
function needsRowLookup(result) {
  return result.type !== 'other' && result.type !== 'confirmation' && Boolean(result.company);
}

// The sheet's "Applied" cell: "Company - Role", or just the company when the
// email names no role.
function formatApplied(company, role) {
  return role ? `${company} - ${role}` : company;
}

function normalizeKey(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]/g, '');
}

// existingCells: values of the sheet's "Applied" column. Punctuation and
// spacing are ignored, so "Johnson&Johnson" matches "Johnson & Johnson", and
// company names match loosely, so "Niantic" matches a "Niantic Spatial" row.
function isDuplicate(company, role, existingCells) {
  const key = normalizeKey(formatApplied(company, role));
  const roleKey = normalizeKey(role);
  return existingCells.some((cell) => {
    const cellKey = normalizeKey(cell);
    if (cellKey === key) return true;
    // Rows typed without the " - " separator, e.g. "NVIDIA 2027 Internships: ...".
    if (roleKey && cellKey === roleKey) return true;
    const cellRole = normalizeKey(String(cell).split(' - ').slice(1).join(' - '));
    return Boolean(roleKey) && cellRole === roleKey && rowMatchesCompany(cell, company);
  });
}

// Guards against the model pointing a status update at another company's row.
// Loose on purpose: "Robert Bosch LLC" should still match a "Bosch - ..." row.
function rowMatchesCompany(cell, company) {
  const rowCompany = normalizeKey(String(cell).split(' - ')[0]);
  const emailCompany = normalizeKey(company);
  if (!rowCompany || !emailCompany) return false;
  return rowCompany.includes(emailCompany) || emailCompany.includes(rowCompany);
}

// A role-less confirmation ("Thanks for applying to Lab37!") counts as a
// duplicate when that company already has a row dated within a few days.
// rows: [{ applied, date }]; date may be a Date, a date string, or blank.
function isRolelessDuplicate(company, role, emailTime, rows) {
  if (role) return false;
  const windowMs = 3 * 24 * 60 * 60 * 1000;
  return rows.some((r) => {
    const t = new Date(r.date).getTime();
    return rowMatchesCompany(r.applied, company) && !isNaN(t) && Math.abs(t - emailTime) <= windowMs;
  });
}

// When a company has several rows, a status email must name a role that
// matches the chosen row; otherwise it could belong to any of them.
function isUnambiguousRow(target, company, role, rows) {
  const sameCompany = rows.filter((r) => rowMatchesCompany(r.applied, company));
  if (sameCompany.length <= 1) return true;
  const rowRole = normalizeKey(String(target.applied).split(' - ').slice(1).join(' - '));
  const emailRole = normalizeKey(role);
  return Boolean(rowRole && emailRole) && (rowRole.includes(emailRole) || emailRole.includes(rowRole));
}

function statusRank(status) {
  const s = String(status || '').trim().toLowerCase();
  if (s.startsWith('offer')) return 4;
  if (s.startsWith('rejected')) return 3;
  if (s.startsWith('interview')) return 2;
  if (s === 'oa') return 1;
  return 0;
}

// Statuses only move forward, so a late OA reminder never overwrites
// "Interview" and nothing overwrites an offer.
function shouldUpdateStatus(current, next) {
  return statusRank(next) > statusRank(current);
}

if (typeof module !== 'undefined') {
  module.exports = {
    TRACKER_MODEL,
    MAX_BODY_CHARS,
    EMAIL_TYPES,
    STATUS_FOR_TYPE,
    SYSTEM_PROMPT,
    OUTPUT_SCHEMA,
    emailToText,
    buildRequest,
    parseResponse,
    needsRetry,
    needsRowLookup,
    formatApplied,
    normalizeKey,
    isDuplicate,
    rowMatchesCompany,
    isRolelessDuplicate,
    isUnambiguousRow,
    statusRank,
    shouldUpdateStatus,
  };
}
