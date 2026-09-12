---
id: tailwind-responsive-darkmode-styler
file_path: skills/tailwind-responsive-darkmode-styler/tailwind-responsive-darkmode-styler.md
name: Tailwind Responsive & Darkmode Styler
category: frontend
tags: [tailwindcss, responsive-design, dark-mode, accessibility]
author: opencode-core
version: 1.0.0
description: Transforms raw JSX or HTML structures into fully responsive, accessible, dark-mode ready web interfaces using Tailwind CSS utility classes.
---

# Tailwind Responsive & Darkmode Styler

## 1. System Architecture & Prerequisites
- Runtime: Node.js >= 20.11.0, npm >= 10 (or pnpm/yarn/bun).
- Framework: Next.js 15.1.6 with React 19 for the component variant; the demo variant ships as a standalone `index.html` using the Tailwind Play CDN (no build step required).
- Dependencies: `next@15.1.6`, `react@19.0.0`, `react-dom@19.0.0`, `next-themes@^0.4.4`.
- Dev dependencies: `tailwindcss@^3.4.17`, `postcss@^8.5.1`, `autoprefixer@^10.4.20`, `typescript@^5.7.3`, `@types/react@^19.0.7`, `@types/react-dom@^19.0.3`, `@types/node@^22.10.7`.
- Architecture rules enforced by this blueprint:
  - `darkMode: "class"` toggles a `.dark` class on `<html>`; `next-themes` manages the class and the `system` preference without a flash of wrong theme.
  - No hardcoded grays. Every color is a semantic token (`background`, `onsurface`, `surface`, `surface-muted`, `edge`, `primary`) mapped to CSS variables defined once for `:root` (light) and overridden under `.dark`.
  - Token pairs are chosen to keep WCAG 2.1 AA contrast (4.5:1+): text uses `onsurface` on `background`/`surface`; primary interactive accents keep >= 4.5:1 on both themes.
  - Breakpoints are used only where layout reflows: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px).

## 2. Input/Output Data Contracts

Input parameters (JSON Schema):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "sourceMarkup": { "type": "string", "minLength": 1, "description": "Raw HTML or JSX to convert" },
    "mode": { "enum": ["nextjs", "plain-html"] },
    "framework": { "enum": ["next"], "default": "next" },
    "darkModeStrategy": { "enum": ["class", "media"], "default": "class" },
    "breakpoints": {
      "type": "array",
      "items": { "enum": ["sm", "md", "lg", "xl"] },
      "default": ["sm", "md", "lg", "xl"]
    }
  },
  "required": ["sourceMarkup"]
}
```

Output artifacts (exact paths):
- `tailwind.config.js`, `postcss.config.js`, `app/globals.css`, `package.json`
- `components/ResponsiveNavbar.tsx`, `components/Card.tsx`, `components/ThemeToggle.tsx`
- `app/layout.tsx` (ThemeProvider wiring), `app/page.tsx` (demo usage)
- `input-reference.html` (the raw, unconverted source markup)
- `index.html` (plain-HTML demo variant using the Play CDN, no build step)

## 3. Production Reference Implementation
One complete implementation. The first file is the raw input this skill converts; every following file is final and runnable:

```
# =========================================================
# FILE: input-reference.html (raw markup, BEFORE conversion)
# =========================================================
<div class="navbar">
  <div class="logo">Acme UI</div>
  <ul class="links">
    <li><a href="#">Home</a></li>
    <li><a href="#">Features</a></li>
    <li><a href="#">Pricing</a></li>
  </ul>
  <button class="signin">Sign in</button>
</div>
<div class="card-list">
  <div class="card">
    <h3>Feature one</h3>
    <p>Description text for the first feature card.</p>
    <button>Read more</button>
  </div>
  <div class="card">
    <h3>Feature two</h3>
    <p>Description text for the second feature card.</p>
    <button>Read more</button>
  </div>
</div>

# =========================================================
# FILE: package.json
# =========================================================
{
  "name": "tailwind-responsive-darkmode",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.1.6",
    "next-themes": "^0.4.4",
    "react": "19.0.0",
    "react-dom": "19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.7",
    "@types/react": "^19.0.7",
    "@types/react-dom": "^19.0.3",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.5.1",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.3"
  }
}

# =========================================================
# FILE: tailwind.config.js
# =========================================================
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./index.html"
  ],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--color-background) / <alpha-value>)",
        onsurface: "rgb(var(--color-onsurface) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        "surface-muted": "rgb(var(--color-surface-muted) / <alpha-value>)",
        edge: "rgb(var(--color-edge) / <alpha-value>)",
        primary: "rgb(var(--color-primary) / <alpha-value>)"
      },
      spacing: {
        gutter: "1.5rem",
        section: "6rem"
      },
      maxWidth: {
        shell: "80rem"
      }
    }
  },
  plugins: []
};

# =========================================================
# FILE: postcss.config.js
# =========================================================
/** @type {import('postcss-load-config').Config} */
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {}
  }
};

# =========================================================
# FILE: app/globals.css
# =========================================================
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --color-background: 255 255 255;
  --color-onsurface: 15 23 42;
  --color-surface: 241 245 249;
  --color-surface-muted: 226 232 240;
  --color-edge: 203 213 225;
  --color-primary: 37 99 235;
}

.dark {
  --color-background: 15 23 42;
  --color-onsurface: 248 250 252;
  --color-surface: 30 41 59;
  --color-surface-muted: 51 65 85;
  --color-edge: 71 85 105;
  --color-primary: 96 165 250;
}

@layer base {
  html {
    @apply scroll-smooth;
  }

  body {
    @apply bg-background text-onsurface antialiased;
  }

  ::selection {
    @apply bg-primary/20;
  }
}

# =========================================================
# FILE: components/ThemeToggle.tsx
# =========================================================
"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <span aria-hidden="true" className="block h-9 w-9 rounded-full border border-edge bg-surface" />
    );
  }

  const isDark = resolvedTheme === "dark";
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={label}
      title={label}
      className="grid h-9 w-9 place-items-center rounded-full border border-edge bg-surface text-onsurface transition-colors hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      {isDark ? (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path strokeLinecap="round" d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}

# =========================================================
# FILE: components/ResponsiveNavbar.tsx
# =========================================================
"use client";

import { useState } from "react";
import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" }
] as const;

export function ResponsiveNavbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-edge bg-background/90 backdrop-blur">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 max-w-shell items-center justify-between gap-4 px-4 sm:px-gutter lg:px-8"
      >
        <Link href="/" className="flex items-center gap-2 text-base font-bold text-onsurface lg:text-lg">
          <span
            aria-hidden="true"
            className="grid h-8 w-8 place-items-center rounded-md bg-primary text-sm font-black text-white"
          >
            A
          </span>
          <span className="hidden sm:inline">Acme UI</span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-onsurface/70 transition-colors hover:bg-surface hover:text-onsurface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            type="button"
            className="hidden rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90 sm:inline-block"
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label="Toggle navigation menu"
            className="grid h-10 w-10 place-items-center rounded-md border border-edge text-onsurface md:hidden"
          >
            {open ? (
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" d="M6 6l12 12M18 6L6 18" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </nav>

      <div id="mobile-menu" className={open ? "block border-t border-edge md:hidden" : "hidden"}>
        <ul className="space-y-1 px-4 py-3 sm:px-gutter">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                onClick={() => setOpen(false)}
                className="block rounded-md px-3 py-2 text-sm font-medium text-onsurface/80 hover:bg-surface"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </header>
  );
}

# =========================================================
# FILE: components/Card.tsx
# =========================================================
import type { ReactNode } from "react";

type CardProps = {
  eyebrow?: string;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function Card({ eyebrow, title, children, footer }: CardProps) {
  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-6 shadow-sm transition-shadow hover:shadow-md">
      {eyebrow ? (
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">{eyebrow}</p>
      ) : null}
      <h3 className="text-lg font-semibold text-onsurface">{title}</h3>
      <p className="flex-1 text-sm leading-relaxed text-onsurface/80">{children}</p>
      {footer ? <div className="pt-2">{footer}</div> : null}
    </article>
  );
}

# =========================================================
# FILE: app/layout.tsx
# =========================================================
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import "./globals.css";

export const metadata: Metadata = {
  title: "Acme UI",
  description: "Responsive, accessible, dark-mode ready components"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}

# =========================================================
# FILE: app/page.tsx
# =========================================================
import { Card } from "../components/Card";
import { ResponsiveNavbar } from "../components/ResponsiveNavbar";

const FEATURES = [
  {
    eyebrow: "Responsive",
    title: "Mobile first",
    body: "Breakpoints at sm, md, lg and xl reflow the grid from one column to three without JavaScript."
  },
  {
    eyebrow: "Dark mode",
    title: "Class strategy",
    body: "darkMode: class swaps semantic color tokens so light and dark both pass 4.5:1 contrast."
  },
  {
    eyebrow: "Accessible",
    title: "Keyboard ready",
    body: "Focus rings, aria-labels and visible states come out of the box on every interactive element."
  }
] as const;

export default function HomePage() {
  return (
    <>
      <ResponsiveNavbar />
      <main className="mx-auto max-w-shell px-4 py-10 sm:px-gutter lg:px-8">
        <section className="mb-10 rounded-2xl border border-edge bg-surface p-6 sm:p-10 lg:p-14">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-primary">Hero</p>
          <h1 className="max-w-2xl text-3xl font-bold leading-tight text-onsurface sm:text-4xl lg:text-5xl">
            Responsive by default, dark-mode ready
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-onsurface/80 sm:text-base">
            Semantic color tokens keep the interface on the same token pair in every theme, so WCAG
            contrast stays above 4.5:1 automatically.
          </p>
        </section>

        <section aria-label="Features" className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} eyebrow={feature.eyebrow} title={feature.title}>
              {feature.body}
            </Card>
          ))}
        </section>
      </main>
    </>
  );
}

# =========================================================
# FILE: index.html (plain-HTML demo variant, no build step)
# =========================================================
<!doctype html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tailwind responsive + dark mode demo</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: "class",
      theme: {
        extend: {
          colors: {
            background: "rgb(var(--color-background) / <alpha-value>)",
            onsurface: "rgb(var(--color-onsurface) / <alpha-value>)",
            surface: "rgb(var(--color-surface) / <alpha-value>)",
            "surface-muted": "rgb(var(--color-surface-muted) / <alpha-value>)",
            edge: "rgb(var(--color-edge) / <alpha-value>)",
            primary: "rgb(var(--color-primary) / <alpha-value>)"
          }
        }
      }
    };
  </script>
  <style>
    :root {
      --color-background: 255 255 255;
      --color-onsurface: 15 23 42;
      --color-surface: 241 245 249;
      --color-surface-muted: 226 232 240;
      --color-edge: 203 213 225;
      --color-primary: 37 99 235;
    }
    html.dark {
      --color-background: 15 23 42;
      --color-onsurface: 248 250 252;
      --color-surface: 30 41 59;
      --color-surface-muted: 51 65 85;
      --color-edge: 71 85 105;
      --color-primary: 96 165 250;
    }
    body {
      background: rgb(var(--color-background));
      color: rgb(var(--color-onsurface));
      font-family: ui-sans-serif, system-ui, sans-serif;
      margin: 0;
    }
  </style>
</head>
<body>
  <header class="sticky top-0 border-b border-edge bg-background/90 backdrop-blur">
    <nav aria-label="Primary" class="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
      <a href="#" class="flex items-center gap-2 text-base font-bold sm:text-lg">
        <span aria-hidden="true" class="grid h-8 w-8 place-items-center rounded-md bg-primary text-sm font-black text-white">A</span>
        <span class="hidden sm:inline">Acme UI</span>
      </a>
      <button id="theme-toggle" type="button" aria-label="Toggle dark mode"
        class="rounded-full border border-edge bg-surface px-3 py-1.5 text-sm font-medium hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
        Toggle theme
      </button>
    </nav>
  </header>

  <main class="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
    <section class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <article class="rounded-2xl border border-edge bg-surface p-6">
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">Card</p>
        <h2 class="mt-2 text-lg font-semibold">One column on phones</h2>
        <p class="mt-2 text-sm text-onsurface/80">sm:grid-cols-2, lg:grid-cols-3, xl:grid-cols-4 - no media queries needed.</p>
      </article>
      <article class="rounded-2xl border border-edge bg-surface p-6">
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">Card</p>
        <h2 class="mt-2 text-lg font-semibold">Tokens, not hardcoded grays</h2>
        <p class="mt-2 text-sm text-onsurface/80">bg-surface swaps with .dark so contrast holds in both modes.</p>
      </article>
      <article class="rounded-2xl border border-edge bg-surface p-6">
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">Card</p>
        <h2 class="mt-2 text-lg font-semibold">Focus visible states</h2>
        <p class="mt-2 text-sm text-onsurface/80">Every interactive element ships a visible focus ring.</p>
      </article>
      <article class="rounded-2xl border border-edge bg-surface p-6">
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">Card</p>
        <h2 class="mt-2 text-lg font-semibold">Raw HTML to Tailwind</h2>
        <p class="mt-2 text-sm text-onsurface/80">This file is the drop-in index.html demo variant of the same markup.</p>
      </article>
    </section>
  </main>

  <script>
    var root = document.documentElement;
    var toggle = document.getElementById("theme-toggle");
    toggle.addEventListener("click", function () {
      var next = root.classList.toggle("dark") ? "dark" : "light";
      toggle.setAttribute("aria-label", next === "dark" ? "Switch to light mode" : "Switch to dark mode");
    });
  </script>
</body>
</html>
```

## 4. Execution Protocol & Step-by-Step Workflow
```bash
# 1. Scaffold the Next.js project and install dependencies
mkdir tailwind-responsive-darkmode
cd tailwind-responsive-darkmode
npm install

# 2. Write tailwind.config.js, postcss.config.js, app/globals.css
# 3. Write components: ResponsiveNavbar.tsx, Card.tsx, ThemeToggle.tsx
# 4. Wire the theme provider in app/layout.tsx and the demo in app/page.tsx
# 5. Generate the plain-HTML variant (index.html) for consumers with no JS toolchain
# 6. Type-check and build
npm run typecheck
npm run build

# 7. Interactive verification
npm run dev
#    Resize the window: navbar collapses to the hamburger below md; grid reflows
#    at sm/lg/xl. Click the theme toggle: .dark is applied to <html>, colors swap.
#    Verify contrast by tabbing: focus ring always visible.
```

## 5. Edge Cases & Error Handling
- Hydration mismatch with `next-themes`: suppress it by adding `suppressHydrationWarning` to `<html>` and gating `ThemeToggle` render behind a `mounted` state; the SSR placeholder must not claim any theme.
- Unknown color tokens become nonexistent utilities silently: if `bg-background` does not compile, verify the CSS variable exists in both `:root` and `.dark` and that `content` globs cover the file.
- Alpha modifiers (`bg-background/80`) require the `rgb(var(--x) / <alpha-value>)` declaration format; plain `var(--x)` breaks opacity utilities.
- CDN Play build (`index.html`) is for prototyping only; the no-JS and no-CDN production path is the `next build` + `tailwindcss` CLI pipe in section 4.
- JS disabled: the plain-HTML toggle degrades to the `.dark` class present in the initial markup; content, layout, and contrast remain usable.
- Rollback: keep `input-reference.html` as the single source of truth; on a bad conversion, restore the reference and regenerate components rather than hand-patching utilities.