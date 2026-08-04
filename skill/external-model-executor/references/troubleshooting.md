# Troubleshooting

## Gateway does not start

Run `validate` first, then inspect the log path reported by `gateway start`.
Common causes are invalid JSON, a non-loopback host, an occupied port, or an
unsupported protocol name.

## Authentication works but the child receives no task

Use brief mode `auto` or `always`. This is a message-transport compatibility
failure, not an API-key failure.

## Text works but file edits do not

Run `validate --live --tools`. If that succeeds, test a bounded child task. The
provider may still reject custom tools, emit malformed JSON arguments, rename
tools, or fail to continue after tool results.

## Custom `apply_patch` fails

The Chat and Anthropic adapters represent Responses custom tools as ordinary
functions with one string field named `input`, then translate the returned call
back. The upstream model must preserve the tool name and produce valid
arguments. Use normal function tools or a read-only task when the model cannot.

## Streaming appears delayed

Native Responses routes are streamed through. Translated Chat and Anthropic
routes currently buffer one upstream turn and then emit valid Responses SSE
events. Long generations therefore appear after the upstream turn completes.

## A relay claims OpenAI compatibility

Confirm whether it exposes `/responses` or only `/chat/completions`. Use
`custom-responses` for the former and `custom-openai-chat` for the latter. Then
run both text and tool probes.

## Changes are not visible in a new task

Codex discovers Skill and custom Agent configuration at startup. Restart Codex
after `codex install --apply`, then create a new conversation.
