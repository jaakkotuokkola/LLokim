# Development

## Local setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -e ".[test]"
```

## Test

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Run

```bash
.venv/bin/llokim --help
.venv/bin/llokim doctor
.venv/bin/llokim analyze --since 1h --no-ai --json
```

## Benchmark

```bash
.venv/bin/python -m llokim.benchmark
```

The benchmark is synthetic and measures parsing, analysis, and report
generation. It does not read the host journal. Memory reporting uses the
process peak resident-set size exposed by Python's `resource` module where
available.

To print JSON suitable for comparison or archival:

```bash
.venv/bin/python -m llokim.benchmark --json
```
