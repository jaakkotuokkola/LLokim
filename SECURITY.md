# Security

LLokim is a local diagnostic application. It does not upload logs or collect
telemetry.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the project maintainers rather
than opening a public issue. Include reproduction details and the affected
version when possible.

## Security principles

- Use explicit subprocess argument lists; never use a shell.
- Do not execute AI-generated commands or modify system configuration.
- Treat journal content as untrusted input.
- Redact obvious credentials before local Ollama prompts.
- Restrict Ollama configuration to loopback or localhost endpoints.
- Limit event collection, prompts, API responses, and request timeouts.
- Fall back to deterministic analysis when Ollama is unavailable.
