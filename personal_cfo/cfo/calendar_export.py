"""Turn a recommendation into something that lands on an actual calendar.

This is deliberately export, not sync: a downloadable .ics (works with
Apple Calendar, Outlook, Google Calendar import, any app that reads the
standard) plus a zero-auth Google Calendar "quick add" link. Real two-way
sync would mean OAuth credentials, a consent screen, and token storage per
provider -- a much bigger and riskier feature than "let me get this
recommendation onto my calendar," which is what this actually serves.

Uses floating local time (no timezone) in the .ics file -- this is a
single-user, self-hosted app, so the server's clock and the user's clock
are the same clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4


@dataclass
class CalendarEvent:
    title: str
    description: str = ""
    start: datetime = field(default_factory=lambda: (datetime.now() + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    ))
    duration_minutes: int = 30
    reminder_minutes_before: int = 60
    recurrence_monthly_count: int | None = None  # None/<=1 = one-off


def _fold(line: str) -> str:
    """RFC 5545 line folding: continuation lines start with a space, and no
    line (content included) exceeds 75 octets."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts = []
    remaining = line
    while len(remaining.encode("utf-8")) > 75:
        cut = 75
        while len(remaining[:cut].encode("utf-8")) > 75:
            cut -= 1
        parts.append(remaining[:cut])
        remaining = " " + remaining[cut:]
    parts.append(remaining)
    return "\r\n".join(parts)


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _dt(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S")


def build_ics(events: list[CalendarEvent], calendar_name: str = "Personal CFO") -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personal CFO//Recommended Actions//EN",
        "CALSCALE:GREGORIAN",
        _fold(f"X-WR-CALNAME:{_escape(calendar_name)}"),
    ]
    now_stamp = _dt(datetime.now())
    for event in events:
        end = event.start + timedelta(minutes=event.duration_minutes)
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uuid4()}@personal-cfo")
        lines.append(_fold(f"SUMMARY:{_escape(event.title)}"))
        if event.description:
            lines.append(_fold(f"DESCRIPTION:{_escape(event.description)}"))
        lines.append(f"DTSTAMP:{now_stamp}")
        lines.append(f"DTSTART:{_dt(event.start)}")
        lines.append(f"DTEND:{_dt(end)}")
        if event.recurrence_monthly_count and event.recurrence_monthly_count > 1:
            lines.append(f"RRULE:FREQ=MONTHLY;COUNT={event.recurrence_monthly_count}")
        if event.reminder_minutes_before:
            lines.append("BEGIN:VALARM")
            lines.append("ACTION:DISPLAY")
            lines.append(_fold(f"DESCRIPTION:{_escape(event.title)}"))
            lines.append(f"TRIGGER:-PT{event.reminder_minutes_before}M")
            lines.append("END:VALARM")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def google_calendar_link(event: CalendarEvent) -> str:
    """A zero-auth 'quick add' link that opens Google Calendar's own event
    creation UI pre-filled -- not sync, just a one-click prefill. Modeled
    as an all-day event so there's no timezone conversion to get wrong."""
    start_date = event.start.date()
    end_date = start_date + timedelta(days=1)
    params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{start_date:%Y%m%d}/{end_date:%Y%m%d}",
        "details": event.description,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def slugify(text: str) -> str:
    keep = [c if c.isalnum() else "-" for c in text.lower()]
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60] or "reminder"
