# 排错

## 网关无法启动

先运行 `validate`，再检查 `gateway start` 输出的日志路径。常见原因是 JSON 无效、host 非 loopback、端口被占用或 protocol 名称不支持。

## 认证成功但子 Agent 没收到任务

尝试 `brief_mode: auto` 或 `always`。这通常是消息传输兼容性问题，不是 API Key 问题。

## 文本成功但文件修改失败

运行 `validate --live --tools`，通过后再测试范围很小的子任务。Provider 仍可能拒绝自定义工具、返回非法 JSON 参数、重命名工具或无法在工具结果后继续。

## `apply_patch` 失败

Chat 和 Anthropic 适配器会把 Responses 自定义工具表示为带一个 `input` 字符串字段的普通函数，再把调用翻译回来。上游模型必须保留工具名并返回合法参数；不满足时改用普通函数工具或只读任务。

## 流式输出延迟

原生 Responses route 直接流式转发；转换后的 Chat 和 Anthropic route 会缓冲一轮上游响应，再发出合法 Responses SSE 事件，因此长输出会在一轮完成后出现。

## 中转站声称 OpenAI 兼容

确认它提供 `/responses` 还是只有 `/chat/completions`。前者用 `custom-responses`，后者用 `custom-openai-chat`，然后分别做文本和工具探测。

## 新任务看不到变更

Codex 在启动时发现 Skill 和自定义 Agent 配置。执行 `codex install --apply` 后重启 Codex，并新建会话。
