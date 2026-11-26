# LLokim

LLokim is a lightweight, privacy-focused Linux diagnostic utility. It collects
structured system journal events, performs deterministic analysis, and can
optionally ask a local Ollama model to explain findings.

## Features

- Local-first diagnostics: no cloud AI, API keys, subscriptions, or telemetry
- Deterministic severity counts, service grouping, recurring-event detection,
  and modular rules
- Optional Ollama integration with a deterministic fallback
- Human-readable terminal reports, JSON output, and text export
- Synthetic unit tests that do not require the developer's journal or Ollama
- Low dependency footprint based primarily on the Python standard library

## Requirements

- Linux
- Python 3.10 or newer
- `journalctl` for system journal collection
- Ollama for optional AI interpretation

Target hardware includes low-power, CPU-only Linux laptops with approximately
8 GB RAM. The Ollama model and inference process are separate from LLokim.

## Installation

Create an isolated environment rather than installing into Debian-managed
Python:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -e .
```

Run LLokim:

```bash
.venv/bin/llokim --help
.venv/bin/llokim --version
.venv/bin/llokim doctor
```

## Usage

```bash
llokim analyze
llokim analyze --since 1h
llokim analyze --since 24h
llokim analyze --since 7d
llokim analyze --no-ai
llokim analyze --limit 500
llokim analyze --json
llokim analyze --output ~/.local/share/llokim/reports/report.txt
```

Relative periods accept `m`, `h`, and `d`. JSON mode writes only valid JSON to
stdout. The `--output` option exports a plain-text report.
When findings exist, Ollama inference runs synchronously and may take tens of
seconds on CPU, especially on the first request after the model is unloaded.
Reports include `ai_status`, `ai_duration`, and end-to-end `analysis_duration`.
AI text streams to stderr as Ollama generates it; JSON report data remains
valid on stdout.
In an interactive terminal, press `q` during generation to stop inference and
continue to the report with the partial AI text and finding evidence.

## Configuration

Configuration is loaded from `~/.config/llokim/config.json`:

```json
{
  "ollama_url": "http://localhost:11434",
  "model": "qwen2.5:1.5b",
  "ai_enabled": true,
  "default_period": "2h",
  "max_events": 2000,
  "request_timeout": 120,
  "report_directory": "~/.local/share/llokim/reports"
}
```

Defaults are applied when the file is missing or malformed. Ollama URLs are
restricted to loopback endpoints.

## Privacy

System journal entries can contain private or sensitive information. LLokim
does not upload logs or collect telemetry, and it does not execute AI output.
AI prompts contain redacted, bounded finding evidence. Ollama runs locally.

## Known limitations

- Real benchmark numbers depend on host hardware and journal volume.
- Ollama inference is optional and requires the model to be installed locally.
- Ordinary text logs, historical comparisons, SQLite history, watch mode,
  custom plugins, scheduled reports, and hardware-disk integrations are future
  features, not implemented in 0.1.0.
- Findings are evidence-based observations, not confirmed diagnoses.
- Screenshot documentation is not included until reproducible release
  captures are available.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Benchmarks

Run synthetic parser, analyzer, and report benchmarks:

```bash
.venv/bin/python -m llokim.benchmark
```

The benchmark uses synthetic events and never reads private journal entries.
Measured results are printed, not assumed or fabricated.
It reports parsing, analysis, report-generation time, and process peak RSS.
AI inference duration is marked as not run because it requires a live local
Ollama model and request.

## Development

See [docs/development.md](docs/development.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
