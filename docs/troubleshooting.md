# Troubleshooting

## `journalctl` is not found

Install or restore the systemd journal tools for your distribution. LLokim
does not escalate privileges automatically.

## Journal access is denied

LLokim never changes permissions or uses elevated privileges. Check whether
the current Linux user can read the system journal. If access is unavailable,
the doctor and analyze commands will report the failure without exposing log
contents.

## Ollama is unavailable

Start Ollama and verify the model:

```bash
ollama serve
ollama list
ollama pull qwen2.5:1.5b
```

LLokim remains usable with `--no-ai` and falls back to deterministic reports.
CPU inference can take tens of seconds, particularly while Ollama loads the
model. Terminal mode indicates when the request starts. JSON reports expose
`ai_status` and `ai_duration`; `analysis_duration` includes collection,
analysis, and the AI request. Generated AI text streams to stderr while the
request is running; in JSON mode stdout remains valid JSON.
In interactive terminal use, press `q` to cancel generation and continue to
the report. The partial text and findings remain available.

## Configuration is ignored or malformed

Check `~/.config/llokim/config.json`. Malformed values fall back to defaults.
The Ollama URL must use HTTP or HTTPS and point to `localhost`, `127.0.0.1`, or
`::1`.

## JSON output is missing

Use `llokim analyze --json` without a separate text export. JSON mode writes
only the machine-readable report to stdout.

## Report export fails

Confirm that the destination directory is writable. LLokim creates export
directories only within the requested export path.
