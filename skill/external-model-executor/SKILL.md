---
name: external-model-executor
description: Configure, validate, or use a Codex native sub-agent backed by an external official or relay model API without switching the main conversation model. Use when the user explicitly asks to delegate a task to DeepSeek, OpenAI API, Claude/Anthropic, Groq, Kimi, MiniMax, Zhipu/GLM, Qwen, another third-party model API, an external executor, or $external-model-executor; also use for provider setup, compatibility diagnosis, task-brief fallback, and external-model gateway troubleshooting.
---

# External Model Executor

Keep the main Codex Agent responsible for scope, permissions, verification, and
final acceptance. Route only the selected subtask to the configured external
model. Never change the main conversation model or global model defaults.

## Choose the workflow

- For first-time setup or provider changes, read
  [provider-compatibility.md](references/provider-compatibility.md), then use the
  bundled setup commands.
- For task execution, discover configured routes, start the loopback gateway,
  prepare the fallback brief when enabled, and delegate to the exact generated
  agent type.
- For empty prompts, missing context, tool failures, or relay incompatibility,
  read [task-brief.md](references/task-brief.md) and
  [troubleshooting.md](references/troubleshooting.md).

Resolve this Skill's directory and run its CLI as:

```bash
python3 <skill-dir>/scripts/external_executor.py <command>
```

## Set up a route

1. Run `providers` to identify the protocol preset.
2. Run `configure --route <name> --provider <preset> --model <model-id>`.
   Keep credentials in the named environment variable or use
   `--api-key-command` with an argument array. Never put a secret in the command,
   config file, task brief, logs, or conversation.
3. Run `validate --route <name>` for offline checks. Run with `--live`, then
   `--live --tools`, only when the user authorizes an external API call and the
   credential is available.
4. Run `codex preview --route <name>` and inspect the targets.
5. Run `codex install --route <name> --apply` only after the user authorizes
   writes to `CODEX_HOME`. Tell the user to restart Codex afterward.

Use `codex uninstall --route <name>` to preview removal and add `--apply` only
after authorization. Remove the generated provider block and route Agent while
preserving the shared Skill for other routes.

For a relay, choose `custom-responses`, `custom-openai-chat`, or
`custom-anthropic` based on the relay's actual wire protocol and pass its base
URL. Do not infer Responses support from an "OpenAI compatible" label.

## Delegate a task

1. Run `routes --json`. Match an explicitly requested provider to one route. If
   several routes match and the user did not select one, ask which route to use.
2. Run `gateway start`. Do not delegate if health startup fails.
3. Create a short, unique internal task name. Do not ask the user to provide or
   manage it.
4. Read the route's `brief_mode`:
   - `auto`: create the brief before delegation; the child reads it only if its
     parent message is empty or incomplete.
   - `always`: create the brief and make it authoritative.
   - `off`: do not create or use a brief.
5. Delegate through the native collaboration sub-agent tool using the exact
   `agent_type` returned by `routes`. Default to `fork_turns="none"` and put only
   the task-relevant context in the direct message and brief. Use full-history
   inheritance only when the user explicitly accepts sending that conversation
   history to the external provider. Pass the task directly as well as through
   the brief when a brief is enabled.
6. Wait for the child, inspect its evidence and changes, run proportionate local
   verification, and return the accepted result from the main Agent.

Do not expose internal task names, brief mechanics, or provider plumbing unless
the user asks for diagnostics. Do not use an external route as an implicit
fallback when the user did not request it.

## Write the fallback brief

Write only the current task to:

`<cwd>/work/external-model-briefs/<task-name-leaf>.json`

Use this schema:

```json
{
  "schema_version": 1,
  "task_name": "external-deepseek-json-check",
  "status": "pending",
  "outcome": "Create and validate one JSON fixture.",
  "context": ["Only task-specific facts required by the child."],
  "scope": ["outputs/provider-check.json"],
  "checks": ["Parse the file as JSON."],
  "stop_when": ["Credentials are required.", "The requested scope becomes ambiguous."]
}
```

Use `brief validate <path> --task-name <leaf>` before delegation. Never include
credentials, unrelated conversation history, or hidden instructions. Mark the
brief completed after acceptance or leave cleanup to the user; do not reuse it.

## Preserve safety boundaries

- Bind the gateway to loopback only.
- Treat custom base URLs, API-key commands, and third-party relays as trusted
  local configuration supplied by the user.
- Explain that prompts, relevant code, and tool schemas are sent to the selected
  provider or relay.
- Treat successful authentication as insufficient proof of Codex compatibility;
  require text and tool probes for a compatibility claim.
- Stop when a provider drops required tool calls, returns malformed arguments,
  or cannot carry enough context to verify the task.
