"""Safe collection of system journal entries using journalctl."""

from __future__ import annotations

import shutil
import subprocess
import re
from typing import Iterable

MAX_EVENTS = 10000
MAX_TIMEOUT_SECONDS = 300


class CollectionError(RuntimeError):
    """Base class for journal collection failures."""


class JournalctlNotFoundError(CollectionError):
    """Raised when journalctl is not installed."""


class JournalAccessError(CollectionError):
    """Raised when journal access is denied or unavailable."""


class JournalTimeoutError(CollectionError):
    """Raised when journalctl exceeds the collection timeout."""


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be a positive integer")
    if limit < 1:
        raise ValueError("limit must be a positive integer")
    if limit > MAX_EVENTS:
        raise ValueError(f"limit must not exceed {MAX_EVENTS}")
    return limit


def normalize_since(since: str) -> str:
    """Convert LLokim relative periods to journalctl syntax."""
    text = since.strip()
    if any(ord(char) < 32 for char in text):
        raise ValueError("since contains control characters")
    if re.fullmatch(r"[1-9]\d*[mhd]", text, re.IGNORECASE):
        return f"-{text.lower()}"
    return text


def validate_priority(value: str | int) -> str:
    """Normalize and validate one journal priority selector."""
    if isinstance(value, bool):
        raise ValueError("priority must be a valid journal priority")
    if isinstance(value, int):
        if 0 <= value <= 7:
            return str(value)
        raise ValueError("priority must be between 0 and 7")
    if not isinstance(value, str):
        raise ValueError("priority must be a valid journal priority")
    normalized = value.strip().lower()
    allowed = {"0", "1", "2", "3", "4", "5", "6", "7",
               "emerg", "alert", "crit", "err", "warning",
               "notice", "info", "debug"}
    if normalized not in allowed:
        raise ValueError("priority must be a valid journal priority")
    aliases = {"emerg": "0", "alert": "1", "crit": "2", "err": "3",
               "warning": "4", "notice": "5", "info": "6", "debug": "7"}
    return aliases.get(normalized, normalized)


def collect(
    since: str | None = None,
    limit: int = 2000,
    priority: str | int | Iterable[str | int] | None = None,
    timeout: float = 30.0,
    severity: str | int | Iterable[str | int] | None = None,
    priorities: str | int | Iterable[str | int] | None = None,
) -> list[dict]:
    """Collect structured journal entries as dictionaries.

    This function uses an explicit argument list and never invokes a shell.
    """
    limit = _validate_limit(limit)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout < 1
        or timeout > MAX_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds"
        )
    journalctl = shutil.which("journalctl")
    if journalctl is None:
        raise JournalctlNotFoundError(
            "journalctl was not found; install systemd journal tools"
        )

    command = [
        journalctl,
        "--no-pager",
        "--quiet",
        "--output=json",
        "--lines",
        str(limit),
    ]
    if since:
        if not isinstance(since, str) or not since.strip():
            raise ValueError("since must be a non-empty string")
        command.extend(["--since", normalize_since(since)])

    selected_priority = priority
    if selected_priority is None:
        selected_priority = severity
    if selected_priority is None:
        selected_priority = priorities
    if selected_priority is not None:
        if isinstance(selected_priority, (str, int)):
            priority_values = [selected_priority]
        else:
            priority_values = list(selected_priority)
        if not priority_values:
            raise ValueError("priority must not be empty")
        joined = ",".join(validate_priority(item) for item in priority_values)
        command.extend(["--priority", joined])

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise JournalTimeoutError(
            f"journalctl timed out after {timeout:g} seconds"
        ) from exc
    except OSError as exc:
        raise CollectionError(
            f"could not start journalctl: {exc.strerror or exc.__class__.__name__}"
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        lowered = stderr.lower()
        if "permission" in lowered or "denied" in lowered or "not permitted" in lowered:
            raise JournalAccessError(
                "journal access was denied; no elevated privileges were used"
            )
        if stderr:
            raise JournalAccessError(f"journalctl failed: {stderr}")
        raise JournalAccessError("journalctl failed with no error details")

    entries: list[dict] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append({"_llokim_raw_line": line})
    return entries


def collect_events(
    since: str | None = None,
    limit: int = 2000,
    priority: str | int | Iterable[str | int] | None = None,
    timeout: float = 30.0,
) -> list[dict]:
    """Compatibility alias for collect."""
    return collect(since=since, limit=limit, priority=priority, timeout=timeout)


def collect_journal(
    since: str | None = None,
    limit: int = 2000,
    severity: str | int | Iterable[str | int] | None = None,
    timeout: float = 30.0,
    priority: str | int | Iterable[str | int] | None = None,
    priorities: str | int | Iterable[str | int] | None = None,
) -> list[dict]:
    """Compatibility alias using the severity terminology."""
    selected = severity if severity is not None else priority
    if selected is None:
        selected = priorities
    return collect(since=since, limit=limit, priority=selected, timeout=timeout)


class JournalCollector:
    """Small object-oriented wrapper around journal collection."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def collect(
        self,
        since: str | None = None,
        limit: int = 2000,
        severity: str | int | Iterable[str | int] | None = None,
    ) -> list[dict]:
        return collect(
            since=since,
            limit=limit,
            severity=severity,
            timeout=self.timeout,
        )
