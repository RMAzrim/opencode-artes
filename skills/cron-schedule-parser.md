---
id: cron-schedule-parser
file_path: skills/cron-schedule-parser.md
name: Cron Schedule Parser
category: developer-experience
tags: [cron, scheduling, time-rules, nodejs, python]
author: opencode-core
version: 1.0.0
description: Translate natural language time rules into valid 5-part or 6-part Cron schedule expressions.
---

# Cron Schedule Parser

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm (or Python 3.10+ for alternative implementation)
- Mandatory packages: `npm i node-cron` (for scheduling) or built-in cron expression parsing libraries
- A natural language description of the desired schedule (e.g., "every Monday at 9 AM", "at the start of every month", "every 15 minutes between 9 AM and 5 PM")

## Execution Steps
1. Parse the natural language schedule into components: frequency (minutely, hourly, daily, weekly, monthly), specific day(s), time of day, and optional ranges/intervals
2. Map components to the 5-field cron format: `minute hour day-of-month month day-of-week`
   - Minute: 0–59
   - Hour: 0–23 (0 = midnight)
   - Day-of-month: 1–31
   - Month: 1–12 or JASON, Jan–Dec
   - Day-of-week: 0–7 (0 and 7 = Sunday)
3. Generate the cron expression string, using `*` for every value, `,` for lists, `-` for ranges, `/` for steps, and `?` for "no specific value" (in day-of-month or day-of-week)
4. Validate the expression: use `cron-parser` npm package or custom unit tests to ensure the schedule fires as expected
5. (Optional) Generate 6-field format including year: `year minute hour day month dow`
6. Export the result as a string for use in `node-cron`, `crontab`, CI/CD pipelines, or cron monitoring tools

```javascript
// Example: Cron expression generator from natural language
const cronParser = require('cron-parser');

const naturalSchedules = {
  'every minute': '*/1 * * * *',
  'every hour': '0 * * * *',
  'at 9 AM daily': '0 9 * * *',
  'every Monday at 9 AM': '0 9 * * 1',
  'at the start of every month': '0 0 1 * *',
  'every 15 minutes': '*/15 * * * *',
  'weekdays at 8 AM and 5 PM': '0 8,17 * * 1-5',
};

naturalSchedules.forEach((cronExpr, nat) => {
  // cron-parser can validate and parse next run times
  const parser = cronParser.parseExpression(cronExpr);
  const next = parser.next().toString();
  console.log(`Natural: "${nat}" → Cron: "${cronExpr}"`);
  console.log(`  Next run: ${next}`);
});
```

```bash
npm i cron-parser

# Using node-cron for scheduled tasks
const cron = require('node-cron');

cron.schedule('0 9 * * 1-5', () => {
  console.log('🔔 Running weekday morning job at 9 AM');
});
```

```text
# Cron format reference (5 fields)

| Field         | Allowed values |
|---------------|----------------|
| Minute        | 0–59           |
| Hour          | 0–23           |
| Day-of-month  | 1–31           |
| Month         | 1–12 or names  |
| Day-of-week   | 0–7 (0,7 = Sun) |

# Symbols

- `*` → every value
- `,` → list (e.g., `1,15`)
- `-` → range (e.g., `1-5`)
- `/` → step (e.g., `*/2` every 2)
- `?` → no specific value (used in day-of-month or day-of-week when one field is specified)

# Examples

| Description              | Cron Expression |
|--------------------------|-----------------|
| Every minute             | `*/1 * * * *`   |
| 9 AM daily               | `0 9 * * *`     |
| Mondays at 9 AM          | `0 9 * * 1`     |
| Weekdays 8 AM – 5 PM     | `0 8-17 * * 1-5`|
| Every 15 minutes         | `*/15 * * * *`  |
| Start of each month      | `0 0 1 * *`     |
```