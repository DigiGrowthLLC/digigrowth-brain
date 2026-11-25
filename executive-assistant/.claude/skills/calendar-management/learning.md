# Self-Learning: How Dylan Reschedules

The planner learns Dylan's scheduling style from **what he changes on his calendar after a run**. Every run saves what it planned (a snapshot), and the next run compares that snapshot to the real calendar. Changes that repeat become rules automatically.

Files (all in this folder):
- `learning/plans/<YYYY-MM-DD>-<HHMM>.json`: one snapshot per run (Step 4 writes it)
- `learning/observations.md`: every change seen, grouped into patterns with a count
- Promoted rules go into `school-and-work.md` → "Learned preferences" (small rules) or straight into `SKILL.md` (day shape, MDR/Gym/Meal Prep rules, block sizes) when they replace an existing rule

---

## 1. Save a snapshot (end of Step 4, every run)

After the calendar check, write `learning/plans/<date>-<HHMM of run>.json`:

```json
{
  "date": "2026-11-17",
  "run_at": "2026-11-17T10:43",
  "reviewed": false,
  "answers": "his Step 0B answer, one line",
  "blocks": [
    {"id": "<event id>", "title": "Study: MAR 3023 Exam 4", "kind": "test_study",
     "start": "10:45", "end": "12:45", "color": "10"}
  ],
  "fixed": [{"title": "Haircut", "start": "13:00", "end": "13:30"}]
}
```

`kind` is one of `must_do, test_study, assignment, service_delivery, todo, outreach, mdr, gym, meal_prep, groceries`.

## 2. Review earlier plans (start of Step 0A, every run)

For every snapshot with `"reviewed": false` (past days and earlier runs today), list that day's calendar and match each block **by event id**:

| What he did | How to read it |
|---|---|
| **Moved** a block (start changed) | Placement preference: which kind he wants earlier/later, or before/after which other kind |
| **Resized** it | Size preference for that kind (e.g. MDR 45 min, not 30) |
| **Deleted** it | Unwanted on that kind of day, **unless** it was school and Canvas now shows it submitted (that means done, not a preference), or a re-run replaced it |
| **Retitled / split** it | Naming or splitting preference (e.g. "Groceries + Meal Prep" → two separate blocks) |
| **Added his own event** (no `Planned by morning planner`, created after `run_at`) | Something the planner should have booked: what, how long, and where it sits |
| Unchanged | **Proves nothing.** He doesn't always fix the calendar to match reality. Never learn from it |

Ignore changes to shifts, classes, meetings and other fixed events.

For each change, write the **pattern**, not the one-off. Bad: "Boulder SD moved to 11:00 on 11/17". Good: "business blocks before school in the morning". Then add it to `observations.md`: new pattern → new line with count 1; same pattern as an existing line → bump its count and add the date. If he says *why* in chat, record his words.

Set `"reviewed": true` on the snapshot when done. Delete snapshots older than 30 days.

## 3. Promote to a rule

- **Count reaches 2** (two different days), **or Dylan states it in chat once** → promote it. Write it where it belongs (see Files), dated, with "(learned from calendar edits)" or "(Dylan said)". Mark it `PROMOTED` in `observations.md`.
- **Contradicts an existing rule** → edit that rule instead of stacking a new one on top. Newest evidence wins.
- **Context-dependent** (only on shift days, only weekends, only when there's a test) → write the condition into the rule.
- **One-off** (count 1, no repeat in 14 days) → leave it in observations; never act on it.

## 4. Tell him (in the Step 0B snapshot)

One line per thing that changed since the last run, so he can veto:

> 🧠 Learned from your edits: MDR stays 45 min (you stretched it twice). Say "undo" to drop it.

An "undo" means remove the rule, mark the pattern `REJECTED` in `observations.md`, and never promote it again unless he asks.
