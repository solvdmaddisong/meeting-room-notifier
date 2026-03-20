# Meeting Room Booking Notifier

## What does it do?

Every weekday morning at 8:45am, this automation checks the SOLVD meeting room calendar. If there are any meetings that day with **external people** (anyone outside of solvdagency.com.au), it sends you an email listing those meetings with their times.

If there are no external meetings that day, no email is sent.

---

## What does the email look like?

**From:** Meeting Room Bookings
**Subject:** Meeting room bookings today Friday 20 March 2026

**Body:**

> Meeting room bookings today Friday 20 March 2026
>
> **8:30am - 9:30am** | Valuations Conference — Brand Naming
>
> **2:00pm - 3:00pm** | Client Presentation

---

## How does it work?

There are three parts:

### 1. The script (`check_meetings.py`)
A Python script that does the following:
- Logs into Google using a service account (like a robot Google account)
- Pulls today's events from the meeting room calendar
- Checks each event's attendee list for anyone with an email address that isn't @solvdagency.com.au
- If it finds any, it sends you an email with the meeting times and names

### 2. The schedule (GitHub Actions)
The script doesn't run on anyone's computer. It runs on GitHub's servers (free) using a feature called GitHub Actions. A small config file tells GitHub: "Run this script at 8:45am every weekday."

### 3. The Google service account
A service account is like a robot user in Google. It has permission to:
- **Read** the meeting room calendar
- **Send emails** on behalf of maddisong@solvdagency.com.au

It can't do anything else — it only has those two permissions.

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

## How does it decide if a meeting is "external"?

It looks at the attendee list for each meeting. If any attendee has an email that does NOT end in `@solvdagency.com.au`, that meeting is considered external. It ignores the room's own calendar address.

---

## What if I need to change something?

| I want to... | Do this |
|--------------|---------|
| Change who gets the email | Update the `NOTIFY_EMAIL` variable in GitHub repo Settings > Variables |
| Change the time it runs | Edit `.github/workflows/daily_check.yml` and change the cron line |
| Stop it temporarily | Go to GitHub repo > Actions > Meeting Room Check > click the "..." menu > Disable workflow |
| Check if it ran today | Go to GitHub repo > Actions tab — you'll see a list of all runs with green (success) or red (error) |
| Run it manually right now | Go to GitHub repo > Actions > Meeting Room Check > Run workflow |

---

## Timing note

The schedule is set for 8:45am during daylight saving time (AEDT, October to April). During standard time (AEST, April to October), it will arrive at 7:45am instead — one hour early. This is intentional since early is better than late for a morning heads-up.

---

## Cost

This is completely free:
- **Google Cloud** — free tier (no billing needed for this usage)
- **GitHub Actions** — free tier gives 2,000 minutes/month. This script takes about 10 seconds per run, so it uses roughly 3 minutes per month
