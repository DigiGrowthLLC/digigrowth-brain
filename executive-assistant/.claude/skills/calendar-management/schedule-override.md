# Schedule Override

Set this file to temporarily change how your days are scheduled. The calendar management skill checks it every night before building tomorrow's schedule. When the `to` date passes, the override is automatically ignored — no cleanup needed.

To activate an override, fill in the fields below. To deactivate early, clear the fields or delete this file.

---

from: 2026-06-06
to: 2026-06-09
start: 08:30
blocks: Morning Routine → Growth → Gym → MDR

---

## Example

```
from: 2026-06-06
to: 2026-06-09
start: 08:30
blocks: Morning Routine → Growth → MDR → Gym
```

**`from` / `to`** — date range (YYYY-MM-DD, inclusive)  
**`start`** — what time the first block begins (24h format)  
**`blocks`** — ordered list of blocks to schedule, using canonical names: `Morning Routine`, `Admin`, `Outreach`, `MDR`, `Meal Prep`, `Growth`, `Gym`

Durations, minimums, and colors still follow the block reference table. Omitted blocks are simply not scheduled.
