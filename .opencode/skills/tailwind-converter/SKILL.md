---
name: Tailwind CSS Converter
description: Convert raw CSS or inline styles into clean, idiomatic Tailwind CSS utility classes.
metadata:
  source: skills/tailwind-converter/tailwind-converter.md
---

# Tailwind CSS Converter

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- Mandatory packages: `npm i tailwindcss@latest postcss@latest autoprefixer@latest`
- Optional: `npm i @tailwindcss/typography` for enhanced typography support
- Build tool: `postcss` or a bundler (Vite, Webpack, Next.js) with Tailwind plugin

## Execution Steps
1. Initialize Tailwind: `npx tailwindcss init -p` to generate `tailwind.config.js` and `postcss.config.js`
2. Define your design system in `tailwind.config.js`: extend colors, fonts, breakpoints, and add custom utilities
3. Import Tailwind base directives at the top of your global CSS file: `@tailwind base; @tailwind components; @tailwind utilities;`
4. Convert raw CSS rules to Tailwind utility classes using the mapping: `margin-top: 1rem` → `mt-4`, `color: blue` → `text-blue-500`, `display: flex` → `flex`
5. For complex layouts, use Tailwind's responsive prefixes: `sm:`, `md:`, `lg:` to apply utilities at breakpoints
6. Purge unused classes by configuring the `content` array in `tailwind.config.js` to include all your `.jsx`/`.vue` files
7. Build your production CSS: `npx tailwindcss -i src.css -o dist.css --minify`

```css
/* Input: raw CSS */
.button {
  display: inline-block;
  padding: 0.5rem 1rem;
  background-color: #3b82f6;
  color: white;
  border-radius: 0.375rem;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

/* Output: Tailwind-converted CSS */
.button {
  @apply inline-block px-4 py-2 bg-blue-500 text-white rounded-lg text-lg cursor-pointer transition-colors;
}

/* Responsive variant */
@media (min-width: 768px) {
  .button {
    @apply px-6 py-3 text-xl;
  }
}
```

```bash
npx tailwindcss -i ./src/input.css -o ./dist/output.css --minify
```
