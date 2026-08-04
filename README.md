# Codex External Executor

<p align="center">
  <img src="assets/readme/hero.svg" alt="Codex External Executor: Codex keeps control while one native child agent routes through a local gateway to an official API or relay" width="100%">
</p>

<p align="center"><strong>Use an external model API for one Codex child task—without switching the main conversation.</strong></p>

<p align="center"><a href="README.zh-CN.md">简体中文</a> · <a href="docs/architecture.md">Architecture</a> · <a href="docs/providers.md">Provider catalog</a> · <a href="docs/deployment.md">Deployment</a> · <a href="docs/limitations.md">Limitations</a></p>

Codex External Executor is a reusable Codex Skill for selectively delegating a bounded task to an external model API. Codex remains the parent: it owns permissions, workspace access, verification, and the final response. Only the chosen native child-agent route uses the external provider.

## What it changes

```text
Main Codex conversation  ── stays on its normal model and plan
        │
        └── selected task → generated native child agent → local gateway → external API
```

- Keeps the original Codex workflow intact when no external route is selected.
- Adds one explicit, route-specific native child-agent profile per provider.
- Bridges Codex Responses, OpenAI Chat Completions, and Anthropic Messages APIs.
- Keeps API keys out of Codex provider configuration and out of this repository.

The user-facing invocation stays simple:

```text
Use $external-model-executor and let the DeepSeek route create and validate a
small JSON file in the current project. Return the path and verification result.
```

Internal task names and fallback briefs are implementation details, not prompt requirements for the user.

## Provider catalog

The route is selected by the provider's real wire protocol, not only by an "OpenAI-compatible" label. Model IDs are supplied by the user and validated live, because each provider's catalog changes independently.

| Group | Built-in presets | Protocol path |
|---|---|---|
| International official APIs | OpenAI, Anthropic Claude, Groq | Responses / Anthropic Messages |
| China official APIs | DeepSeek, Kimi, MiniMax, Zhipu GLM, Alibaba Qwen | Responses / OpenAI Chat Completions |
| Third-party or self-hosted APIs | Any Responses-, OpenAI Chat-, or Anthropic-compatible endpoint | Explicit custom adapter |

For the full preset list, regional endpoints, and compatibility levels, see [the provider catalog](docs/providers.md).

### TokenDance relay example

TokenDance is configured as a third-party relay, not as a special hard-coded provider. If its selected model exposes a genuine Responses endpoint, configure it through the generic Responses adapter:

```bash
python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route tokendance-deepseek \
  --provider custom-responses \
  --model deepseek-v4-flash-0731 \
  --base-url https://tokendance.space/gateway/v1 \
  --api-key-env TOKENDANCE_API_KEY
```

Run a live validation before installing the route. A relay can change model availability, protocol support, privacy terms, or tool support without a change to this project.

## Architecture

<p align="center"><img src="assets/readme/architecture.svg" alt="Control plane, adapter plane, and provider plane of Codex External Executor" width="100%"></p>

1. The Skill decides whether to configure a route or delegate a bounded task.
2. A generated native Codex child-agent profile pins that route for the task.
3. A loopback-only gateway accepts Codex Responses traffic.
4. The gateway either passes it through or adapts it to Chat Completions or Anthropic Messages, then converts the result back.
5. The main Codex Agent checks the result before accepting it.

When an upstream API or relay loses native collaboration data, an optional, strict workspace task brief provides the minimum task contract. By default the child gets task-local context, not the complete parent conversation.

## Deployment forms

All forms keep the gateway on the local machine and bind only to `127.0.0.1`. There is no hosted control plane and no global model switch.

| Form | Best for | How it runs |
|---|---|---|
| Source checkout | Contributors and local testing | Run the bundled Python CLI from this repository |
| User-local Codex install | Daily use on one machine | Generate and install one route profile under the local Codex configuration |
| Detached local gateway | Repeated use in a user session | Start the same loopback gateway in the background with the CLI |
| OS-managed local service | Advanced users | Wrap the gateway command in a user-owned `launchd`, `systemd`, or Windows task; never installed automatically |

See [deployment guidance](docs/deployment.md) for commands and boundaries.

## Quick start

Requirements: Python 3.11 or newer and a current Codex installation with native sub-agent support.

```bash
git clone https://github.com/YOUR_ACCOUNT/codex-external-executor.git
cd codex-external-executor

python3 skill/external-model-executor/scripts/external_executor.py providers

python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route deepseek \
  --provider deepseek \
  --model deepseek-v4-flash \
  --api-key-env DEEPSEEK_API_KEY

python3 skill/external-model-executor/scripts/external_executor.py validate --route deepseek

python3 skill/external-model-executor/scripts/external_executor.py codex install \
  --route deepseek --apply
```

Restart Codex and open a new conversation. Use the prompt shown above. The Skill starts the local gateway when needed and delegates through the generated native child-agent profile.

### Configure another official API

```bash
python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route kimi \
  --provider kimi \
  --model kimi-k3 \
  --api-key-env MOONSHOT_API_KEY
```

Use `openai`, `anthropic`, `groq`, `deepseek`, `minimax-cn`, `minimax-global`, `zhipu`, `qwen-cn`, or `qwen-global` in the same way.

### Configure another relay

Choose the relay's actual endpoint shape:

```bash
python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route my-relay \
  --provider custom-openai-chat \
  --model provider/model-id \
  --base-url https://relay.example.com/v1 \
  --api-key-env MY_RELAY_API_KEY
```

Use `custom-responses` only when the relay actually exposes `/responses`. "OpenAI compatible" often means `/chat/completions` only. A narrowly scoped `--drop-request-field <field>` override is available for a Responses relay that rejects an optional Codex field; required execution fields cannot be dropped.

## Validation and safety

```bash
# Parse configuration only; no external call
python3 skill/external-model-executor/scripts/external_executor.py validate

# Text probe; consumes external API quota
python3 skill/external-model-executor/scripts/external_executor.py validate --route deepseek --live

# Function-calling probe; consumes external API quota
python3 skill/external-model-executor/scripts/external_executor.py validate --route deepseek --live --tools

# Local test suite; no external credentials or network required
python3 -m unittest discover -s tests -v
```

No API key belongs in this repository or its JSON configuration. Use an environment variable, or a trusted local command that prints a credential to stdout. The gateway refuses non-loopback binding. Prompts, selected workspace context, and tool schemas are still sent to the configured upstream, so review each provider's privacy and retention terms before using proprietary code.

## Important limitations

- HTTP 200 proves reachability—not full Codex compatibility. Verify text, tools, and a real child task before relying on a route.
- Native Responses providers still differ in supported fields, tools, state, and reasoning metadata.
- Chat and Anthropic adapters translate Codex custom tools into ordinary functions with one `input` string. A model that emits malformed tool arguments cannot be fixed by configuration alone.
- Prompt caching and billing are controlled by the upstream provider. The main Codex Agent still consumes Codex usage for orchestration and final review.

See [limitations](docs/limitations.md) and [SECURITY.md](SECURITY.md) before using an untrusted relay or sensitive repository.

## Development

The repository follows the portable Skill layout used by the open Agent Skills ecosystem: a concise `SKILL.md`, on-demand `references/`, executable `scripts/`, examples, and offline tests. It can be installed manually into Codex or through tools that discover standard Skill directories.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
