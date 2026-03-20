import os
import json
import base64
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr

import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Configuration (all values come from environment variables)
# ---------------------------------------------------------------------------
CALENDAR_ID = os.environ["CALENDAR_ID"]
MEETING_EMAIL = os.environ.get("MEETING_EMAIL", "meeting@solvdagency.com.au")
COMPANY_DOMAIN = os.environ["COMPANY_DOMAIN"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
DELEGATE_EMAIL = os.environ["DELEGATE_EMAIL"]
TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

# ---------------------------------------------------------------------------
# Authenticate with a service account using domain-wide delegation
# ---------------------------------------------------------------------------
sa_info = json.loads(base64.b64decode(os.environ["GOOGLE_SA_CREDENTIALS_B64"]))
credentials = service_account.Credentials.from_service_account_info(
    sa_info, scopes=SCOPES
)
delegated = credentials.with_subject(DELEGATE_EMAIL)

# ---------------------------------------------------------------------------
# Build the day's time window (midnight to 23:59 in the configured timezone)
# ---------------------------------------------------------------------------
tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)
start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

# ---------------------------------------------------------------------------
# Fetch today's events from the meeting room resource calendar
# ---------------------------------------------------------------------------
cal_service = build("calendar", "v3", credentials=delegated)

events_result = cal_service.events().list(
    calendarId=CALENDAR_ID,
    timeMin=start_of_day,
    timeMax=end_of_day,
    singleEvents=True,
    orderBy="startTime",
).execute()
events = events_result.get("items", [])

# Also check the meeting@ calendar to catch bookings made by adding the
# email directly (rather than selecting the room resource).
try:
    meeting_result = cal_service.events().list(
        calendarId=MEETING_EMAIL,
        timeMin=start_of_day,
        timeMax=end_of_day,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    existing_ids = {e["id"] for e in events}
    for evt in meeting_result.get("items", []):
        if evt["id"] not in existing_ids:
            events.append(evt)
    events.sort(key=lambda e: e["start"].get("dateTime", e["start"].get("date", "")))
except Exception:
    # meeting@ calendar may not be accessible — resource calendar is primary
    pass

# ---------------------------------------------------------------------------
# Exit silently if no bookings today
# ---------------------------------------------------------------------------
if not events:
    print("No meeting room bookings today.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Format the notification
# ---------------------------------------------------------------------------
today_str = now.strftime("%A %-d %B %Y")  # e.g. "Friday 20 March 2026"

# Filter to only meetings with external attendees
external_events = []
for event in events:
    attendees = event.get("attendees", [])
    has_external = any(
        not a["email"].endswith(f"@{COMPANY_DOMAIN}")
        and not a["email"].endswith("@resource.calendar.google.com")
        for a in attendees
    )
    if has_external:
        external_events.append(event)

if not external_events:
    print("No external meetings today.")
    raise SystemExit(0)

# Build HTML email
html_lines = [f"<p>Meeting room bookings today {today_str}</p>"]

for event in external_events:
    summary = event.get("summary", "(No title)")
    start_dt = datetime.fromisoformat(event["start"]["dateTime"])
    end_dt = datetime.fromisoformat(event["end"]["dateTime"])
    start_time = start_dt.strftime("%-I:%M%p").lower()
    end_time = end_dt.strftime("%-I:%M%p").lower()
    html_lines.append(f"<p><b>{start_time} - {end_time}</b> | {summary}</p><br>")

html_body = "\n".join(html_lines)

# Plain text for logging
for event in external_events:
    summary = event.get("summary", "(No title)")
    start_dt = datetime.fromisoformat(event["start"]["dateTime"])
    end_dt = datetime.fromisoformat(event["end"]["dateTime"])
    start_time = start_dt.strftime("%-I:%M%p").lower()
    end_time = end_dt.strftime("%-I:%M%p").lower()
    print(f"  {start_time} - {end_time} | {summary}")

# ---------------------------------------------------------------------------
# Send email via Gmail API
# ---------------------------------------------------------------------------
gmail_service = build("gmail", "v1", credentials=delegated)

message = MIMEText(html_body, "html")
message["from"] = formataddr(("Meeting Room Bookings", DELEGATE_EMAIL))
message["to"] = NOTIFY_EMAIL
message["subject"] = f"Meeting room bookings today {today_str}"
raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

gmail_service.users().messages().send(
    userId="me", body={"raw": raw}
).execute()

print(f"\nEmail sent to {NOTIFY_EMAIL}")
