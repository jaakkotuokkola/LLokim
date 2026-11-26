import json
import unittest

from llokim.models import AnalysisReport, Finding, LogEvent


class ModelsTests(unittest.TestCase):
    def test_log_event_json_serialization(self):
        event = LogEvent(
            timestamp="2023-11-15T10:15:00+00:00",
            hostname="host",
            service="sshd",
            pid=42,
            priority=3,
            message="failed",
            unit="sshd.service",
        )
        serialized = json.dumps(event.to_dict())
        self.assertIn('"service": "sshd"', serialized)

    def test_finding_json_serialization(self):
        finding = Finding(
            identifier="auth-failed",
            category="Authentication",
            severity="warning",
            title="Authentication failures",
            description="Repeated authentication failures",
            occurrence_count=2,
            first_seen="2023-11-15T10:00:00+00:00",
            last_seen="2023-11-15T10:15:00+00:00",
            evidence=[{"message": "failed"}],
            confidence=0.8,
        )
        json.dumps(finding.to_dict())

    def test_report_json_serialization(self):
        report = AnalysisReport(
            start_time="2023-11-15T10:00:00+00:00",
            end_time="2023-11-15T11:00:00+00:00",
            total_events=0,
            severity_counts={"error": 0},
        )
        data = json.dumps(report.to_dict())
        self.assertIn('"total_events": 0', data)


if __name__ == "__main__":
    unittest.main()
