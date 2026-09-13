---
name: Cron Schedule Parser
description: Translate natural language time rules into valid 5-part or 6-part Cron schedule expressions.
metadata:
  source: skills/cron-schedule-parser/cron-schedule-parser.md
---

# Cron Schedule Parser

## Prerequisites & Dependencies

- Python 3.10+ (for cron expression parsing)
- No external runtime dependencies; pure-Python cron library optional

## Execution Steps

1. **Identify the cron expression format**: Determine if the input is a standard 5-part cron (minute hour day month weekday) or 6-part format (including seconds).

2. **Parse the cron expression**: Use a cron library or manual parsing to extract the five (or six) time fields: minute, hour, day-of-month, month, day-of-week.

3. **Convert to cron format**: If the input is in natural language (e.g., "every hour", "first Monday of the month"), translate it into the standard cron five-part format.

4. **Validate the cron expression**: Check that the parsed values are valid (e.g., minute 0-59, hour 0-23, day-of-month 1-31, month 1-12, weekday 0-6).

5. **Output the cron schedule**: Produce the cron expression string that can be used in crontab files or scripts.

6. **Example outputs**:
   - "Every hour" → `0 * * * *`
   - "Daily at 8am" → `0 8 * * *`
   - "First Monday of every month" → `0 0 * * 1`
   - "Every 15 minutes" → `*/15 * * * *`

```bash
npm i node-cron
```

```python
import croniter
from datetime import datetime

base = datetime.now()
schedule = croniter.croniter('0 * * * *', base)
next_time = schedule.get_next(datetime)
```

## CLI Usage

```bash
cron-schedule-parser "every hour"
# Output: 0 * * * *
```
