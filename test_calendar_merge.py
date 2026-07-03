from calendar_merge import merge_room_and_meeting_events, room_has_accepted


def make_event(event_id, ical_uid, start="2026-07-06T10:00:00+10:00"):
    return {
        "id": event_id,
        "iCalUID": ical_uid,
        "status": "confirmed",
        "start": {"dateTime": start},
        "end": {"dateTime": "2026-07-06T11:00:00+10:00"},
    }


def old_id_only_merge(room_events, meeting_events):
    """Reproduces the pre-fix logic from check_meetings.py for comparison."""
    merged = list(room_events)
    existing_ids = {e["id"] for e in merged}
    for evt in meeting_events:
        if evt.get("status") == "cancelled":
            continue
        if evt["id"] not in existing_ids:
            merged.append(evt)
    return merged


def test_old_logic_double_counts_when_ids_differ_across_calendars():
    # Same real meeting: room resource copy has one `id`, the meeting@ copy of
    # the exact same invite comes back from Google with a different `id` but
    # the same iCalUID. The old id-only dedup fails to recognise this.
    room_copy = make_event(event_id="room-copy-abc", ical_uid="shared-uid@google.com")
    meeting_copy = make_event(event_id="meeting-copy-xyz", ical_uid="shared-uid@google.com")

    result = old_id_only_merge([room_copy], [meeting_copy])

    assert len(result) == 2, "documents the bug: same booking counted twice"


def test_merge_collapses_room_and_meeting_copies_of_the_same_event():
    room_copy = make_event(event_id="room-copy-abc", ical_uid="shared-uid@google.com")
    meeting_copy = make_event(event_id="meeting-copy-xyz", ical_uid="shared-uid@google.com")

    result = merge_room_and_meeting_events([room_copy], [meeting_copy])

    assert len(result) == 1, "room + meeting@ on the same event must count once"


def test_merge_keeps_genuinely_separate_bookings():
    room_booking = make_event(event_id="room-1", ical_uid="uid-1@google.com")
    tv_only_booking = make_event(
        event_id="meeting-2", ical_uid="uid-2@google.com",
        start="2026-07-06T14:00:00+10:00",
    )

    result = merge_room_and_meeting_events([room_booking], [tv_only_booking])

    assert len(result) == 2, "distinct real bookings must not be merged away"


def test_merge_skips_cancelled_meeting_copy():
    room_copy = make_event(event_id="room-copy-abc", ical_uid="shared-uid@google.com")
    cancelled = make_event(event_id="meeting-copy-xyz", ical_uid="other-uid@google.com")
    cancelled["status"] = "cancelled"

    result = merge_room_and_meeting_events([room_copy], [cancelled])

    assert len(result) == 1


def test_orphaned_room_organised_ghost_with_no_attendees_is_rejected():
    # Reproduces the "Weekly Consultant WIP" ghost from the 2026-07-03 test run:
    # the room ended up organising its own stale copy of a meeting that has
    # since moved to a human organiser, with nobody left on the invite.
    ghost = {
        "organizer": {"email": "c_abc123@resource.calendar.google.com"},
        "attendees": [],
    }
    assert room_has_accepted(ghost) is False


def test_room_organised_event_with_real_attendees_is_not_rejected():
    # Guards against reintroducing the "too broad" bug from f87eccd: a
    # legitimate booking the room organises for itself, but with real people
    # actually invited, must still be treated as a genuine booking.
    legit = {
        "organizer": {"email": "c_abc123@resource.calendar.google.com"},
        "attendees": [
            {"email": "georgiab@solvdagency.com.au", "responseStatus": "accepted"},
        ],
    }
    assert room_has_accepted(legit) is True


def test_human_organised_event_with_pending_room_invite_still_checked_normally():
    pending = {
        "organizer": {"email": "georgiab@solvdagency.com.au"},
        "attendees": [
            {"email": "georgiab@solvdagency.com.au"},
            {"email": "c_abc123@resource.calendar.google.com", "responseStatus": "needsAction"},
        ],
    }
    assert room_has_accepted(pending) is False


def test_human_organised_event_with_no_room_invite_at_all_passes():
    no_room = {
        "organizer": {"email": "georgiab@solvdagency.com.au"},
        "attendees": [{"email": "georgiab@solvdagency.com.au"}],
    }
    assert room_has_accepted(no_room) is True


if __name__ == "__main__":
    test_old_logic_double_counts_when_ids_differ_across_calendars()
    test_merge_collapses_room_and_meeting_copies_of_the_same_event()
    test_merge_keeps_genuinely_separate_bookings()
    test_merge_skips_cancelled_meeting_copy()
    test_orphaned_room_organised_ghost_with_no_attendees_is_rejected()
    test_room_organised_event_with_real_attendees_is_not_rejected()
    test_human_organised_event_with_pending_room_invite_still_checked_normally()
    test_human_organised_event_with_no_room_invite_at_all_passes()
    print("All tests passed.")
