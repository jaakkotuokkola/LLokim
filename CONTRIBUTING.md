# Contributing

Contributions are welcome. Keep changes focused, lightweight, and compatible
with Python 3.10 or newer.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/llokim --help
.venv/bin/llokim doctor
```

Normal unit tests must use synthetic data. Do not make tests depend on a
developer's actual journal or on an Ollama installation.

## Change guidelines

- Follow the existing modular architecture.
- Preserve deterministic analysis without Ollama.
- Never use `shell=True`.
- Never execute AI-generated commands.
- Treat journal content as untrusted input.
- Add tests for behavior changes and security boundaries.
- Do not add telemetry or cloud dependencies.
