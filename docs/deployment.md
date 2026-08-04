# Deployment

Codex External Executor is deliberately local-first. Its gateway listens only on `127.0.0.1`; external model traffic leaves the machine only from that gateway to the provider or relay selected for one route.

## 1. Source checkout

Use this form for development, review, and local testing.

```bash
git clone https://github.com/YOUR_ACCOUNT/codex-external-executor.git
cd codex-external-executor
python3 -m unittest discover -s tests -v
python3 skill/external-model-executor/scripts/external_executor.py providers
```

## 2. User-local Codex integration

After configuring and validating a route, generate one native Codex child-agent profile and install it for the current user:

```bash
python3 skill/external-model-executor/scripts/external_executor.py codex preview --route deepseek
python3 skill/external-model-executor/scripts/external_executor.py codex install --route deepseek --apply
```

Restart Codex before testing the generated profile. This does not change the main conversation's model or overwrite unrelated Codex profiles.

## 3. Detached loopback gateway

The Skill starts the gateway when needed. For repeated tasks in one logged-in user session, it can also be started separately:

```bash
python3 skill/external-model-executor/scripts/external_executor.py gateway start
```

The gateway remains local. Check it with the validation command and stop it using the matching CLI command documented by `gateway --help`.

## 4. OS-managed user service

Advanced users may wrap the same gateway command in a per-user `launchd` (macOS), `systemd --user` (Linux), or Windows Task Scheduler definition. This repository intentionally does not install a system service: service ownership, Python path, log retention, and credential exposure must remain under the user's control.

When creating a service, keep these invariants:

- bind only to `127.0.0.1`, never a LAN or public address;
- pass credentials through an environment manager or secure local command, not a checked-in service file;
- use a dedicated user account and restrictive file permissions;
- test restart behavior and API-key availability before relying on it.

## Removal

Preview removal first; then apply it. Shared Skill files remain intact.

```bash
python3 skill/external-model-executor/scripts/external_executor.py codex uninstall --route deepseek
python3 skill/external-model-executor/scripts/external_executor.py codex uninstall --route deepseek --apply
```
