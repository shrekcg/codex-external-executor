# Codex External Executor

This repository is the English companion page for the Chinese-first README. It provides the same setup and safety information for international contributors.

Use an official or third-party model API for one selected Codex child task without switching the main conversation. The main Codex Agent remains responsible for scope, permissions, verification, and final acceptance.

See the [Chinese README](README.md), [provider catalog](docs/providers.md), [best practices](docs/best-practices.md), [architecture](docs/architecture.md), [deployment](docs/deployment.md), and [limitations](docs/limitations.md).

```bash
python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route deepseek \
  --provider deepseek \
  --model deepseek-v4-flash \
  --api-key-env DEEPSEEK_API_KEY
python3 skill/external-model-executor/scripts/external_executor.py validate \
  --route deepseek --live --tools
python3 skill/external-model-executor/scripts/external_executor.py codex install \
  --route deepseek --apply
```

The repository uses a local loopback gateway and supports native Responses, OpenAI Chat Completions, Anthropic Messages, third-party relays, and self-hosted endpoints. Never commit credentials or send sensitive code to an upstream you have not reviewed.
