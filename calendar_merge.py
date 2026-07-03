def merge_room_and_meeting_events(room_events, meeting_events):
    """Combine the room-resource calendar's events with the meeting@ calendar's
    events, treating two entries as the same real-world booking if either their
    `id` or their `iCalUID` matches — a meeting with the room resource, meeting@,
    or both attached should only be counted once."""
    merged = list(room_events)
    seen_ids = {e["id"] for e in merged}
    seen_uids = {e["iCalUID"] for e in merged if e.get("iCalUID")}

    for evt in meeting_events:
        if evt.get("status") == "cancelled":
            continue
        if evt["id"] in seen_ids or evt.get("iCalUID") in seen_uids:
            continue
        merged.append(evt)
        seen_ids.add(evt["id"])
        if evt.get("iCalUID"):
            seen_uids.add(evt["iCalUID"])

    merged.sort(key=lambda e: e["start"].get("dateTime", e["start"].get("date", "")))
    return merged


def room_has_accepted(event, meeting_email=None):
    """Return True unless this looks like an orphaned ghost booking.

    A resource-calendar copy of a real invite has the room listed among
    `attendees`, so we can check its responseStatus there. But a leftover
    ghost — where the room ended up organising an empty copy of a meeting
    that has since moved on to a human organiser (e.g. after being re-invited
    via meeting@) — has no resource `attendees` entry to check, since the
    room's role is "organizer", not "attendee". The earlier blanket rule
    (reject anything the room organises) was too broad and rejected genuine
    room-organised bookings that still had real people on them; the signal
    that actually distinguishes a ghost is having NO human attendees at all.
    """
    organizer_email = event.get("organizer", {}).get("email", "")
    attendees = event.get("attendees", [])

    def is_resource_or_meeting_address(email):
        return email.endswith("@resource.calendar.google.com") or email == meeting_email

    human_attendees = [
        a for a in attendees
        if not is_resource_or_meeting_address(a.get("email", ""))
    ]
    if is_resource_or_meeting_address(organizer_email) and not human_attendees:
        return False

    resource_attendees = [
        a for a in attendees
        if a.get("email", "").endswith("@resource.calendar.google.com")
    ]
    if not resource_attendees:
        return True
    return any(a.get("responseStatus") == "accepted" for a in resource_attendees)
