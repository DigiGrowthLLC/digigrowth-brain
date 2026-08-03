# Sheets Digest — 2026-07-25 (Historical Backfill)

**Run type:** One-time backfill — all historical cold calling sheets, resonations field populated for first time.

## Sheets Included

| Sheet | File ID | Calls | Calls Answered | Pitches (Contacts) | Resonations | Calls Booked |
|---|---|---|---|---|---|---|
| February 2026 Cold Calling Metrics | 1aiGiWDYMtx14IdP2nWL384iX_5_QrRhyk5d_2MNDr8U | 1,459 | — (col n/a) | 85 | 8 | 1 |
| March 2026 Cold Calling Metrics | 1m7kcoD7b3vcCmNeEkD7o4oBOAhrg4-rlb1mFT2Gf4QM | 924 | — (col n/a) | 78 | 4 | 8 |
| April 2026 Cold Calling Metrics | 1rk2Z5gzLz_eV2SU68bybiKvmzzsURGHvZZ7z3rKDkuY | 1,344 | 211 | 124 | 15 | 6 |
| July 2026 Cold Calling Metrics | 18SUNgfnGY6eBHtELYbvE5kVnOR_xoQasNpTF6fcmLaU | 30 | 4 | 1 | 0 | 0 |
| **ALL-TIME TOTAL** | | **3,757** | **215** | **288** | **27** | **15** |

*Note: Feb and Mar sheets predate the "Calls Answered" column — only Apr and Jul have it. All-time calls_answered = 211 + 4 = 215.*

*Note: appointments_booked all-time corrected to 15 (sum of Calls Booked from all 4 cold calling sheets' Totals rows), separate from the Sales Performance Tracker's 18 discovery calls booked.*

## Sales Performance Tracker

- Discovery calls booked: 18 · Shows: 9 · Closes: 0 · Revenue: $0

## Period Buckets (today = 2026-07-25)

**7-day (Jul 18–25) and 30-day (Jun 25–Jul 25):** Only Jul 20 and Jul 21 rows qualify for both windows.

| Metric | 7d | 30d |
|---|---|---|
| Calls made | 30 | 30 |
| Calls answered | 4 | 4 |
| Contacts reached | 1 | 1 |
| Resonations | 0 | 0 |
| Appointments booked | 0 | 0 |

## Stats Written to OS

| Field | Value |
|---|---|
| calls_made (all-time) | 3,757 |
| calls_answered (all-time) | 215 |
| contacts_reached (all-time) | 288 |
| resonations (all-time) | **27** ← new field, first backfill |
| appointments_booked (all-time) | 15 |
| shows | 9 |
| closes | 0 |
| discovery_calls | 18 |
| total_revenue | $0 |
| [all 30d/7d variants] | see table above |

## Notes

- `drive_search` used (not `drive_list_recent`) to find all sheets matching the pattern — confirmed 4 sheets total across Feb, Mar, Apr, Jul 2026. No May or June sheet exists in Drive.
- Totals rows used as source of truth for all metrics per instructions. No per-row re-summation was needed — all Totals rows were present and complete.
- Resonations field now populated in the OS Analytics panel for all historical periods.
