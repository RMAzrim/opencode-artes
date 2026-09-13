---
id: pr-logic-reviewer
file_path: skills/pr-logic-reviewer/pr-logic-reviewer.md
name: PR Logic Reviewer
category: developer-experience
tags: [code-review, pull-request, logic, bugs, boundaries, diff]
author: opencode-core
version: 1.0.0
description: Review a pull-request diff for logic bugs — boundary conditions, null safety, state and edge semantics — not style, and emit a bug-first review report.
---

# PR Logic Reviewer

## 1. System Architecture & Prerequisites

Most automated review checks style; the bugs live in logic. This skill reads a
diff (from `git diff` or a PR), extracts the changed hunks, and applies
targeted heuristic probes for the highest-risk bug classes — then presents a
report ordered by severity that a human reviewer verifies. Node 18+ stdlib.

Bug classes it drives you toward:

- `BOUNDARY` — off-by-one, `<=` vs `<`, empty arrays, `first`/`last` on empty
- `NULL` — dereference without guard after async, `?.` misplacement, unfiltered
  falsy (0, "", false treated as "not set")
- `STATE` — read-then-write races, loops mutating the collection they iterate,
  stale closure values
- `ASYNC` — promise not awaited, parallel writes to same resource
- `INVARIANT` — duplicated branches, dead condition, swapped operands

## 2. Input/Output Data Contracts

Input: a unified diff (`git diff main...HEAD`) on stdin, or a file path.

Output `PR_LOGIC_REVIEW.md` + `pr-logic-report.json`:

```json
{ "files": 6, "probes": 42, "hits": [ { "file": "src/auth.ts", "line": 120, "class": "BOUNDARY", "snippet": "if (i >= arr.length-1) ...", "prompt": "verify: does -1 make the last element unreachable?" } ] }
```

Exit: `0` = no hits (still recommend human review), `1` = hits that need
attention (report is advisory — always requires a human sign-off).

## 3. Production Reference Implementation

```js
// pr-logic-reviewer.js
const fs = require('fs');
const path = require('path');

const input = process.argv[2]; // '-' for stdin or a diff file
let diff;
if (input === '-') diff = fs.readFileSync(0, 'utf-8');
else diff = fs.readFileSync(input, 'utf-8');

const files = [];
const fileRe = /^diff --git a\/(\S+) b\/(\S+)/gm;
let m;
while ((m = fileRe.exec(diff))) files.push(m[2]);

const hunks = [];
const hunkRe = /^@@ -\d+(?:,\d+)? \+(\d+)(?:,?(\d+))? @@([\s\S]*?)(?=^@@ |^diff --git |(?![\s\S]))/gm;
let hm;
while ((hm = hunkRe.exec(diff))) {
  const base = Number(hm[1]);
  let ln = base;
  const lines = [];
  for (const l of hm[3].split(/\r?\n/)) {
    if (l.startsWith('+')) { lines.push({ ln, text: l.slice(1) }); ln++; }
    else if (l.startsWith('-')) { /* skip removed */ }
    else if (l.startsWith(' ')) { ln++; }
  }
  hunks.push({ lines: lines.filter((x) => x.text.trim()) });
}

const PROBES = [
  { re: /(\w+)\s*[<>=]=?\s*[^;]*\.length\s*-1|length\s*-\s*1\s*[<>=]/, cls: 'BOUNDARY', hint: 'off-by-one near .length - 1' },
  { re: /\b(?:arr|list|items)\.(?:forEach|map)\([\s\S]{0,80}\1\.(?:push|splice|unshift)/, cls: 'STATE', hint: 'mutating collection during iteration' },
  { re: /if\s*\(!\w+(\.\w+)*\)\s*\{[\s\S]{0,60}\.(\w+)\s*[.\[(]/, cls: 'NULL', hint: 'falsy check followed by property access that may be undefined' },
  { re: /(?:async\s+\w+\(.*\)\s*{[^}]*})\s*(?!await)\n/, cls: 'ASYNC', hint: 'possible un-awaited async (verify on multi-statement bodies)' },
  { re: /(?:==|===)\s*false|!==\s*true\b/, cls: 'INVARIANT', hint: 'redundant boolean comparison' },
  { re: /if\s*\(([\w.]+)\s*[!==]=?\s*[^)]+\)[^{]*\{\s*\n\s*return\s+\3/, cls: 'DUPLICATE', hint: 'adjacent identical return branches — likely copy/paste' },
];

const hits = [];
const seen = new Set();
for (const h of hunks) {
  for (const line of h.lines) {
    for (const probe of PROBES) {
      if (probe.re.test(line.text) && !seen.has(`${line.ln}|${probe.cls}`)) {
        seen.add(`${line.ln}|${probe.cls}`);
        hits.push({ line: line.ln, cls: probe.cls, snippet: line.text.slice(0, 120), hint: probe.hint });
      }
    }
  }
}

const report = { files: files.length, probes: PROBES.length, hits };
fs.writeFileSync('pr-logic-report.json', JSON.stringify(report, null, 2));
const md = ['# PR Logic Review', '',
  `Changed files: **${files.length}** · Probe hits: **${hits.length}**`, '',
  '## Hits (human verifies each)', ''].concat(
  hits.length ? hits.map((h) => `- \`L${h.line}\` [${h.cls}] ${h.snippet}\n  → check: ${h.hint}`) : ['_no automated hits — still perform a manual logic pass_'],
  '', '## Files changed', '',
  ...files.map((f) => `- \`${f}\``));
fs.writeFileSync('PR_LOGIC_REVIEW.md', md.join('\n'));
console.log(md.join('\n'));
process.exit(hits.length ? 1 : 0);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Generate a diff: `git diff main...HEAD --no-color > pr.diff` (or export the
   PR patch from your forge).
2. `node pr-logic-reviewer.js pr.diff` (or `| node pr-logic-reviewer.js -`).
3. For each hit, perform the human verification it asks for — the probe names
   the class, the snippet locates it, and the `hint` tells you exactly what to
   confirm in the reviewer's head.
4. Beyond the automated classes, walk the diff with the "three questions":
   empty input? max input? concurrent input? That trio catches most remaining
   logic bugs the probes can't.
5. Resolve by editing code or by confirming intentional behavior (comment +
   test), and re-run the reviewer to see the hit count drop.
6. Gate merges on the *human* sign-off note, not on the exit code alone — the
   tool is a force-multiplier for reading diffs, never a replacement.

## 5. Edge Cases & Error Handling

- Diffs with conflicting hunk headers (complex merges) are tolerated: each hunk
   is parsed independently and line positions best-effort.
- Binary file diffs (`Binary files ... differ`) are skipped gracefully.
- Probe regexes are intentionally conservative to keep the false-positive rate
   low; they under-fire rather than over-fire, so zero hits is *not* a proof of
   correctness.
- Duplicate changes are deduped by line+class to avoid noise in large PRs.
- Multi-line constructs (mutating loop with a body >1 line) are approximated
   via very small windows; genuine multi-line cases are deliberately under-caught,
   and the manual "three questions" pass covers them.