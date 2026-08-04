# Provider 兼容性

## Provider 分组

| 分组 | 内置 preset |
|---|---|
| 海外官方 API | `openai`、`anthropic`、`groq` |
| 国内官方 API | `deepseek`、`kimi`、`minimax-cn`、`minimax-global`、`zhipu`、`qwen-cn`、`qwen-global` |
| 第三方或自建 API | `custom-responses`、`custom-openai-chat`、`custom-anthropic` |

分组只用于发现。始终按端点真实协议选择 route，并现场验证。

## 路由类别

| 类别 | 网关行为 | Provider 示例 |
|---|---|---|
| 原生 Responses | 保留请求并流式转发，只移除该 preset 已知不支持的字段 | OpenAI、DeepSeek、Groq、Responses 中转 |
| OpenAI Chat | 转换 Responses input 和工具，完成后再把文本和工具调用转换回来 | Kimi、MiniMax、智谱、千问、Chat 中转 |
| Anthropic Messages | 转换 Responses 消息和工具，完成后把文本与 `tool_use` 转换回来 | Claude、Anthropic 兼容中转 |

“OpenAI 兼容”通常只代表 Chat Completions，不一定代表 Responses。以文档中的实际端点为准。

## 内置 preset

| Preset | 协议 | 默认凭据来源 | 重要说明 |
|---|---|---|---|
| `openai` | Responses | `OPENAI_API_KEY` | 直接透传 |
| `deepseek` | Responses | `DEEPSEEK_API_KEY` | 移除不支持的状态与加密推理请求 |
| `groq` | Responses | `GROQ_API_KEY` | 模型级 Responses 与工具能力可能不同 |
| `anthropic` | Anthropic Messages | `ANTHROPIC_API_KEY` | 需要协议转换 |
| `kimi` | OpenAI Chat | `MOONSHOT_API_KEY` | 需要协议转换 |
| `minimax-cn`、`minimax-global` | OpenAI Chat | `MINIMAX_API_KEY` | 区域端点不同 |
| `zhipu` | OpenAI Chat | `ZAI_API_KEY` | 需要协议转换 |
| `qwen-cn`、`qwen-global` | OpenAI Chat | `DASHSCOPE_API_KEY` | 优先使用当前区域与工作区 URL |
| `custom-responses` | Responses | `EXTERNAL_MODEL_API_KEY` | 必须 live 验证 |
| `custom-openai-chat` | OpenAI Chat | `EXTERNAL_MODEL_API_KEY` | 必须做文本与工具探测 |
| `custom-anthropic` | Anthropic Messages | `EXTERNAL_MODEL_API_KEY` | 必须做文本与工具探测 |

模型 ID 和 Provider 能力会独立变化。要求用户提供模型 ID 并现场验证，不要在 Skill 中写死 `latest`。

## TokenDance 中转示例

TokenDance 是第三方中转类别的示例，不是硬编码的 Provider 集成。若端点支持 Responses，可用通用 preset：

```bash
python3 scripts/external_executor.py configure \
  --route tokendance-deepseek \
  --provider custom-responses \
  --model deepseek-v4-flash-0731 \
  --base-url https://tokendance.space/gateway/v1 \
  --api-key-env TOKENDANCE_API_KEY
```

安装前验证真实协议、模型名、工具支持、价格和数据政策。不要把 API Key 放入 Skill prompt 或配置文件。

## 兼容性分级

1. **Configured**：配置可解析，route 可解析。
2. **Reachable**：认证成功，文本探测返回。
3. **Tool-capable**：Provider 返回合法函数调用。
4. **Codex-capable**：真实子任务可以读文件、调用工具、完成限定变更并返回证据。

不要把 1–3 级描述为完整 Codex 集成。

## 主要文档

- [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [DeepSeek Responses API](https://api-docs.deepseek.com/guides/responses_api/)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages)
- [Groq OpenAI 兼容](https://console.groq.com/docs/openai)
- [Kimi Chat Completions](https://platform.kimi.com/docs/api/chat)
- [MiniMax API 概览](https://platform.minimaxi.com/docs/api-reference/api-overview)
- [智谱 OpenAI 兼容](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)
- [千问 OpenAI 兼容](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)
