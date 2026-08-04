# Provider 清单

Codex External Executor 按真实协议兼容性路由。Provider 名称或“OpenAI 兼容”标签并不足够，必须匹配当前账号实际可用的端点。

## 海外官方 API

| Provider | Preset | 网关路径 | 凭据环境变量 |
|---|---|---|---|
| OpenAI | `openai` | 原生 Responses | `OPENAI_API_KEY` |
| Anthropic Claude | `anthropic` | Anthropic Messages 适配器 | `ANTHROPIC_API_KEY` |
| Groq | `groq` | 原生 Responses | `GROQ_API_KEY` |

## 国内官方 API

| Provider | Preset | 网关路径 | 凭据环境变量 |
|---|---|---|---|
| DeepSeek | `deepseek` | 原生 Responses，并做有限字段过滤 | `DEEPSEEK_API_KEY` |
| Kimi / Moonshot | `kimi` | OpenAI Chat 适配器 | `MOONSHOT_API_KEY` |
| MiniMax（国内） | `minimax-cn` | OpenAI Chat 适配器 | `MINIMAX_API_KEY` |
| MiniMax（国际） | `minimax-global` | OpenAI Chat 适配器 | `MINIMAX_API_KEY` |
| 智谱 GLM | `zhipu` | OpenAI Chat 适配器 | `ZAI_API_KEY` |
| 阿里千问（国内） | `qwen-cn` | OpenAI Chat 适配器 | `DASHSCOPE_API_KEY` |
| 阿里千问（国际） | `qwen-global` | OpenAI Chat 适配器 | `DASHSCOPE_API_KEY` |

Preset 只提供端点族和安全默认值；模型 ID 由用户填写并现场验证，不依赖内置 `latest` 别名。

## 第三方中转与自建端点

| 实际端点 | 使用 preset | 最低验证要求 |
|---|---|---|
| `/v1/responses` | `custom-responses` | 文本探测，再做工具探测 |
| `/v1/chat/completions` | `custom-openai-chat` | 文本、工具和子任务冒烟 |
| `/v1/messages` | `custom-anthropic` | 文本、工具和子任务冒烟 |

### TokenDance 示例

以下把 TokenDance 作为用户提供的中转示例，不代表供应商背书，也不保证模型持续可用。使用前请确认端点、模型 ID、计费和数据政策：

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

如果中转站只有 OpenAI Chat 兼容端点，就选择 `custom-openai-chat`。不要把中转 Key 写进命令、配置或仓库。

## 兼容性分级

1. **Configured**：本地配置可解析，route 可解析。
2. **Reachable**：认证成功，文本探测返回。
3. **Tool-capable**：Provider 返回合法函数调用。
4. **Codex-capable**：真实子任务可以读文件、调用工具、完成限定变更并返回可验证证据。

只有第 4 级才足以支持日常 Codex 任务执行。

## Provider 官方文档

内置 preset 参考了各 Provider 发布的 API 文档：

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [DeepSeek Responses API](https://api-docs.deepseek.com/guides/responses_api/)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages)
- [Groq OpenAI 兼容](https://console.groq.com/docs/openai)
- [Kimi Chat Completions](https://platform.kimi.com/docs/api/chat)
- [MiniMax API 概览](https://platform.minimaxi.com/docs/api-reference/api-overview)
- [智谱 OpenAI 兼容](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)
- [千问 OpenAI 兼容](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)
