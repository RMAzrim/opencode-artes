---
name: Postmortem Autobiographer
description: Turn an incident description or production stack trace into a structured postmortem with timeline, 5-whys, and trackable action items — ready for team review.
metadata:
  source: skills/postmortem-autobiographer/postmortem-autobiographer.md
---

# Postmortem Autobiographer

## 1. System Architecture & Prerequisites

Every incident deserves a review, but blank-page postmortems never get written.
The Autobiographer takes raw material — an incident description, a stack trace
paste, timestamps, slack snippets — and composes a structured, blame-free
document following industry conventions (Google SRE model): summary, timeline,
impact, root cause via 5-why, and action items with owners and deadlines.
Node 18+ stdlib.

Input formats recognized:

- Stack traces (V8, Python, generic) — service/exception extracted
- Free-form incident notes (timestamps `YYYY-MM-DD HH:MM`, `@owner`, `action`)
- Structured JSON `{ title, started, ended, summary, services[] }`

## 2. Input/Output Data Contracts

Input: a text file and optional starter JSON. Output `POSTMORTEM.md` (plus raw
`postmortem.json`) with sections:

- `# Postmortem: <title>` + status (DRAFT)
- `## Summary` / `## Timeline` / `## Impact`
- `## Root Cause (5-Why)` — five chained why rows
- `## Action Items` — `- [ ]` checklist with `owner:` and `by:` metadata
- `## Prevention Notes`

Exit: `0` always on successful generation; `2` if no usable material.

## 3. Production Reference Implementation

```js
// postmortem-autobiographer.js
const fs = require('fs');
const path = require('path');

const inputFile = process.argv[2];
const title = process.argv[3] || 'Incident Review';
if (!inputFile) { console.error('usage: node postmortem-autobiographer.js <incident.txt|incident.json> [title]'); process.exit(2); }
const raw = fs.readFileSync(inputFile, 'utf-8');

function parseStack(raw) {
  const lines = raw.split(/\r?\n/);
  const exception = lines.find((l) => /(Error|Exception|Traceback|failed|FATAL)/i.test(l))?.trim() || 'Unknown exception';
  const frames = lines.filter((l) => /^\s+at\s|^\s+File\s"/.test(l)).slice(0, 8).map((l) => l.trim());
  const first = frames[0] || exception;
  return { exception, firstFrame: first, frames };
}

function parseNotes(raw) {
  const timeline = [];
  const re = /(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)/g;
  let m;
  while ((m = re.exec(raw))) timeline.push({ time: m[1] });
  const owners = [...new Set((raw.match(/@(\w+)/g) || []).map((o) => o.slice(1)))];
  const actions = (raw.match(/^(?:-\s*\[\s*\]|action:?)\s*(.+)$/gim) || []).map((a) => a.replace(/^-\s*\[\s*\]\s*/, '').replace(/^action:?\s*/i, ''));
  return { timeline, owners, actions };
}

let input = { title, summary: '', body: raw };
try { const j = JSON.parse(raw); input = { ...input, ...j }; } catch {}

const st = parseStack(raw);
const notes = parseNotes(raw);

// Craft 5-whys from the evidence (heuristic chain, human confirms each level).
const whys = [];
const problem = input.summary || st.exception || 'Unexpected failure in production';
whys.push(`1. **Why did ${problem} occur?** — Direct cause observed: ${st.firstFrame || 'no frame captured; see timeline'}.`);
whys.push('2. **Why was the direct cause possible?** — Guard/validation missing or ordering wrong (verify against code).');
whys.push('3. **Why was the guard missing?** — Assumption made earlier; not encoded as a test/budget/boundary check.');
whys.push('4. **Why was the assumption not encoded?** — Change-management/review gap; refactor without characterization coverage.');
whys.push('5. **Why did that persist?** — Missing feedback loop (alerting/detection) surfaced it only after user impact.');

const actionItems = (notes.actions.length ? notes.actions : [
  'Add characterization test reproducing the failure path',
  'Add alert/budget gate so a recurrence trips before user impact',
]).map((a, i) => {
  const owner = notes.owners[i % Math.max(1, notes.owners.length)] || 'TBD';
  const by = new Date(Date.now() + 5 * 86400000).toISOString().slice(0, 10);
  return `- [ ] ${a}  \`owner: ${owner}\` \`by: ${by}\``;
});

const timelineMd = notes.timeline.length
  ? notes.timeline.map((t, i) => `- \`${t.time}\` step ${i + 1} (event recorded in notes)`).join('\n')
  : '- (no timestamps recovered — reconstruct from logs)';

const md = [
  `# Postmortem: ${input.title}`, '',
  `**Status:** DRAFT · **Severity:** pending`, '',
  '## Summary', '', input.summary || 'Production impact event(s) detected; see timeline and evidence.', '',
  '## Timeline', '', timelineMd, '',
  '## Impact', '', '- Affected service/function: to be filled', '- User-visible impact: to be filled', '- Metrics (error rate/latency): to be filled', '',
  '## Root Cause (5-Why)', '', ...whys, '',
  '## Evidence', '', `- First frame: \`${st.firstFrame}\``, ...st.frames.slice(0, 4).map((f) => `- Frame: \`${f}\``), '',
  '## Action Items', '', ...actionItems, '',
  '## Prevention Notes', '', '- Verify 5-whys line 2 against the actual guard', '- Link monitoring dashboards + runbook', '- Set severity and owner; schedule review',
].join('\n');

fs.writeFileSync('POSTMORTEM.md', md);
fs.writeFileSync('postmortem.json', JSON.stringify({ title: input.title, problem, owners: notes.owners, actions: actionItems }, null, 2));
console.log(`Postmortem written: POSTMORTEM.md (${actionItems.length} action items; owners: ${notes.owners.join(', ') || 'TBD'})`);
process.exit(0);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Collect the incident material into one file: stack trace dump, timestamps,
   `@owner` tags, and any explicit action lines.
2. `node postmortem-autobiographer.js incident.txt "API latency spike Sep 12"`.
3. Review the generated `POSTMORTEM.md` and fill the `Impact` placeholders —
   the tool extracts what it can extract; market impact must come from humans.
4. Walk the 5-whys chain with the actual guard in code: level 2 is the load
   bearing one — verify which check was missing by reading the diff/deployment.
5. Assign owners to every action item, blast it in the channel, track closed
   items in the review, and move the status from DRAFT once resolved.
6. Store the final `POSTMORTEM.md` alongside the team's incident reviews;
   link it from the monitoring dashboard.

## 5. Edge Cases & Error Handling

- No timestamps recovered → the timeline section politely says so and asks for
   reconstruction, instead of fabricating events.
- No owners/actions recovered → defaults to `TBD` owner and a 5-day `by` date,
   but the empty-places force human completion rather than silent GTM.
- Malformed JSON input falls back to treating the text as free-form notes; the
   document is still generated.
- Multi-error stack traces keep only the first exception for the "problem"
   line but list extra frames as evidence.
- The 5-whys are *hypotheses* the team must verify — the report is designed for
   a group review, not as a finished accountability document.
