import json
import tempfile
import unittest
from pathlib import Path

from llokim.models import AnalysisReport, Finding
from llokim.reporter import (
    export_json,
    export_text,
    render_json,
    render_terminal,
    render_text,
)


def sample_report() -> AnalysisReport:
    return AnalysisReport(
        start_time="2026-11-26T01:00:00+00:00",
        end_time="2026-11-26T01:02:00+00:00",
        total_events=3,
        severity_counts={"error": 2, "warning": 1},
        findings=[
            Finding(
                identifier="auth.authentication_failure",
                category="Authentication",
                severity="warning",
                title="Authentication failure",
                description="Authentication failures were detected.",
                occurrence_count=2,
                first_seen="2026-11-26T01:00:00+00:00",
                last_seen="2026-11-26T01:01:00+00:00",
                evidence=[
                    {
                        "timestamp": "2026-11-26T01:00:00+00:00",
                        "message": "Failed password",
                    }
                ],
                confidence=0.75,
            )
        ],
        ai_summary=None,
        recommendations=["Review authentication logs."],
        analysis_duration=0.125,
    )


class ReporterTests(unittest.TestCase):
    def test_terminal_rendering(self):
        rendered = render_terminal(sample_report(), use_color=False)
        self.assertIn("LLokim", rendered)
        self.assertIn("Total events examined", rendered)
        self.assertIn("Authentication failure", rendered)
        self.assertIn("Evidence:", rendered)
        self.assertIn("0.125 seconds", rendered)

    def test_json_serialization(self):
        decoded = json.loads(render_json(sample_report()))
        self.assertEqual(decoded["total_events"], 3)
        self.assertEqual(decoded["findings"][0]["severity"], "warning")

    def test_empty_report(self):
        report = AnalysisReport(start_time=None, end_time=None, total_events=0)
        rendered = render_terminal(report, use_color=False)
        self.assertIn("No severity data", rendered)
        self.assertIn("No important findings detected.", rendered)

    def test_missing_ai_response(self):
        rendered = render_text(sample_report())
        self.assertIn("Not available (status: not_requested).", rendered)

    def test_text_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = export_text(
                sample_report(),
                Path(directory) / "nested" / "report.txt",
            )
            self.assertTrue(path.exists())
            self.assertIn("LLokim", path.read_text(encoding="utf-8"))

    def test_json_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = export_json(
                sample_report(),
                Path(directory) / "report.json",
            )
            decoded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(decoded["total_events"], 3)


if __name__ == "__main__":
    unittest.main()
