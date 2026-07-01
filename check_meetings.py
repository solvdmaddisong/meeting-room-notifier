import os
import json
import base64
from datetime import datetime, timedelta
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
HOLIDAYS_CALENDAR = "en.australian#holiday@group.v.calendar.google.com"

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
# Time-window guard — only proceed during the 4pm hour (Sydney local time).
# Two GitHub crons fire daily (05:30 UTC and 06:30 UTC); only the one that
# falls in the 4pm hour for the current DST period should run.
# ---------------------------------------------------------------------------
tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)
is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
if not is_manual and now.hour != 16:
    print(f"Outside expected time window (Sydney hour: {now.hour:02d}). Exiting.")
    raise SystemExit(0)

cal_service = build("calendar", "v3", credentials=delegated)

# ---------------------------------------------------------------------------
# Find the next business day, skipping weekends and Australian public holidays
# ---------------------------------------------------------------------------
def is_public_holiday(date):
    start = tz.localize(datetime(date.year, date.month, date.day, 0, 0, 0))
    end = tz.localize(datetime(date.year, date.month, date.day, 23, 59, 59))
    try:
        result = cal_service.events().list(
            calendarId=HOLIDAYS_CALENDAR,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
        ).execute()
        return len(result.get("items", [])) > 0
    except Exception:
        return False


def get_next_business_day(from_date):
    candidate = from_date + timedelta(days=1)
    while candidate.weekday() >= 5 or is_public_holiday(candidate):
        candidate += timedelta(days=1)
    return candidate


next_day = get_next_business_day(now.date())
next_day_str = datetime(next_day.year, next_day.month, next_day.day).strftime(
    "%A %-d %B %Y"
)

# ---------------------------------------------------------------------------
# Build time window for the next business day
# ---------------------------------------------------------------------------
start_of_day = tz.localize(
    datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0)
).isoformat()
end_of_day = tz.localize(
    datetime(next_day.year, next_day.month, next_day.day, 23, 59, 59)
).isoformat()

# ---------------------------------------------------------------------------
# Fetch events from the meeting room resource calendar
# ---------------------------------------------------------------------------
events_result = cal_service.events().list(
    calendarId=CALENDAR_ID,
    timeMin=start_of_day,
    timeMax=end_of_day,
    singleEvents=True,
    orderBy="startTime",
).execute()
events = [e for e in events_result.get("items", []) if e.get("status") != "cancelled"]


# Exclude all-day events — they don't represent room time slots
events = [e for e in events if "dateTime" in e.get("start", {})]


def room_has_accepted(event):
    """Return True if the resource-calendar attendee has accepted, or if there
    is no resource attendee entry (older-style bookings with no room invite)."""
    resource_attendees = [
        a for a in event.get("attendees", [])
        if a.get("email", "").endswith("@resource.calendar.google.com")
    ]
    if not resource_attendees:
        return True
    return any(a.get("responseStatus") == "accepted" for a in resource_attendees)


events = [e for e in events if room_has_accepted(e)]

if not events:
    print(f"No meeting room bookings for {next_day_str}.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Detect overlapping pairs (strict — back-to-back meetings are not a conflict)
# ---------------------------------------------------------------------------
def parse_times(event):
    return (
        datetime.fromisoformat(event["start"]["dateTime"]),
        datetime.fromisoformat(event["end"]["dateTime"]),
    )


overlapping_pairs = []
for i in range(len(events)):
    for j in range(i + 1, len(events)):
        s1, e1 = parse_times(events[i])
        s2, e2 = parse_times(events[j])
        if s1 < e2 and s2 < e1:
            overlapping_pairs.append((events[i], events[j]))

if not overlapping_pairs:
    print(f"No conflicting bookings for {next_day_str}.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Build HTML email
# ---------------------------------------------------------------------------
def fmt_time(dt):
    return dt.strftime("%-I:%M%p").lower()


def get_meeting_type(event):
    for a in event.get("attendees", []):
        email = a.get("email", "")
        if (
            not email.endswith(f"@{COMPANY_DOMAIN}")
            and not email.endswith("@resource.calendar.google.com")
        ):
            return "client"
    return "internal"


def get_organiser(event):
    org = event.get("organizer", {})
    return org.get("displayName") or org.get("email", "Unknown")


def get_attendees(event):
    names = []
    for a in event.get("attendees", []):
        email = a.get("email", "")
        if email.endswith("@resource.calendar.google.com"):
            continue
        name = a.get("displayName") or email
        names.append(name)
    return names


INTERNAL_BADGE = (
    '<span style="font-size:11px;font-weight:500;padding:2px 7px;border-radius:4px;'
    'background:#F1EFE8;color:#5F5E5A;letter-spacing:0.03em;">INTERNAL</span>'
)
CLIENT_BADGE = (
    '<span style="font-size:11px;font-weight:500;padding:2px 7px;border-radius:4px;'
    'background:#E6F1FB;color:#185FA5;letter-spacing:0.03em;">CLIENT</span>'
)
BOOKED_FIRST_BADGE = (
    '<span style="font-size:11px;font-weight:500;padding:2px 7px;border-radius:4px;'
    'background:#FDECEA;color:#A32D2D;letter-spacing:0.03em;">BOOKED FIRST</span>'
)


def event_row_html(event, booked_first):
    s, e = parse_times(event)
    badge = INTERNAL_BADGE if get_meeting_type(event) == "internal" else CLIENT_BADGE
    organiser = get_organiser(event)
    attendees = get_attendees(event)
    first_badge = f"&nbsp;{BOOKED_FIRST_BADGE}" if booked_first else ""
    title = event.get("summary", "(No title)")
    attendees_lines = "".join(
        f'<div style="font-size:11px;color:#888888;">{a}</div>' for a in attendees
    )
    attendees_html = (
        f'<div style="font-size:11px;color:#888888;margin-top:2px;">Attendees:</div>'
        f"{attendees_lines}"
        if attendees
        else ""
    )
    return (
        f'<div style="margin:0 0 12px;">'
        f'<div style="font-size:12px;font-weight:600;color:#666666;margin:0 0 2px;">'
        f"{fmt_time(s)} – {fmt_time(e)}</div>"
        f'<div style="font-size:14px;color:#111111;font-weight:500;margin:0 0 5px;">'
        f"{title}&nbsp;{badge}{first_badge}</div>"
        f'<div style="font-size:11px;color:#888888;">Organiser: {organiser}</div>'
        f"{attendees_html}"
        f"</div>"
    )


total = len(overlapping_pairs)
cards_html = []
for idx, (ev1, ev2) in enumerate(overlapping_pairs, 1):
    ev1_first = ev1.get("created", "") <= ev2.get("created", "")
    card = (
        f'<div style="background:#fafafa;border:1px solid #e5e5e5;border-left:3px solid #E24B4A;'
        f'border-radius:0 8px 8px 0;padding:14px 16px;margin:0 0 12px;">'
        f'<p style="margin:0 0 10px;font-size:12px;font-weight:700;color:#A32D2D;'
        f'letter-spacing:0.04em;">CONFLICT {idx} OF {total}</p>'
        f"{event_row_html(ev1, ev1_first)}"
        f'<p style="font-size:11px;font-weight:600;color:#E24B4A;letter-spacing:0.04em;'
        f'text-transform:uppercase;margin:0 0 10px;">↕ overlaps with</p>'
        f"{event_row_html(ev2, not ev1_first)}"
        f"</div>"
    )
    cards_html.append(card)

html_body = (
    f'<p style="font-size:15px;color:#111111;margin:0 0 20px;">'
    f"The following meetings conflict in the meeting room on {next_day_str}:</p>"
    + "".join(cards_html)
    + '<p style="font-size:13px;color:#666666;margin:20px 0 0;">'
    "Please resolve these conflicts before the day starts.</p>"
)

subject = f"Meeting room booking conflicts {next_day_str}"

# Plain text for logging
print(f"\n{subject}")
for idx, (ev1, ev2) in enumerate(overlapping_pairs, 1):
    s1, e1 = parse_times(ev1)
    s2, e2 = parse_times(ev2)
    print(f"\nConflict {idx} of {total}:")
    print(f"  {fmt_time(s1)} - {fmt_time(e1)} | {ev1.get('summary', '(No title)')}")
    print("  overlaps with")
    print(f"  {fmt_time(s2)} - {fmt_time(e2)} | {ev2.get('summary', '(No title)')}")

# ---------------------------------------------------------------------------
# Send email via Gmail API
# ---------------------------------------------------------------------------
gmail_service = build("gmail", "v1", credentials=delegated)

message = MIMEText(html_body, "html")
message["from"] = formataddr(("Meeting Room Bookings", DELEGATE_EMAIL))
message["to"] = NOTIFY_EMAIL
message["subject"] = subject
raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()

print(f"\nEmail sent to {NOTIFY_EMAIL}")
