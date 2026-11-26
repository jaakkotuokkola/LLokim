"""Deterministic Linux journal analysis."""

from __future__ import annotations

from collections import Counter, defaultdict
from time import perf_counter
from typing import Iterable

from .models import AnalysisReport, Finding, LogEvent
from .patterns import DETECTION_RULES


SEVERITY_NAMES = (
    "emergency",
    "alert",
    "critical",
    "error",
    "warning",
    "notice",
    "info",
    "debug",
)


def classify_severity(priority: int | str | None) -> str:
    """Map journal priorities to terminal/report severity names."""
    if isinstance(priority, int):
        if 0 <= priority < len(SEVERITY_NAMES):
            return SEVERITY_NAMES[priority]
    if isinstance(priority, str):
        normalized = priority.strip().casefold()
        aliases = {
            "emerg": "emergency",
            "err": "error",
            "warn": "warning",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in SEVERITY_NAMES:
            return normalized
    return "unknown"


def count_events(events: Iterable[LogEvent]) -> int:
    """Count events in an iterable without modifying it."""
    return sum(1 for _ in events)


def count_by_severity(events: Iterable[LogEvent]) -> dict[str, int]:
    """Count events by normalized severity."""
    counts = Counter(classify_severity(event.priority) for event in events)
    return dict(sorted(counts.items()))


def group_errors_by_service(events: Iterable[LogEvent]) -> dict[str, list[LogEvent]]:
    """Group error-level events by service name."""
    grouped: dict[str, list[LogEvent]] = defaultdict(list)
    for event in events:
        severity = classify_severity(event.priority)
        if severity not in {"emergency", "alert", "critical", "error"}:
            continue
        service = event.service or event.unit or "unknown"
        grouped[service].append(event)
    return dict(sorted(grouped.items()))


def group_by_service(events: Iterable[LogEvent]) -> dict[str, list[LogEvent]]:
    """Group all events by service name."""
    grouped: dict[str, list[LogEvent]] = defaultdict(list)
    for event in events:
        grouped[event.service or event.unit or "unknown"].append(event)
    return dict(sorted(grouped.items()))


def event_evidence(event: LogEvent) -> dict[str, object]:
    """Create traceable evidence from one source event."""
    message = event.message
    if len(message) > 1024:
        message = message[:1024] + "...[truncated]"
    return {
        "timestamp": event.timestamp,
        "hostname": event.hostname,
        "service": event.service,
        "pid": event.pid,
        "priority": event.priority,
        "message": message,
        "unit": event.unit,
    }


def find_repeated_messages(
    events: Iterable[LogEvent],
    minimum_occurrences: int = 2,
) -> list[Finding]:
    """Find exact repeated messages, grouped within each service."""
    if isinstance(minimum_occurrences, bool) or minimum_occurrences < 1:
        raise ValueError("minimum_occurrences must be a positive integer")

    groups: dict[tuple[str, str], list[LogEvent]] = defaultdict(list)
    for event in events:
        message = " ".join(event.message.split()).strip()
        if not message:
            continue
        service = event.service or event.unit or "unknown"
        groups[(service, message)].append(event)

    findings: list[Finding] = []
    for (service, message), matches in groups.items():
        if len(matches) < minimum_occurrences:
            continue
        timestamps = [event.timestamp for event in matches if event.timestamp]
        severity_priority = {
            "emergency": 0,
            "alert": 1,
            "critical": 2,
            "error": 3,
            "warning": 4,
            "notice": 5,
            "info": 6,
            "debug": 7,
            "unknown": 8,
        }
        repeated_severity = min(
            (classify_severity(event.priority) for event in matches),
            key=lambda severity: severity_priority.get(severity, 8),
        )
        findings.append(
            Finding(
                identifier=f"repeated-message:{service}:{message[:80]}",
                category="General errors",
                severity=repeated_severity,
                title=f"Repeated message in {service}",
                description="The same normalized message occurred repeatedly.",
                occurrence_count=len(matches),
                first_seen=min(timestamps) if timestamps else None,
                last_seen=max(timestamps) if timestamps else None,
                evidence=[
                    event_evidence(event)
                    for event in matches[:100]
                ],
                confidence=0.9,
            )
        )
    return findings


def find_recurring_failures(events: Iterable[LogEvent]) -> list[Finding]:
    """Find services with repeated error-level events."""
    grouped = group_errors_by_service(events)
    findings: list[Finding] = []
    for service, matches in grouped.items():
        if len(matches) < 2:
            continue
        timestamps = [event.timestamp for event in matches if event.timestamp]
        findings.append(
            Finding(
                identifier=f"recurring-failure:{service}",
                category="Services",
                severity="error",
                title=f"Recurring failures from {service}",
                description="Multiple error-level events were recorded for this service.",
                occurrence_count=len(matches),
                first_seen=min(timestamps) if timestamps else None,
                last_seen=max(timestamps) if timestamps else None,
                evidence=[
                    event_evidence(event)
                    for event in matches[:100]
                ],
                confidence=0.85,
            )
        )
    return findings


def identify_related_events(events: Iterable[LogEvent]) -> list[Finding]:
    """Link consecutive high-priority events that occur for the same unit or service."""
    by_service: dict[str, list[LogEvent]] = defaultdict(list)
    for event in events:
        severity = classify_severity(event.priority)
        if severity in {"emergency", "alert", "critical", "error", "warning"}:
            service = event.service or event.unit or "unknown"
            by_service[service].append(event)

    findings: list[Finding] = []
    for service, matches in sorted(by_service.items()):
        if len(matches) < 2:
            continue
        timestamps = [event.timestamp for event in matches if event.timestamp]
        findings.append(
            Finding(
                identifier=f"related-events:{service}",
                category="General errors",
                severity="warning",
                title=f"Related high-priority events for {service}",
                description="Multiple high-priority events were associated with the same service.",
                occurrence_count=len(matches),
                first_seen=min(timestamps) if timestamps else None,
                last_seen=max(timestamps) if timestamps else None,
                evidence=[
                    event_evidence(event)
                    for event in matches[:100]
                ],
                confidence=0.6,
            )
        )
    return findings


def apply_detection_rules(
    events: Iterable[LogEvent],
) -> list[Finding]:
    """Apply all deterministic detection rules and return grouped findings."""
    event_list = list(events)
    findings: list[Finding] = []
    for rule in DETECTION_RULES:
        matches = rule.matching_events(event_list)
        if not matches:
            continue
        timestamps = [event.timestamp for event in matches if event.timestamp]
        findings.append(
            Finding(
                identifier=rule.identifier,
                category=rule.category,
                severity=rule.severity,
                title=rule.name,
                description=rule.description,
                occurrence_count=len(matches),
                first_seen=min(timestamps) if timestamps else None,
                last_seen=max(timestamps) if timestamps else None,
                evidence=[
                    event_evidence(event)
                    for event in matches[:100]
                ],
                confidence=0.75,
            )
        )
    return findings


def rank_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Rank findings by severity, confidence, and occurrence count."""
    severity_rank = {
        "emergency": 8,
        "alert": 7,
        "critical": 6,
        "error": 5,
        "warning": 4,
        "notice": 3,
        "info": 2,
        "debug": 1,
        "unknown": 0,
    }
    return sorted(
        list(findings),
        key=lambda finding: (
            severity_rank.get(finding.severity.casefold(), 0),
            finding.confidence,
            finding.occurrence_count,
        ),
        reverse=True,
    )


def analyze_events(events: Iterable[LogEvent]) -> AnalysisReport:
    """Produce a deterministic structured report for a collection of events."""
    started = perf_counter()
    event_list = list(events)

    findings = apply_detection_rules(event_list)
    findings.extend(find_repeated_messages(event_list))
    findings.extend(find_recurring_failures(event_list))
    findings.extend(identify_related_events(event_list))

    unique_findings: dict[str, Finding] = {}
    for finding in findings:
        if finding.identifier not in unique_findings:
            unique_findings[finding.identifier] = finding

    timestamps = [event.timestamp for event in event_list if event.timestamp]
    return AnalysisReport(
        start_time=min(timestamps) if timestamps else None,
        end_time=max(timestamps) if timestamps else None,
        total_events=len(event_list),
        severity_counts=count_by_severity(event_list),
        findings=rank_findings(unique_findings.values()),
        ai_summary=None,
        recommendations=[],
        analysis_duration=max(perf_counter() - started, 0.0),
    )
