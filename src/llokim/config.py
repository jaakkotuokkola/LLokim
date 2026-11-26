"""Configuration loading and validation for LLokim."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
MAX_EVENTS = 10000
MAX_REQUEST_TIMEOUT = 300


@dataclass(frozen=True)
class Config:
    """Validated LLokim configuration."""

    ollama_url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_MODEL
    ai_enabled: bool = True
    default_period: str = "2h"
    max_events: int = 2000
    request_timeout: int = 120
    report_directory: Path = Path("~/.local/share/llokim/reports")

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "report_directory", Path(self.report_directory).expanduser()
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible configuration dictionary."""
        data = asdict(self)
        data["report_directory"] = str(self.report_directory)
        return data


def get_config_path() -> Path:
    """Return the platform configuration path."""
    return Path("~/.config/llokim/config.json").expanduser()


def get_default_config() -> Config:
    """Return a fresh default configuration object."""
    return Config()


def validate_config(data: Mapping[str, Any]) -> Config:
    """Validate a configuration mapping and return a Config instance."""
    unknown_keys = set(data) - set(Config.__dataclass_fields__)
    if unknown_keys:
        raise ValueError(
            "Unknown configuration key(s): " + ", ".join(sorted(unknown_keys))
        )

    defaults = get_default_config()
    ollama_url = data.get("ollama_url", defaults.ollama_url)
    model = data.get("model", defaults.model)
    ai_enabled = data.get("ai_enabled", defaults.ai_enabled)
    default_period = data.get("default_period", defaults.default_period)
    max_events = data.get("max_events", defaults.max_events)
    request_timeout = data.get("request_timeout", defaults.request_timeout)
    report_directory = data.get("report_directory", defaults.report_directory)

    if not isinstance(ollama_url, str) or not ollama_url.strip():
        raise ValueError("ollama_url must be a non-empty string")
    if not ollama_url.startswith(("http://", "https://")):
        raise ValueError("ollama_url must use http:// or https://")
    from urllib.parse import urlsplit
    parsed_url = urlsplit(ollama_url)
    if parsed_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("ollama_url must point to a local Ollama instance")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    if not isinstance(ai_enabled, bool):
        raise ValueError("ai_enabled must be a boolean")
    if not isinstance(default_period, str) or not validate_period(default_period):
        raise ValueError("default_period must be a valid time period")
    if not isinstance(max_events, int) or isinstance(max_events, bool) or max_events < 1:
        raise ValueError("max_events must be a positive integer")
    if max_events > MAX_EVENTS:
        raise ValueError(f"max_events must not exceed {MAX_EVENTS}")
    if (
        not isinstance(request_timeout, int)
        or isinstance(request_timeout, bool)
        or request_timeout < 1
        or request_timeout > MAX_REQUEST_TIMEOUT
    ):
        raise ValueError(
            f"request_timeout must be between 1 and {MAX_REQUEST_TIMEOUT} seconds"
        )
    if not isinstance(report_directory, (str, Path)):
        raise ValueError("report_directory must be a string or path")

    return Config(
        ollama_url=ollama_url.strip(),
        model=model.strip(),
        ai_enabled=ai_enabled,
        default_period=default_period,
        max_events=max_events,
        request_timeout=request_timeout,
        report_directory=Path(report_directory),
    )


def validate_period(value: str) -> bool:
    """Validate a bounded relative time period used by LLokim."""
    if len(value) < 2:
        return False
    amount = value[:-1]
    unit = value[-1:].lower()
    return amount.isdigit() and int(amount) > 0 and unit in {"m", "h", "d"}


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration, returning validated defaults on missing/invalid data."""
    config_path = Path(path).expanduser() if path is not None else get_config_path()
    if not config_path.exists():
        return get_default_config()

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return get_default_config()
        return validate_config(data)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return get_default_config()


def save_config(config: Config, path: Path | str | None = None) -> Path:
    """Save a configuration file and return its path."""
    config_path = Path(path).expanduser() if path is not None else get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2)
        handle.write("\n")
    return config_path
