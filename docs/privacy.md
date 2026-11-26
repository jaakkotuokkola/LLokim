# Privacy

LLokim is local-first.

- Journal collection uses the local `journalctl` command.
- No logs are uploaded.
- No telemetry or usage data is collected.
- No API keys or cloud AI services are required.
- Ollama URLs are restricted to loopback endpoints.
- Obvious passwords, tokens, bearer credentials, private-key markers, and
  credential-bearing URLs are redacted before AI payload construction.
- Log evidence is bounded and delimited as untrusted prompt input.
- AI output never executes commands or modifies system configuration.

Journal entries can contain hostnames, usernames, network details, and
application data. Exported reports should be handled as potentially sensitive.
