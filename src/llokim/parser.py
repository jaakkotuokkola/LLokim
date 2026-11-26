"""Normalization of journalctl JSON output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from .models import LogEvent


PRIORITY_NAMES = {
    "emerg": 0,
    "alert": 1,
    "crit": 2,
    "err": 3,
    "error": 3,
    "warning": 4,
    "warn": 4,
    "notice": 5,
    "info": 6,
    "debug": 7,
}

MAX_MESSAGE_LENGTH = 4096
MAX_FIELD_LENGTH = 1024


def parse_timestamp(value: object) -> str | None:
    """Parse journal microseconds or common timestamp strings."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 100000000000:
            numeric /= 1000000
        try:
            return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return parse_timestamp(int(text))

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except (TypeError, ValueError):
        return None


def _safe_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return text[:MAX_FIELD_LENGTH]
    if isinstance(value, (int, float)):
        return str(value)
    return None


def parse_priority(value: object) -> int | str | None:
    """Normalize journal priority names and numbers."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 7 else str(value)
    if isinstance(value, float):
        if value.is_integer():
            return parse_priority(int(value))
        return str(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return None
        if text.isdigit():
            number = int(text)
            return number if 0 <= number <= 7 else str(number)
        if text in PRIORITY_NAMES:
            return PRIORITY_NAMES[text]
        return text
    return None


def parse_journal_entry(entry: object) -> LogEvent | None:
    """Parse one journal JSON object or JSON string into a LogEvent."""
    if isinstance(entry, str):
        text = entry
        if text.startswith("{"):
            try:
                entry = json.loads(text)
            except json.JSONDecodeError:
                return None
        else:
            return None

    if not isinstance(entry, dict):
        return None

    raw = entry
    timestamp = parse_timestamp(
        raw.get("__REALTIME_TIMESTAMP")
        or raw.get("_SOURCE_REALTIME_TIMESTAMP")
        or raw.get("timestamp")
        or raw.get("time")
    )

    hostname = _safe_text(
        raw.get("_HOSTNAME") or raw.get("HOSTNAME") or raw.get("hostname")
    )
    unit = _safe_text(
        raw.get("_SYSTEMD_UNIT") or raw.get("UNIT") or raw.get("unit")
    )
    service = _safe_text(
        raw.get("SYSLOG_IDENTIFIER")
        or raw.get("_COMM")
        or raw.get("service")
        or unit
    )

    pid_value = raw.get("_PID") or raw.get("PID") or raw.get("pid")
    pid: int | None
    if isinstance(pid_value, bool):
        pid = None
    elif isinstance(pid_value, int):
        pid = pid_value
    elif isinstance(pid_value, str) and pid_value.strip().isdigit():
        pid = int(pid_value.strip())
    else:
        pid = None

    priority = parse_priority(
        raw.get("PRIORITY")
        or raw.get("priority")
        or raw.get("severity")
    )

    message_value = raw.get("MESSAGE")
    if message_value is None:
        message_value = raw.get("message")
    if isinstance(message_value, (dict, list)):
        message = json.dumps(message_value, ensure_ascii=False)
    else:
        message = _safe_text(message_value) or ""
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH] + "...[truncated]"

    return LogEvent(
        timestamp=timestamp,
        hostname=hostname,
        service=service,
        pid=pid,
        priority=priority,
        message=message,
        unit=unit,
    )


def parse_line(line: str) -> LogEvent | None:
    """Parse one line of journal JSON."""
    if not isinstance(line, str) or not line.strip():
        return None
    line = line.strip()
    if line.startswith("{"):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        return parse_journal_entry(data)
    return parse_journal_entry(line)


def parse_journal_entries(entries: Iterable[object]) -> list[LogEvent]:
    """Parse an iterable of raw entries and skip malformed or empty items."""
    events: list[LogEvent] = []
    for entry in entries:
        if isinstance(entry, dict) and "_llokim_raw_line" in entry:
            event = parse_line(entry["_llokim_raw_line"])
        else:
            event = parse_journal_entry(entry)
        if event is not None:
            events.append(event)
    return events


def parse_journal_line(line: str) -> LogEvent | None:
    """Compatibility alias for parsing one journal JSON line."""
    return parse_line(line)


def parse_events(entries: Iterable[object]) -> list[LogEvent]:
    """Compatibility alias for parsing journal entries."""
    return parse_journal_entries(entries)
