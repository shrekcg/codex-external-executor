# Task-brief fallback

## Why it exists

Codex normally sends the parent task through the native collaboration message.
An external Responses implementation or relay can accept the HTTP request while
still dropping or rejecting parts of Codex's input, including encrypted
reasoning content, provider-specific message items, or tool history. The child
can then start with an empty or incomplete task even though authentication and a
simple text probe succeeded.

The brief provides a small, deterministic plaintext handoff inside the current
workspace. It does not replace the API adapter and does not grant permissions.

## Modes

- `auto` is the reliability default. The parent creates a matching brief, while
  the child reads it only when the collaboration message is unusable.
- `always` makes the brief the explicit contract. Use it for relays known to
  alter messages or for repeatable workflows.
- `off` keeps all task context in the native message. Use it for trusted,
  verified Responses providers or projects where plaintext workspace handoff is
  unacceptable.

## Matching rules

The child may read only the file whose basename exactly matches the leaf of its
own task name. It must require `schema_version: 1`, an exact `task_name`, and
`status: pending`. It must never scan the brief directory for alternatives.

These rules prevent stale or unrelated briefs from becoming instructions.

## Privacy and caching

The brief is plaintext in the workspace and can contain project facts. Never put
credentials, secret file contents, or unrelated conversation history in it.
Projects should ignore `work/external-model-briefs/` when briefs are temporary.

Creating a brief does not by itself send its contents to the provider. If the
child reads it, the resulting tool output becomes later model input. Stable
system instructions and tool schemas can still be cached, but task-specific
brief content normally changes and should not be expected to hit a provider's
prompt cache.

## Failure behavior

Stop and return control to the parent when the brief is missing, malformed,
mismatched, already completed, or requests work beyond the child's inherited
permissions.
