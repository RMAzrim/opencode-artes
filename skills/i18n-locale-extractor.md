---
id: i18n-locale-extractor
file_path: skills/i18n-locale-extractor.md
name: i18n Locale Extractor
category: frontend
tags: [i18n, localization, json, translation, ui]
author: opencode-core
version: 1.0.0
description: Extract hardcoded UI text strings into structured internationalization JSON translation files.
---

# i18n Locale Extractor

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- Mandatory packages: `npm i -g i18next-extract` or `npm i react-i18next i18next`
- A codebase with hardcoded strings (JSX, HTML, or plain text)
- Optional: `npm i -D json5` for flexible JSON handling during extraction

## Execution Steps
1. Scan the codebase for hardcoded string literals: search for `\"`, `'\`, or template literals used in `innerText`, `placeholder`, `alt`, or `render()` calls
2. Extract each unique string and assign a message ID (camelCase or UUID) to avoid collisions
3. Group strings by namespace or component (e.g., `login`, `header`, `footer`) to produce a structured JSON tree
4. Generate the initial translation file in the format expected by your i18n library:
   - **i18next**: `{ "login": { "username": "Username", "password": "Password" } }`
   - **react-i18next**: same JSON structure, consumed via `<Translation>`
5. Replace the original hardcoded strings in the source code with `i18next.t('message.id')` calls (or `t('login.username')` for namespaced access)
6. Validate the extraction by building the app and checking that no missing keys appear in the console warnings
7. Commit the translation JSON files (`en.json`, `es.json`, etc.) and continue translating with your team

```json
// Example: extracted en.json for a login form
{
  "login": {
    "title": "Sign in to your account",
    "username": "Username",
    "password": "Password",
    "submit": "Log in",
    "forgot_password": "Forgot password?"
  },
  "header": {
    "logo": "Acme Corp",
    "nav_home": "Home",
    "nav_profile": "Profile"
  }
}
```

```javascript
// Example: replacing hardcoded strings in a React component
import React from 'react';
import i18next from 'i18next';
import { useTranslation } from 'react-i18next';

const LoginForm = () => {
  const { t } = useTranslation();

  return (
    <form>
      <h2>{t('login.title')}</h2>
      <div>
        <label>{t('login.username')}</label>
        <input type="text" placeholder={t('login.username')} />
      </div>
      <div>
        <label>{t('login.password')}</label>
        <input type="password" placeholder={t('login.password')} />
      </div>
      <button type="submit">{t('login.submit')}</button>
      <a href="/forgot">{t('login.forgot_password')}</a>
    </form>
  );
};

export default LoginForm;

// Initialization (usually in entry point)
i18next.init({
  lng: 'en',
  resources: {
    en: { translation: require('./locales/en.json') },
    // ... other locales
  },
  fallbackLng: 'en',
});
```

```bash
# Extract strings using i18next-extract CLI
i18next-extract -p i18next-extract-defaults.js

# Generate missing locale files
cpLocales/en.json locales/es.json
```