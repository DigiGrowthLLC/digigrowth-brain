# Morning Briefing — Tuesday, November 24

## Emails

- **Chelsea Murphy (Pinnacle Physical Therapy)** *(dylanrg@)* — Re: One quick permission on the Pinnacle ad account · Chelsea wrote yesterday at `3:39 PM` that she thinks the Meta ad account permission is fixed and confirmed **Monday, Nov 30** works for launch (Brian cc'd). You replied at `10:38 PM` confirming full control and locking in the **Nov 30** launch. No reply pending.
- **Retell** *(dylanrg@)* — [Action required] Update your Retell API integration (`4` notices) · Retell has removed endpoints that requests from your workspace's "Secret Key" were still calling, and those requests are now failing: `POST /v2/list-calls` → `/v3/list-calls` (`4` requests), `GET /list-agents` → `POST /v2/list-agents` (`4`), `GET /get-agent-versions` → `/list-agent-versions` (`2`), and `POST /v2/create-web-call` → v3 web client (`1`). Last use came from IP `153.33.93.32` on `11/19`–`11/22`. *None of these endpoints appear in the digigrowth-brain code, so the calls likely came from local scripts or curl.* **[ACTION]**
- *Only the dylanrg@digigrowthllc.com inbox returned results from this session. No other business emails came in during the last 24 hours.*

## Domain Health

- `digigrowthllc.com`: DMARC pass `99%` of `339` msgs (*Postmark, Nov 15–22*). **Unknown source: `cloud-sec-av.com`** (`35.174.145.124`) sent `1` message as the domain with SPF and DKIM both failing. Google: `2` of `73` messages in its "more IPs" group were not aligned. `2` forwarded messages (titan.email, ace-host.net) passed on DKIM.

*Full detail in OS → Email Identities → Domain Health.*

## Schedule

- `11:00 AM` **Discount Tire Shift** — *7h*

Committed: `7h 0m` · Free: `6h 0m` *(`7:00–11:00 AM` and `6:00–8:00 PM`)*

## Outreach This Week

**Cold calling (Drive tracker):** No cold calling tracker found in Drive. If a separate file tracks calls made or contacts reached, confirm the file name.

**SMS (OS, last 7 days, snapshot exported `11/23`):** `148` messages sent · reply rate `27.3%` · interested rate `4.5%` (`7` interested) · booked `1` (ABR `0.6%`)
- All-time: `3,773` messages sent · reply rate `35.9%` · `24` booked
- Last 30 days, for context: `1,047` messages sent · booked `3`

*Fetch note: this briefing ran at `5:04 AM`, before today's `5:50 AM` export, so these are yesterday's numbers. The live fetch from Railway returned nothing, because the sandbox's egress proxy blocked it.*

## Yesterday's Performance

*Monday `11/23` compared with the prior week (`11/16` and `11/19`).*

**Wins yesterday:**
- **7am Wake Up**: `TRUE`. *First time logged this month (`0/2` the prior week).*
- **W?**: `TRUE`. *`0/2` the prior week.*
- **SMS & Email**: `TRUE`. *`1/2` the prior week.*
- **Score**: `6/10`. *Hit the goal of `6` (prior week: `6`).*

*Also done: MR, Systems Building, Gym, Healthy Diet, Dopamine Reg, NTR (each `1/2` or better the prior week).*

**Focus today:**
- **HLT**: `FALSE` → target: `TRUE` *(logged on `11/16`)*

## Sales This Week

- **Shows**: `0` *(vs. `15` all-time)*
- **Closes**: `0` *(vs. `1` all-time)*
- **Discovery calls**: `0` *(vs. `25` all-time)*
- **Revenue**: `$0` *(vs. `$0` all-time)*

*The sales tracker hasn't changed since `9/25`, so the diff against the `11/17` snapshot is zero.*

**Follow-up candidates:** none. Every showed row in the sales tracker is marked Lost or Won. *(This cloud session can't reach `crm_list_followups`, so the dialer's manual follow-up list was not checked.)*

*Snapshot: shows=15, closes=1, discovery_calls=25, total_revenue=0*

## How to Use Your Day

- `7:00–11:00 AM` open *(4h)* before your shift. One option is to work through Pinnacle's remaining pre-launch setup, now that the ad account is shared and launch is set for **Mon, Nov 30**.
- Another option in that block: the open SMS conversations (`7` interested in the last 7 days, `1` booked).
- `6:00–8:00 PM` open *(2h)*. One option is to find which local script is calling the removed Retell endpoints (IP `153.33.93.32`). Another is to log recent discovery calls in the Sales Performance Tracker, which hasn't changed since `9/25`.

*Daily briefing — Tuesday, November 24*
