# Calls Answered Bug Fix — 2026-07-25

## Problem

`sheet_calls_answered` was 215 (all-time) after the backfill run. This only captured April 2026 (211, from Totals row) and July 2026 (4, from Totals row). The February and March sheets use an older template whose Totals row does not aggregate Calls Answered — but the column exists per-row in both sheets and was never summed.

## Fix: Per-Row Sums

### February 2026 (30 rows)
| Date | Calls Answered |
|---|---|
| 11/17/25 | 10 |
| 11/18/25 | 4 |
| 11/19/25 | 11 |
| 11/20/25 | 12 |
| 11/25/25 (AM) | 6 |
| 11/25/25 (PM) | 8 |
| 12/04/25 | 20 |
| 12/05/25 | 17 |
| 12/15/25 | 11 |
| 12/16/25 | 9 |
| 12/17/25 | 11 |
| 12/18/25 | 6 |
| 12/20/25 | 5 |
| 01/19/26 | 3 |
| 02/02/26 | 1 |
| 02/04/26 | 2 |
| 02/05/26 | 1 |
| 02/07/26 | 2 |
| 02/11/26 | 6 |
| 02/13/26 | 1 |
| 02/16/26 | 7 |
| 02/17/26 | 3 |
| 02/18/26 | 10 |
| 02/19/26 | 4 |
| 02/20/26 | 3 |
| 02/23/26 | 6 |
| 02/24/26 | 5 |
| 02/25/26 | 7 |
| 02/26/26 | 6 |
| 02/27/26 | 5 |
| **Total** | **202** |

### March 2026 (20 rows)
| Date | Calls Answered |
|---|---|
| 03/02/26 | 10 |
| 03/03/26 | 7 |
| 03/05/26 (session 1) | 8 |
| 03/05/26 (session 2) | 7 |
| 03/06/26 | 13 |
| 03/09/26 | 11 |
| 03/10/26 | 3 |
| 03/11/26 | 7 |
| 03/12/26 | 4 |
| 03/13/26 | 10 |
| 03/16/26 | 6 |
| 03/17/26 | 6 |
| 03/18/26 | 4 |
| 03/19/26 | 2 |
| 03/23/26 | 5 |
| 03/24/26 | 4 |
| 03/26/26 | 6 |
| 03/27/26 | 10 |
| 03/30/26 | 6 |
| 03/31/26 | 7 |
| **Total** | **136** |

## Corrected All-Time Total

| Sheet | Source | Calls Answered |
|---|---|---|
| February 2026 | Per-row sum | 202 |
| March 2026 | Per-row sum | 136 |
| April 2026 | Totals row | 211 |
| July 2026 | Totals row | 4 |
| **ALL-TIME** | | **553** |

**Before:** 215 → **After:** 553

## Period Buckets

30d and 7d unchanged at 4 (only July rows fall within those windows).

## Stats Written

`update_os_stats` called with `calls_answered=553`, `calls_answered_30d=4`, `calls_answered_7d=4`.
