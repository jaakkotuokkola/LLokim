import json
import tempfile
import unittest
from pathlib import Path

from llokim.config import (
    Config,
    get_config_path,
    load_config,
    save_config,
    validate_config,
)


class ConfigTests(unittest.TestCase):
    def test_defaults_are_used_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path(directory) / "missing.json")

        self.assertTrue(config.ai_enabled)
        self.assertEqual(config.model, "qwen2.5:1.5b")
        self.assertEqual(config.max_events, 2000)

    def test_valid_config_is_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "model": "custom-model",
                        "ai_enabled": False,
                        "default_period": "6h",
                        "max_events": 500,
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(path)

        self.assertFalse(config.ai_enabled)
        self.assertEqual(config.model, "custom-model")
        self.assertEqual(config.default_period, "6h")
        self.assertEqual(config.max_events, 500)

    def test_malformed_config_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{ malformed", encoding="utf-8")
            config = load_config(path)

        self.assertEqual(config.model, "qwen2.5:1.5b")

    def test_validation_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            validate_config({"max_events": 0})
        with self.assertRaises(ValueError):
            validate_config({"ai_enabled": "yes"})
        with self.assertRaises(ValueError):
            validate_config({"request_timeout": -1})

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "config.json"
            original = Config(ai_enabled=False, default_period="24h", max_events=300)
            saved_path = save_config(original, path)
            loaded = load_config(saved_path)

        self.assertEqual(saved_path, path)
        self.assertFalse(loaded.ai_enabled)
        self.assertEqual(loaded.default_period, "24h")
        self.assertEqual(loaded.max_events, 300)

    def test_config_path_is_in_home_directory(self):
        path = get_config_path()
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.name, "config.json")
        self.assertIn("llokim", str(path))


if __name__ == "__main__":
    unittest.main()

