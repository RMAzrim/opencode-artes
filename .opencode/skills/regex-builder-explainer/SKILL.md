---
name: Regex Builder & Explainer
description: Construct complex regular expressions based on pattern requirements with step-by-step logic breakdown.
metadata:
  source: skills/regex-builder-explainer/regex-builder-explainer.md
---

# Regex Builder & Explainer

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- Mandatory packages: `npm i regexp-score` (for regex quality scoring) or built-in `RegExp` methods
- A code editor with regex support (VS Code, IntelliJ, Vim)
- Optional: `npm iregex-gen` for generative regex creation (experimental)

## Execution Steps
1. Clearly define the pattern requirement: list the characters, digits, delimiters, quantifiers, and edge cases the regex must match
2. Break the pattern into segments: anchors (start `^`, end `$`), character classes, quantifiers, groups, and alternations
3. Construct the regex incrementally, testing each segment with sample inputs before compositing
4. Use online testers or Node REPL to validate: `const re = /pattern/; re.test('input')`
5. Add flags appropriately: `i` (case-insensitive), `g` (global), `m` (multiline), `s` (dotall)
6. Document the regex with inline comments using the `(?#comment)` syntax or `/** @type {RegExp} */` JSDoc
7. Export or share the final regex: as a string constant, a RegExp object, or a code snippet in your docs

```javascript
// Example: Regex to validate a strong password
// Requirements: 8+ characters, at least 1 uppercase, 1 lowercase, 1 digit, 1 special char
const strongPasswordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])[A-Za-z\d!@#$%^&*]{8,}$;

// Test cases
const tests = [
  { input: 'Weak123', expected: false, desc: 'no uppercase, only 1 special' },
  { input: 'StrongPass!', expected: true, desc: 'meets all criteria' },
  { input: 'strongpass!', expected: false, desc: 'missing uppercase' },
  { input: 'StrongPass', expected: false, desc: 'missing digit' },
];

tests.forEach(({ input, expected, desc }) => {
  const result = strongPasswordRegex.test(input);
  console.log(
    `${desc}: "${input}" → ${result} (expected ${expected}) ${result === expected ? '✅' : '❌'}`
  );
});
```

```bash
# Test regex in Node REPL
node -e '
const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])[A-Za-z\d!@#$%^&*]{8,}$/;
console.log(re.test("StrongPass!")); // true
console.log(re.test("weak"));      // false
'
`
```

```regex
# Final regex with comments for documentation
/^(?# anchor start)
  (?=.*[a-z]  # at least one lowercase letter
  (?=.*[A-Z]  # at least one uppercase letter
  (?=.*\d     # at least one digit
  (?=.*[!@#$%^&*])  # at least one special char from set
  [A-Za-z\d!@#$%^&*]{8,}  # 8+ alphanumeric/special chars
$/x  // free-spacing mode: ignores whitespace and allows comments
`
```
