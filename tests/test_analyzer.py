import unittest

from llokim.analyzer import (
    analyze_events,
    classify_severity,
    count_by_severity,
    count_events,
    find_recurring_failures,
    find_repeated_messages,
    group_errors_by_service,
    group_by_service,
)
from llokim.models import LogEvent


def event(
    message: str,
    priority: int | str | None = "info",
    service: str | None = "sshd",
    timestamp: str | None = "2023-11-15T10:15:00+00:00",
) -> LogEvent:
    return LogEvent(
        timestamp=timestamp,
        hostname="host",
        service=service,
        pid=42,
        priority=priority,
        message=message,
        unit=f"{service}.service" if service else None,
    )


class AnalyzerTests(unittest.TestCase):
    def test_event_counts(self):
        events = [event("one"), event("two")]
        self.assertEqual(count_events(events), 2)

    def test_severity_counts(self):
        events = [
            event("error", priority=3),
            event("warning", priority=4),
            event("unknown", priority="notice"),
        ]
        counts = count_by_severity(events)
        self.assertEqual(counts["error"], 1)
        self.assertEqual(counts["warning"], 1)
        self.assertEqual(counts["notice"], 1)

    def test_severity_classification(self):
        self.assertEqual(classify_severity(3), "error")
        self.assertEqual(classify_severity("warn"), "warning")
        self.assertEqual(classify_severity("unknown"), "unknown")

    def test_service_grouping(self):
        events = [
            event("failed", priority=3, service="sshd"),
            event("started", priority=6, service="sshd"),
            event("failed", priority=3, service="nginx"),
        ]
        all_groups = group_by_service(events)
        error_groups = group_errors_by_service(events)
        self.assertEqual(len(all_groups["sshd"]), 2)
        self.assertEqual(len(error_groups["nginx"]), 1)

    def test_repeated_messages(self):
        events = [
            event("Authentication failed", priority=3),
            event("Authentication failed", priority=3),
            event("New message", priority=6),
        ]
        findings = find_repeated_messages(events)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].occurrence_count, 2)
        self.assertEqual(len(findings[0].evidence), 2)

    def test_recurring_failures(self):
        events = [
            event("Failed to start service", priority=3, service="nginx"),
            event("Failed to start service", priority=3, service="nginx"),
        ]
        findings = find_recurring_failures(events)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].identifier, "recurring-failure:nginx")

    def test_empty_input(self):
        report = analyze_events([])
        self.assertEqual(report.total_events, 0)
        self.assertEqual(report.findings, [])
        self.assertIsNone(report.start_time)
        self.assertIsNone(report.end_time)


if __name__ == "__main__":
    unittest.main()
