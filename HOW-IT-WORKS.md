# Meeting Room Conflict Checker

## What does it do?

Every weekday afternoon at 4:30pm, this automation checks the SOLVD meeting room calendar for the **next business day**. If any meetings overlap (two bookings at the same time), it sends an email listing each conflicting pair.

If there are no conflicts, no email is sent.

---

## What does the email look like?

**From:** Meeting Room Bookings  
**Subject:** Meeting room booking conflicts Thursday 26 June 2026

**Body:**

> The following meetings conflict in the meeting room on Thursday 26 June 2026:
>
> **CONFLICT 1 OF 2**  
> 9:00am – 10:00am | Team Sync [INTERNAL]  
> Organiser: Sarah Chen (booked first)  
>  
> overlaps with  
>  
> 9:30am – 11:00am | Client Call — Acme Corp [CLIENT]  
> Organiser: James Liu  
>
> Please resolve these conflicts before the day starts.

Each conflict card shows:
- Both meetings with their times, title, and whether they're **Internal** (all solvdagency.com.au attendees) or **Client** (external attendees present)
- The **Organiser** of each meeting
- Which meeting was **(booked first)** based on when it was created in the calendar

---

## How does it work?

There are three parts:

### 1. The script (`check_meetings.py`)
A Python script that does the following:
- Logs into Google using a service account (like a robot Google account)
- Checks what the next business day is, skipping weekends and Australian public holidays
- Pulls that day's events from the meeting room calendar
- Checks every pair of meetings to see if any overlap in time
- If it finds conflicts, it sends an email with the details

### 2. The schedule (GitHub Actions)
The script doesn't run on anyone's computer. It runs on GitHub's servers (free) using a feature called GitHub Actions. Two cron entries cover daylight saving time — one for AEDT (October–April), one for AEST (April–October). Only the one that lands in the 4pm hour runs; the other exits immediately.

### 3. The Google service account
A service account is like a robot user in Google. It has permission to:
- **Read** the meeting room calendar
- **Read** the Australian public holidays calendar
- **Send emails** on behalf of maddisong@solvdagency.com.au

It can't do anything else — it only has those permissions.

---

## Where does everything live?

| What | Where |
|------|-------|
| The script | GitHub repo: `solvdmaddisong/meeting-room-notifier` > `check_meetings.py` |
| The schedule | GitHub repo: `.github/workflows/daily_check.yml` |
| The service account credentials | GitHub repo: Settings > Secrets > `GOOGLE_SA_CREDENTIALS_B64` |
| The configuration (calendar ID, email, etc.) | GitHub repo: Settings > Secrets and variables > Actions > Variables tab |
| The Google Cloud project | [console.cloud.google.com](https://console.cloud.google.com) > project `meeting-room-notifier` |
| The delegation permissions | [admin.google.com](https://admin.google.com) > Security > API controls > Domain Wide Delegation |

---

## Which calendar does it check?

It checks **SOLVD-1-Meeting Room (20)** — the large meeting room.

It picks up meetings booked in two ways:
1. Someone selected the room using the "Rooms" feature in Google Calendar
2. Someone added `meeting@solvdagency.com.au` as an attendee

---

## How does it detect overlaps?

It compares every pair of meetings. Two meetings overlap when one starts before the other ends. Back-to-back meetings (one ends at 2pm, the next starts at 2pm) are **not** flagged as a conflict.

---

## How does it know which meeting was booked first?

Each Google Calendar event stores the timestamp when it was created. The script compares these timestamps and marks the earlier one as "(booked first)".

---

## How does it know if a meeting is Internal or Client?

It looks at the attendee list:
- **Internal** — every attendee has a `@solvdagency.com.au` email
- **Client** — at least one attendee has an email from a different domain

---

## What if I need to change something?

| I want to... | Do this |
|--------------|---------|
| Change who gets the email | Update the `NOTIFY_EMAIL` variable in GitHub repo Settings > Variables |
| Change the time it runs | Edit `.github/workflows/daily_check.yml` and update both cron lines |
| Stop it temporarily | Go to GitHub repo > Actions > Meeting Room Check > click the "..." menu > Disable workflow |
| Check if it ran today | Go to GitHub repo > Actions tab — you'll see a list of all runs with green (success) or red (error) |
| Run it manually right now | Go to GitHub repo > Actions > Meeting Room Check > Run workflow |

---

## Timing note

Two cron entries handle daylight saving automatically:
- **05:30 UTC** fires at 4:30pm AEDT (October–April, UTC+11)
- **06:30 UTC** fires at 4:30pm AEST (April–October, UTC+10)

The script checks the current Sydney hour and exits immediately if it's not the 4pm hour, so only the correct cron does anything.

---

## Cost

This is completely free:
- **Google Cloud** — free tier (no billing needed for this usage)
- **GitHub Actions** — free tier gives 2,000 minutes/month. This script takes about 10 seconds per run. Two cron entries fire per weekday, but the off-season one exits in under a second — total usage is roughly 5 minutes per month
