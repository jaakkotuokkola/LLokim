# Architecture

LLokim uses a modular Python package in `src/llokim`.

## Components

- `cli.py`: argparse command parsing and command dispatch
- `config.py`: configuration defaults and validation
- `collector.py`: bounded, explicit-argument `journalctl` collection
- `parser.py`: journal JSON normalization and malformed-data handling
- `models.py`: JSON-serializable dataclasses
- `analyzer.py`: deterministic counting and finding generation
- `patterns.py`: modular detection rules
- `ai.py`: local Ollama availability, prompt, and inference handling
- `reporter.py`: terminal, JSON, and text rendering
- `benchmark.py`: synthetic performance measurement

## Data flow

1. The CLI loads configuration.
2. The collector retrieves structured journal lines.
3. The parser converts entries into `LogEvent` objects.
4. The analyzer creates a deterministic `AnalysisReport`.
5. Optional Ollama interpretation adds an AI summary.
6. The reporter renders terminal, JSON, or plain-text output.

No AI result changes the system or journal. AI output is presentation data
only.
