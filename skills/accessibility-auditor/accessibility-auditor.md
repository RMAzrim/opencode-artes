---
id: accessibility-auditor
name: accessibility-auditor
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---



---
id: accessibility-auditor
file_path: skills/accessibility-auditor.md
name: Accessibility Auditor
category: frontend
tags: [accessibility, wcag, aria, html, jsx]
author: opencode-core
version: 1.0.0
description: Audit HTML/JSX code against WCAG 2.1 guidelines and provide accessible ARIA code fixes.
---

# Accessibility Auditor

## Prerequisites & Dependencies
- Node.js 18+ (for running CLI tools) or a modern browser with DevTools
- Mandatory packages: `npm i axe-core @axe-core/react` or `npm i pa11y`
- Required environment variables: `NODE_ENV=development` (optional, for CI integration)

## Execution Steps
1. Install accessibility dependencies: `npm i axe-core @axe-core/react`
2. Create a test component that renders your UI with meaningful ARIA labels and semantic HTML
3. Run automated accessibility testing: `npx axe-cli ./src/index.js` or integrate with Jest via `jest-axe`
4. Review the report and apply suggested ARIA fixes (e.g., missing `aria-label`, `role=` attributes, color contrast ratios)
5. Manually keyboard-test your component (Tab navigation, Escape handling, focus management)
6. Verify fixes against WCAG 2.1 AA criteria: perceivable, operable, understandable, robust

```javascript
// Example: Accessible button with ARIA labels and keyboard handling
import React from 'react';

const AccessibleButton = ({ onClick, label }) => (
  <button
    onClick={onClick}
    aria-label={label}
    className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
  >
    {label}
  </button>
);

export default AccessibleButton;
```