---
name: external-model-executor
description: 在不切换 Codex 主对话模型的情况下，配置、验证或使用由官方 API、第三方中转或自建 API 驱动的 Codex 原生子 Agent。用户明确提到 DeepSeek、OpenAI API、Claude、Groq、Kimi、MiniMax、智谱、千问、外部执行器或 $external-model-executor 时使用；也用于 Provider 配置、兼容性诊断、任务简报降级和网关排错。
---

# External Model Executor

主 Codex Agent 始终负责范围、权限、验证和最终交付；只有用户明确选中的子任务使用外部 route。绝不要修改主对话模型或全局模型默认值。

## 选择工作流

- 首次配置或更换 Provider：先阅读 `references/provider-compatibility.md`，再使用内置 CLI。
- 执行任务：发现已配置 route，启动本机回环网关，按需创建任务简报，然后委派给精确的原生 Agent 类型。
- 遇到空提示词、上下文缺失、工具失败或中转不兼容：阅读 `references/task-brief.md` 和 `references/troubleshooting.md`。

解析 Skill 目录后，按以下形式运行 CLI：

```bash
python3 <skill-dir>/scripts/external_executor.py <command>
```

## 配置 route

1. 运行 `providers`，确认协议 preset。
2. 运行 `configure --route <name> --provider <preset> --model <model-id>`。凭据只放在环境变量或 `--api-key-command` 参数数组中，不得放进命令、配置、简报、日志或对话。
3. 运行 `validate --route <name>` 做离线检查；只有用户授权外部请求且凭据可用时，才运行 `--live` 和 `--live --tools`。
4. 运行 `codex preview --route <name>` 检查目标。
5. 用户授权写入 `CODEX_HOME` 后，运行 `codex install --route <name> --apply`，然后提醒用户重启 Codex。

中转站必须根据真实协议选择 `custom-responses`、`custom-openai-chat` 或 `custom-anthropic`。不能仅依据“OpenAI 兼容”推断 Responses 支持。

## 委派任务

1. 运行 `routes --json`，把用户明确指定的 Provider 匹配到 route；多个候选且用户没有选择时，询问选择。
2. 运行 `gateway start`；网关健康检查失败时不要委派。
3. 创建简短、唯一的内部任务名，不要求用户提供或管理。
4. 根据 route 的 `brief_mode` 处理简报：`auto` 在原生消息不完整时备用，`always` 作为明确合同，`off` 完全不创建。
5. 通过原生协作子 Agent 工具委派，默认使用 `fork_turns="none"`，只传递任务所需上下文。只有用户明确接受把完整对话发送给外部 Provider 时，才继承完整历史。启用简报时同时把任务直接传入并写入简报。
6. 等待子 Agent，检查证据和变更，按比例运行本地验证，再向用户返回主 Agent 接受的结果。

不要向用户暴露内部任务名、简报机制或 Provider plumbing，除非用户主动要求诊断。用户未指定外部 route 时，不要把它当作隐式 fallback。

## 任务简报

启用时，只写入：`<cwd>/work/external-model-briefs/<task-name-leaf>.json`。它只能描述当前任务，不能包含凭据、秘密文件内容、无关历史或隐藏指令。使用 `brief validate <path> --task-name <leaf>` 校验后再委派；任务接受后标记完成，不要复用旧简报。

## 安全边界

- 网关只绑定 loopback。
- 自定义 URL、API-key command 和第三方中转视为用户信任的本地配置。
- 提示词、相关代码和工具 schema 会发送给选中的 Provider 或中转站。
- 认证成功不等于 Codex 兼容；需要文本、工具和真实子任务验证。
- Provider 丢失必需工具调用、返回非法参数或无法携带足够上下文时，停止并把控制权交回主 Agent。
