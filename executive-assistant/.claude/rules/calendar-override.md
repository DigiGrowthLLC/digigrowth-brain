# Calendar Override — Auto-Write Rule

When Dylan describes a temporary change to his daily schedule — different block order, different start time, skipping blocks, or any variation from the default — immediately write it to:

`.claude/skills/calendar-management/schedule-override.md`

Do this without being asked. Do not confirm first, do not explain the format — just write the file and confirm it's set.

## What counts as a temporary schedule change

- A different block order ("growth before MDR")
- A different start time ("start at 8:30 instead of 6:30")
- Skipping blocks ("no outreach this week")
- A reduced or expanded block set ("just morning routine, gym, and MDR")
- Any of the above scoped to a date range ("until Friday", "this week", "June 6–9")

## What to write

Fill in the four fields using the information Dylan provided:

```
from: YYYY-MM-DD
to: YYYY-MM-DD
start: HH:MM
blocks: Block → Block → Block
```

- `from`: today's date if no start date is given
- `to`: the end date Dylan specified (convert relative like "until Friday" or "till June 9th" to an absolute date)
- `start`: the start time Dylan specified, or the default (06:30) if not mentioned
- `blocks`: the ordered list using canonical names — `Morning Routine`, `Admin`, `Outreach`, `MDR`, `Meal Prep`, `Growth`, `Gym`
