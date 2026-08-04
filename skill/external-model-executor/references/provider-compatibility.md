# Provider compatibility

## Provider groups

| Group | Built-in presets |
|---|---|
| International official APIs | `openai`, `anthropic`, `groq` |
| China official APIs | `deepseek`, `kimi`, `minimax-cn`, `minimax-global`, `zhipu`, `qwen-cn`, `qwen-global` |
| Third-party or self-hosted APIs | `custom-responses`, `custom-openai-chat`, `custom-anthropic` |

The category is only a discovery aid. Always select a route by the endpoint's actual protocol and then validate it live.

## Routing classes

| Class | Gateway behavior | Provider examples |
|---|---|---|
| Native Responses | Preserve the Responses request and stream; remove only fields known to be unsupported by that preset | OpenAI, DeepSeek, Groq, Responses-compatible relays |
| OpenAI Chat | Convert Responses input and tools to Chat Completions, then convert text and tool calls back | Kimi, MiniMax, Zhipu, Qwen, Chat-compatible relays |
| Anthropic Messages | Convert Responses messages and tools to Messages blocks, then convert text and `tool_use` back | Anthropic Claude, Anthropic-compatible relays |

"OpenAI compatible" often means Chat Completions compatibility, not Responses
compatibility. Select the class from the documented endpoint, not marketing
language.

## Built-in presets

| Preset | Protocol | Default credential source | Important note |
|---|---|---|---|
| `openai` | Responses | `OPENAI_API_KEY` | Direct Responses path |
| `deepseek` | Responses | `DEEPSEEK_API_KEY` | Drops unsupported stored-state and encrypted-reasoning requests |
| `groq` | Responses | `GROQ_API_KEY` | Model-level Responses and tool support can differ |
| `anthropic` | Anthropic Messages | `ANTHROPIC_API_KEY` | Requires protocol translation |
| `kimi` | OpenAI Chat | `MOONSHOT_API_KEY` | Requires protocol translation |
| `minimax-cn`, `minimax-global` | OpenAI Chat | `MINIMAX_API_KEY` | Region-specific base URLs |
| `zhipu` | OpenAI Chat | `ZAI_API_KEY` | Requires protocol translation |
| `qwen-cn`, `qwen-global` | OpenAI Chat | `DASHSCOPE_API_KEY` | Prefer the user's current regional/workspace URL |
| `custom-responses` | Responses | `EXTERNAL_MODEL_API_KEY` | Live probe required |
| `custom-openai-chat` | OpenAI Chat | `EXTERNAL_MODEL_API_KEY` | Live text and tool probes required |
| `custom-anthropic` | Anthropic Messages | `EXTERNAL_MODEL_API_KEY` | Live text and tool probes required |

## TokenDance relay example

TokenDance is an example of the third-party relay category, not a hard-coded provider integration. If its endpoint supports Responses, configure it through the generic preset:

```bash
python3 scripts/external_executor.py configure \
  --route tokendance-deepseek \
  --provider custom-responses \
  --model deepseek-v4-flash-0731 \
  --base-url https://tokendance.space/gateway/v1 \
  --api-key-env TOKENDANCE_API_KEY
```

Verify the relay's live protocol, model name, tool support, pricing, and data policy before installing the route. Do not put its API key in a Skill prompt or configuration file.

Model IDs and provider capability details change independently of this project.
Require the user to supply the model ID and verify it live instead of embedding a
"latest" model in the Skill.

## Compatibility levels

1. **Configured**: config parses and the route resolves.
2. **Reachable**: authentication succeeds and a text probe returns.
3. **Tool-capable**: the provider returns a valid function call.
4. **Codex-capable**: a real child task can read files, call tools, modify an
   allowed file, and return verifiable evidence.

Do not describe levels 1-3 as a fully verified Codex integration.

## Primary documentation used for the presets

- Codex custom model provider configuration:
  <https://learn.chatgpt.com/docs/config-file/config-reference>
- OpenAI Responses API: <https://developers.openai.com/api/reference/resources/responses/methods/create>
- DeepSeek Responses API: <https://api-docs.deepseek.com/guides/responses_api/>
- Anthropic Messages API: <https://platform.claude.com/docs/en/api/messages>
- Groq OpenAI and Responses compatibility: <https://console.groq.com/docs/openai>
- Kimi Chat Completions: <https://platform.kimi.com/docs/api/chat>
- MiniMax API overview: <https://platform.minimaxi.com/docs/api-reference/api-overview>
- Zhipu OpenAI compatibility: <https://docs.bigmodel.cn/cn/guide/develop/openai/introduction>
- Qwen OpenAI Chat compatibility: <https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope>
