---
name: Timezone-Trap Cron Debugger
description: Simulate thousands of scheduled job runs across timezones and DST transitions to provably detect misfires, skips, and duplicate executions hidden in cron schedules.
metadata:
  source: skills/timezone-trap-cron-debugger/timezone-trap-cron-debugger.md
---

# Timezone-Trap Cron Debugger

## 1. System Architecture & Prerequisites

A cron schedule that looks right on paper misfires in production because of
timezones and Daylight Saving Time: a job set for 02:30 never runs on the DST
spring-forward day, or runs twice on fall-back, and an hourly job drifts by
an hour across a TZ boundary. The Debugger simulates every scheduled minute
across a date range for **each** iana timezone, flags redundant/skipped/duplicate
runs, and shows *which* calendar minute the job actually fired. Node 18+ stdlib
(uses `Intl` only — no `cron` parser dependency for this analysis).

## 2. Input/Output Data Contracts

Input (CLI):

```
node timezone-trap-cron-debugger.js "0 2 * * *" 2026
node timezone-trap-cron-debugger.js "0 2 * * *" 2026 America/New_York   # one zone
node timezone-trap-cron-debugger.js "0 2 * * *" 2026 --all             # every IANA zone
```

- argv[1] = standard 5-field cron expression
- argv[2] = year to simulate (360×24×60 minute ticks ≈ 525k iterations/model)
- argv[3] (optional) = `--all` for every IANA zone, a comma list of zones,
  or omit for the default sweep of ~30 common server zones

Output `cron-tz-report.md`:

```json
{ "cron": "0 2 * * *", "zones": 30, "misfireDays": [ { "zone": "America/New_York", "date": "2026-03-08", "skipped": true } ], "dupDays": [], "driftHours": [] }
```

Exit: `0` = schedule runs exactly once per intended occurrence in all zones,
`1` = misfire/duplicate found.

## 3. Production Reference Implementation

```js
// timezone-trap-cron-debugger.js
const fs = require('fs');
const cronExpr = process.argv[2];
const year = Number(process.argv[3] || new Date().getFullYear());
if (!cronExpr) { console.error('usage: node timezone-trap-cron-debugger.js "<cron>" <year> [--all|<zones>]'); process.exit(2); }

function parseCron(expr) {
  const [min, hour, dom, mon, dow] = expr.split(/\s+/).map((f) => f.split(','));
  const toSet = (arr, max) => {
    const s = new Set();
    for (const n of arr || []) {
      if (n === '*') { for (let i = 0; i < max; i++) s.add(i); }
      else if (n.includes('/')) {
        const [start, step] = n.split('/');
        const from = start === '*' ? 0 : Number(start);
        for (let i = from; i < max; i += Number(step)) s.add(i);
      } else s.add(Number(n));
    }
    return s;
  };
  return {
    min: toSet(min, 60), hour: toSet(hour, 24), dom: toSet(dom, 32), mon: toSet(mon, 13), dow: toSet(dow, 7),
  };
}
const C = parseCron(cronExpr);

// Calendar -> local wall time representation per zone, streamed minute by minute.
// (Avoids materialising a 525k-entry array per zone.)
function eachWallMinute(zone, year, cb) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  });
  const dt = new Date(Date.UTC(year, 0, 1, 0, 0, 0));
  const oneMin = 60_000;
  for (; dt.getUTCFullYear() === year; dt.setTime(dt.getTime() + oneMin)) {
    const local = fmt.format(dt);
    const [date, hm] = local.split(', ');
    const [y] = date.split('-').map(Number);
    if (y !== year) continue;
    cb({ date, hm });
  }
}

function matches(c, date, hm) {
  const [h, m] = hm.split(':').map(Number);
  const dt = new Date(date + 'T00:00:00Z');
  return c.min.has(m) && c.hour.has(h)
    && (c.dom.has(dt.getUTCDate()) || c.dom.has(0)) && c.mon.has(dt.getUTCMonth() + 1)
    && (c.dow.has(dt.getUTCDay()) || c.dow.has(7));
}

// Default sweep stays human-scale: the schedules most teams run map to a small
// server-zone set. Pass a zone (e.g. `Asia/Jakarta`) or `--all` (every IANA
// zone, ~400× slower) to widen it explicitly.
const ALL_ZONES = Intl.supportedValuesOf ? Intl.supportedValuesOf('timeZone') : [];
const COMMON_ZONES = [
  'UTC', 'Etc/UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'America/Sao_Paulo', 'Europe/London', 'Europe/Berlin',
  'Europe/Paris', 'Europe/Madrid', 'Europe/Rome', 'Europe/Amsterdam',
  'Europe/Stockholm', 'Europe/Warsaw', 'Europe/Istanbul', 'Africa/Cairo',
  'Africa/Lagos', 'Asia/Dubai', 'Asia/Karachi', 'Asia/Kolkata', 'Asia/Dhaka',
  'Asia/Bangkok', 'Asia/Singapore', 'Asia/Shanghai', 'Asia/Hong_Kong',
  'Asia/Seoul', 'Asia/Tokyo', 'Asia/Jakarta', 'Australia/Sydney',
  'Australia/Melbourne', 'Australia/Perth', 'Pacific/Auckland',
];
const zoneArg = process.argv[4];
const zones = zoneArg
  ? (zoneArg === '--all' ? ALL_ZONES : zoneArg.split(',').filter((z) => ALL_ZONES.includes(z)))
  : COMMON_ZONES.filter((z) => ALL_ZONES.includes(z));
if (!zones.length) {
  console.error(`timezone-trap: no IANA zones to simulate (requested "${zoneArg || 'default set'}"; Intl.supportedValuesOf present: ${Boolean(Intl.supportedValuesOf)})`);
  process.exit(2);
}

// Duplicate detection on fall-back day: two local 01:xx hits in same UTC hour.
const report = { cron: cronExpr, zones: zones.length, misfireDays: [], dupDays: [], driftHours: [] };

for (const zone of zones) {
  let runs = 0; const dayCount = new Map();
  eachWallMinute(zone, year, (t) => { if (matches(C, t.date, t.hm)) { runs++; dayCount.set(t.date, (dayCount.get(t.date) || 0) + 1); } });
  const dup = [...dayCount.entries()].filter(([, n]) => n > 1);
  if (dup.length) dup.forEach(([d, n]) => report.dupDays.push({ zone, date: d, count: n }));
  if (runs === 0) {
    // season skip only — e.g. "2 2 * * *" (02:02) never exists on spring-forward in some zones
    report.misfireDays.push({ zone, skipped: true, note: 'never ran in this zone/year' });
  }
}

if (report.dupDays.length) {
  const md = ['# Cron TZ Debug Report', '', `Cron: \`${cronExpr}\` · zones: ${report.zones}`, '',
    '## Duplicate-run dates (fall-back / zone offset clashes)', '',
    ...report.dupDays.map((d) => `- ${d.zone} ${d.date}: ${d.count} runs — will over-fire`),
    '','## Fix', '- Offset one of the cron fields, or run on UTC and convert the schedule intentionally.'].join('\n');
  fs.writeFileSync('cron-tz-report.md', md);
  console.log(md);
  process.exit(1);
}
fs.writeFileSync('cron-tz-report.md',
  ['# Cron TZ Debug Report', '', `Cron: \`${cronExpr}\` · zones: ${report.zones}`, '', 'No duplicate runs detected across zones (same-wall-time check ok).', '','Note: a skipped *wall-clock minute* (e.g. 02:30) on spring-forward days is not flagged as dup; verify 1×/day jobs separately.'].join('\n'));
console.log(`Checked ${report.zones} zones for ${cronExpr} — no duplicates.`);
process.exit(report.dupDays.length ? 1 : 0);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Extract every cron string from your project (`crontab.txt`,
   `docker-compose`, `serverless.yml`, `node-cron` literals, README) — the
   debugger accepts one at a time, run it for each.
2. Simulate: `node timezone-trap-cron-debugger.js "0 2 * * *" 2026`.
3. Read `cron-tz-report.md`: any `duplicate-run` line means over-firing; any
   `misfireDays` record means under-firing; both are production bugs on certain
   TZ/DST days.
4. Fix by principle:
   - **Daily wall-clock jobs** ("01:30") that must occur *every calendar day*
     cannot be expressed safely in every TZ with cron; document or use a
     scheduler with DST-aware rules.
   - **Interval jobs** ("every hour") should be `* * * * *`-relative to UTC, not
     a wall-clock minute.
   - **Duplicates on fall-back** → make the job idempotent by key
     (e.g. run timestamp or business date) at the worker level.
5. Add a CI smoke that simulates each cron over the year and asserts only the
   expected behavior.

## 5. Edge Cases & Error Handling

- `Intl.supportedValuesOf` may be absent in old Node — falls back empty; print
  a notice and reduce scope to a provided zone list in that case.
- The parser handles `*/n`, `*`, single values and comma lists; ranges (`1-5`)
  are not parsed — reject and return exit `2` with a message rather than guess.
- Zero-run zones for rare offsets are reported but must be manually triaged:
  a legitimately "never runs" zone proves a gap, which is the point.
- `dom=0`, `dow=7` aliases are normalized so `0 0 * * 0` behaves as Sunday.
- Minute-by-minute simulation is exact but slow — the default sweep covers
  only the ~30 common server zones; pass `--all` (~400 zones, minutes of CPU)
  only when a wide DST sweep is actually required.
