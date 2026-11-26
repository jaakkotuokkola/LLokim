import json
import unittest
from pathlib import Path

from llokim.models import LogEvent
from llokim.parser import parse_journal_entry, parse_journal_entries, parse_line


FIXTURES = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_valid_json(self):
        event = parse_journal_entry(
            {
                "__REALTIME_TIMESTAMP": "1700000000000000",
                "_HOSTNAME": "host",
                "SYSLOG_IDENTIFIER": "sshd",
                "_PID": "123",
                "PRIORITY": "3",
                "MESSAGE": "Authentication failed",
                "_SYSTEMD_UNIT": "sshd.service",
            }
        )

        self.assertIsInstance(event, LogEvent)
        self.assertEqual(event.hostname, "host")
        self.assertEqual(event.service, "sshd")
        self.assertEqual(event.pid, 123)
        self.assertEqual(event.priority, 3)
        self.assertEqual(event.message, "Authentication failed")
        self.assertEqual(event.unit, "sshd.service")

    def test_missing_fields(self):
        event = parse_journal_entry({})
        self.assertIsNotNone(event)
        self.assertIsNone(event.timestamp)
        self.assertIsNone(event.hostname)
        self.assertEqual(event.message, "")

    def test_invalid_timestamp(self):
        event = parse_journal_entry(
            {"__REALTIME_TIMESTAMP": "not-a-time", "MESSAGE": "ok"}
        )
        self.assertIsNone(event.timestamp)

    def test_malformed_json_line(self):
        self.assertIsNone(parse_line("{bad json"))

    def test_empty_message(self):
        event = parse_journal_entry({"MESSAGE": "", "PRIORITY": "info"})
        self.assertEqual(event.message, "")

    def test_fixture_entries(self):
        lines = (FIXTURES / "sample_journal.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        events = parse_journal_entries(lines)
        self.assertEqual(len(events), 3)

    def test_malformed_fixture_skips_bad_data(self):
        lines = (FIXTURES / "malformed_entries.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        events = parse_journal_entries(lines)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].message, "")


if __name__ == "__main__":
    unittest.main()
