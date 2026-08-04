# Limitations and design decisions

## Responses is a family of behaviors, not only an endpoint name

Providers can expose `/responses` while omitting state, encrypted reasoning,
custom tools, built-in tools, or particular SSE events. Presets document known
differences, while live probes establish current behavior.

## Tool translation is necessarily lossy

OpenAI Chat Completions and Anthropic Messages have function/tool primitives,
but they do not implement every Responses tool type. This gateway translates
ordinary functions and custom text tools. Provider-hosted built-in tools are not
emulated.

Responses custom tools are represented upstream as a function with one string
property, `input`. This works only when the model preserves the tool name and
valid JSON arguments.

## Translated streaming is buffered

Native Responses streams are passed through. For translated protocols, the
gateway currently completes one upstream turn before emitting the downstream
Responses SSE sequence. This prioritizes deterministic tool-call reconstruction
over token-level latency.

## State is reconstructed from Codex input

Translated routes do not implement provider-side `previous_response_id` state.
They convert the input items supplied by Codex on each turn. Relays that drop
history can still fail; brief mode handles only the task contract, not arbitrary
conversation reconstruction.

## Model capability is outside the adapter

The adapter cannot make a text-only model call tools accurately, enlarge a
context window, remove content-policy restrictions, or guarantee valid patches.
The main Agent must keep tasks bounded and verify the output.

## Billing remains separate

External sub-agent tokens are billed by the selected API or relay. The main
Codex Agent still uses the user's Codex plan or configured main-provider billing
for delegation, monitoring, verification, and final output.
