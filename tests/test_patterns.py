import unittest

from llokim.models import LogEvent
from llokim.patterns import (
    DETECTION_RULES,
    get_rule,
    get_rules,
    match_rules,
)


def event(message: str, service: str = "test") -> LogEvent:
    return LogEvent(
        timestamp="2023-11-15T10:15:00+00:00",
        hostname="host",
        service=service,
        pid=42,
        priority=3,
        message=message,
        unit=f"{service}.service",
    )


class PatternTests(unittest.TestCase):
    def test_authentication_failure(self):
        matches = match_rules(event("Failed password for invalid user admin", "sshd"))
        identifiers = {rule.identifier for rule in matches}
        self.assertIn("auth.authentication_failure", identifiers)

    def test_failed_service(self):
        matches = match_rules(event("nginx.service: Failed to start nginx", "nginx"))
        identifiers = {rule.identifier for rule in matches}
        self.assertIn("services.failed_unit", identifiers)

    def test_kernel_warning(self):
        matches = match_rules(event("kernel: warning - watchdog reset", "kernel"))
        identifiers = {rule.identifier for rule in matches}
        self.assertIn("kernel.warning", identifiers)

    def test_storage_warning(self):
        matches = match_rules(event("Buffer I/O error on dev sda1", "kernel"))
        identifiers = {rule.identifier for rule in matches}
        self.assertIn("storage.warning", identifiers)

    def test_network_event(self):
        matches = match_rules(event("Network unreachable", "NetworkManager"))
        identifiers = {rule.identifier for rule in matches}
        self.assertIn("network.failure", identifiers)

    def test_false_positive(self):
        matches = match_rules(event("User profile updated successfully", "accounts"))
        self.assertEqual(matches, [])

    def test_rule_lookup_and_category(self):
        self.assertIsNotNone(get_rule("auth.authentication_failure"))
        auth_rules = get_rules("Authentication")
        self.assertEqual(len(auth_rules), 1)
        self.assertEqual(len(DETECTION_RULES), 6)


if __name__ == "__main__":
    unittest.main()
