---
id: regex-builder-parser
name: regex-builder-parser
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: regex-builder-parser
file_path: skills/regex-builder-parser.md
name: Regex Builder & Parser
category: core-coding
tags: [regex, redoS, parser, string-extraction, patterns]
author: opencode-core
version: 1.0.0
description: Construct ReDoS-safe regular expressions and string parser logic for complex input string extraction.
---

# Regex Builder & Parser

## Prerequisites & Dependencies
- Node.js 18+ or Python 3.10+ with regex engine knowledge
- `npm i redoS` (for safety scoring) or Python's `re` module + `rstr` for generation
- Comfortable with character classes, quantifiers, grouping, and anchors

## Execution Steps
1. Clearly define the input format and extraction goal: what substrings, delimiters, or patterns must be captured
2. Sketch the regex on paper first: anchors (`^`, `$`), delimiters, optional groups, alternation (`|`)
3. Build the regex incrementally, testing each component against sample inputs before compositing
4. Use atomic groups `(?>...)` or possessive quantifiers `++`/`*`+` (if supported) to prevent backtracking exploits
5. Score the regex for ReDoS risk: `npm i redoS` → `checkRegex(regex)` should report low catastrophic backtracking risk
6. Favor simpler alternatives: string methods (`split`, `match`), `String.prototype.replace`, or parser combinators if the pattern exceeds ~20 characters or has nested quantifiers
7. Document the final regex with inline comments `/** @type {RegExp} */` and a brief explanation of each section

```javascript
// Safe regex: extract filename without extension from a path
// Breakdown: ^ anchors start, [^/]+ matches one or more non-slash chars, \. matches literal dot, $ anchors end
// Atomic group prevents backtracking on malicious inputs
const safeFilenameRegex = /^(?>[^/]+)\.([^.]+)$/;

// Test cases
const tests = [
  { input: '/path/to/document.pdf', expected: 'document', desc: 'pdf extension' },
  { input: 'archive.tar.gz', expected: 'archive', desc: 'double extension (should match first)' },
  { input: 'noext', expected: 'noext', desc: 'no dot, return basename' },
];

tests.forEach(({ input, expected, desc }) => {
  const match = input.match(safeFilenameRegex);
  const ok = match && match[1] === expected;
  console.log(`${desc}: "${input}" → ${match ? match[1] : 'null'} ${ok ? '✅' : '❌'}`);
});
```

```bash
# ReDoS safety check (Node)
const { checkRegex } = require('redoS');
const regex = /^(?>[^/]+)\.([^.]+)$/;
const result = checkRegex(regex, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.');
console.log(result); // { safe: true, maxIterations: ... } or warns about backtracking
```
```