# Security policy

## Report a vulnerability

Do not open a public issue for a vulnerability that could expose credentials,
prompts, source code, or local files. Contact the repository owner privately and
include a minimal reproduction without real secrets.

## Deployment guidance

- Keep the gateway bound to loopback. The program rejects non-loopback hosts.
- Store API keys in environment variables or an OS credential manager.
- Never put credentials in project configuration, briefs, logs, issues, or test
  fixtures.
- Review any `api_key_command` and custom base URL before using a shared config.
- Assume the selected official provider or relay can read prompts, relevant code,
  and tool definitions sent to it.
- Default to task-local context. Do not inherit the full main conversation into
  an external child unless the user accepts that disclosure.
- Use `brief_mode: off` when plaintext workspace handoff is not acceptable.
- Do not use an untrusted relay for proprietary code or personal data.

The installer and uninstaller preview their targets unless `--apply` is passed.
They back up changed Codex configuration, Agent profiles, and replaced Skill
directories before modifying or removing managed files.
