# Architecture

## Components

1. **Skill router**: decides whether the user is configuring a route or
   delegating a task. It never changes the main conversation model.
2. **Generated Agent profile**: fixes one native Codex child role to one route.
   Multiple providers therefore produce multiple explicit Agent profiles.
3. **Loopback gateway**: exposes `/v1/responses` to Codex and keeps upstream
   credentials outside Codex provider configuration.
4. **Protocol adapter**: either passes Responses through or converts one turn to
   OpenAI Chat Completions or Anthropic Messages.
5. **Task brief**: carries a minimal task contract when the native collaboration
   message is empty or altered.
6. **Parent verification**: the main Agent inspects changes and evidence before
   accepting the child result.

The default delegation uses no inherited turn history. The parent builds a
minimal task-local context package so unrelated conversation content is not sent
to the external service. Full-history inheritance is an explicit opt-in.

## Why one Agent profile per route

Codex custom Agent profiles select a model provider and model at startup. A
route-specific profile makes provider selection explicit, auditable, and stable
without mutating global model configuration during a conversation.

The model name sent by Codex is the route name. The gateway resolves that route
to the upstream provider, protocol, base URL, credential source, and real model
ID.

## Request paths

### Native Responses

Codex sends Responses JSON to the loopback gateway. The gateway replaces the
route name with the upstream model ID, removes only preset fields known to be
unsupported, and streams the upstream response back.

### OpenAI Chat Completions

The gateway converts Responses messages, function calls, tool outputs, and
custom tools to Chat Completions. After one upstream turn, it converts text or
tool calls to Responses output items and emits a Responses JSON response or SSE
event sequence.

### Anthropic Messages

The gateway converts system text, messages, tool definitions, `tool_use`, and
`tool_result` blocks. Returned text and tool calls are converted to Responses
items using the same downstream builder.

## Trust boundaries

- The main Agent and child share the Codex workspace and its sandbox policy.
- The gateway binds only to loopback.
- The configured upstream receives selected prompt context and tool schemas.
- API-key commands and custom URLs are trusted local configuration.
- The brief is a plaintext workspace artifact and never expands permissions.
