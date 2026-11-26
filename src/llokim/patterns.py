"""Modular, deterministic detection rules for LLokim."""

from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern
from typing import Iterable

from .models import LogEvent


@dataclass(frozen=True)
class DetectionRule:
    """A detection rule with narrow matching and traceable evidence."""

    identifier: str
    name: str
    description: str
    category: str
    severity: str
    patterns: tuple[Pattern[str], ...]

    def matches(self, event: LogEvent) -> bool:
        message = event.message.strip()
        if not message:
            return False
        text = message.casefold()
        return any(pattern.search(text) is not None for pattern in self.patterns)

    def matching_events(self, events: Iterable[LogEvent]) -> list[LogEvent]:
        return [event for event in events if self.matches(event)]


def _compile(patterns: Iterable[str]) -> tuple[Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


DETECTION_RULES: tuple[DetectionRule, ...] = (
    DetectionRule(
        identifier="auth.authentication_failure",
        name="Authentication failure",
        description="Repeated or notable authentication failures.",
        category="Authentication",
        severity="warning",
        patterns=_compile(
            (
                r"\bfailed (?:password|login|authentication)\b",
                r"\b(authentication failure|authentication failed|invalid user)\b",
                r"\bpam_[a-z_]+:?\s*authentication failure\b",
            )
        ),
    ),
    DetectionRule(
        identifier="services.failed_unit",
        name="Failed service",
        description="A systemd unit or service reports a failure.",
        category="Services",
        severity="error",
        patterns=_compile(
            (
                r"\b(?:unit|service)\s+[^\n]*\s(?:failed|failure)\b",
                r"\bfailed to (?:start|stop|restart|load)\b",
                r"\b(?:exit-code|process)\b.*\b(?:failed|failure)\b",
                r"\binactive \(dead\)\b",
            )
        ),
    ),
    DetectionRule(
        identifier="kernel.warning",
        name="Kernel warning",
        description="A kernel warning or instability indicator.",
        category="Kernel",
        severity="warning",
        patterns=_compile(
            (
                r"\b(?:kernel|kern):?\s*(?:warning|bug|oops|panic)\b",
                r"\b(?:kernel panic|watchdog: bug|general protection fault|segmentation fault)\b",
                r"\btainted kernel\b",
            )
        ),
    ),
    DetectionRule(
        identifier="storage.warning",
        name="Storage warning",
        description="Potential disk or filesystem failure indicators.",
        category="Storage",
        severity="error",
        patterns=_compile(
            (
                r"\b(?:i/o error|i/o timeout|buffer i/o error)\b",
                r"\b(?:read-only (?:file)?system|readonly filesystem)\b",
                r"\bno space left on device\b",
                r"\b(?:ext4|xfs|btrfs).*(?:corrupt|error|failure)\b",
            )
        ),
    ),
    DetectionRule(
        identifier="network.failure",
        name="Network failure",
        description="An observed network link or route failure.",
        category="Networking",
        severity="warning",
        patterns=_compile(
            (
                r"\b(?:network unreachable|host unreachable|no route to host)\b",
                r"\blink is (?:down|not found)\b",
                r"\bdhcp(?:d)?.*(?:failed|failure|timed out|timeout)\b",
                r"\b(?:connection refused|name resolution failed)\b",
            )
        ),
    ),
    DetectionRule(
        identifier="hardware.warning",
        name="Hardware warning",
        description="Potential hardware or firmware failure indicators.",
        category="Hardware",
        severity="warning",
        patterns=_compile(
            (
                r"\b(?:hardware error|machine check exception|corrected memory error)\b",
                r"\b(?:nvme|drive|disk)\b.*\b(?:critical (?:warning|error)|unrecovered error)\b",
                r"\b(?:thermal|temperature).*(?:critical|exceeded|above threshold)\b",
            )
        ),
    ),
)


def get_rules(category: str | None = None) -> tuple[DetectionRule, ...]:
    """Return all rules, optionally filtered by category."""
    if category is None:
        return DETECTION_RULES
    normalized = category.casefold()
    return tuple(
        rule
        for rule in DETECTION_RULES
        if rule.category.casefold() == normalized
    )


def get_rule(identifier: str) -> DetectionRule | None:
    """Return a rule by unique identifier."""
    for rule in DETECTION_RULES:
        if rule.identifier == identifier:
            return rule
    return None


def match_rules(event: LogEvent) -> list[DetectionRule]:
    """Return every rule matched by a single event."""
    return [rule for rule in DETECTION_RULES if rule.matches(event)]

