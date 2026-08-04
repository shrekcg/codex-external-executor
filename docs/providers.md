# Provider catalog

Codex External Executor routes by protocol compatibility. A provider name or an "OpenAI-compatible" label is not enough: it must be matched to the actual endpoint the account is allowed to use.

## International official APIs

| Provider | Preset | Gateway path | Credential environment variable |
|---|---|---|---|
| OpenAI | `openai` | Native Responses | `OPENAI_API_KEY` |
| Anthropic Claude | `anthropic` | Anthropic Messages adapter | `ANTHROPIC_API_KEY` |
| Groq | `groq` | Native Responses | `GROQ_API_KEY` |

## China official APIs

| Provider | Preset | Gateway path | Credential environment variable |
|---|---|---|---|
| DeepSeek | `deepseek` | Native Responses with narrow field filtering | `DEEPSEEK_API_KEY` |
| Kimi / Moonshot | `kimi` | OpenAI Chat adapter | `MOONSHOT_API_KEY` |
| MiniMax (China) | `minimax-cn` | OpenAI Chat adapter | `MINIMAX_API_KEY` |
| MiniMax (global) | `minimax-global` | OpenAI Chat adapter | `MINIMAX_API_KEY` |
| Zhipu GLM | `zhipu` | OpenAI Chat adapter | `ZAI_API_KEY` |
| Alibaba Qwen (China) | `qwen-cn` | OpenAI Chat adapter | `DASHSCOPE_API_KEY` |
| Alibaba Qwen (global) | `qwen-global` | OpenAI Chat adapter | `DASHSCOPE_API_KEY` |

The preset supplies the endpoint family and safe defaults. You supply the current model ID; do not rely on an embedded `latest` alias.

## Third-party relays and self-hosted endpoints

| Endpoint really exposes | Use this preset | Required evidence |
|---|---|---|
| `/v1/responses` | `custom-responses` | A live text probe, then a tool probe |
| `/v1/chat/completions` | `custom-openai-chat` | A live text probe, tool probe, and child-task smoke test |
| `/v1/messages` | `custom-anthropic` | A live text probe, tool probe, and child-task smoke test |

### TokenDance example

The following uses TokenDance as a user-supplied relay example. It is not a vendor endorsement or a guarantee that any model remains available. Confirm the endpoint, current model ID, billing, and data policy with the relay before use.

```bash
python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route tokendance-deepseek \
  --provider custom-responses \
  --model deepseek-v4-flash-0731 \
  --base-url https://tokendance.space/gateway/v1 \
  --api-key-env TOKENDANCE_API_KEY

python3 skill/external-model-executor/scripts/external_executor.py validate \
  --route tokendance-deepseek --live --tools
```

If the relay advertises only OpenAI Chat compatibility, select `custom-openai-chat` instead. Never put the relay key in the command, config, or repository.

## Compatibility levels

1. **Configured**: local config parses and the route resolves.
2. **Reachable**: authentication succeeds and a text probe returns.
3. **Tool-capable**: the provider returns a valid function call.
4. **Codex-capable**: a real child task can read files, call tools, change an allowed file, and return verifiable evidence.

Levels 1–3 are useful diagnostics, but only level 4 justifies relying on a route for normal Codex task execution.

## Provider documentation

The initial presets were based on the providers' published API documentation:

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [DeepSeek Responses API](https://api-docs.deepseek.com/guides/responses_api/)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages)
- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [Kimi Chat Completions](https://platform.kimi.com/docs/api/chat)
- [MiniMax API overview](https://platform.minimaxi.com/docs/api-reference/api-overview)
- [Zhipu OpenAI compatibility](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)
- [Qwen OpenAI compatibility](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)
