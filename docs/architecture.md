# 架构

## 组件

1. **Skill 路由器**：判断用户是在配置 route 还是委派任务，不改变主对话模型。
2. **生成的 Agent profile**：把一个原生 Codex 子角色固定到一个 route；多个 Provider 可以生成多个明确 profile。
3. **本机回环网关**：向 Codex 暴露 `/v1/responses`，并把上游凭据留在 Codex provider 配置之外。
4. **协议适配器**：透传 Responses，或把一轮请求转换为 OpenAI Chat Completions / Anthropic Messages。
5. **任务简报**：当原生协作消息为空或被修改时，提供最小任务合同。
6. **主 Agent 验证**：检查子 Agent 的变更与证据后再接受结果。

默认委派不继承主对话完整历史。主 Agent 只构建任务所需的局部上下文，避免把无关内容发送给外部服务。继承完整历史必须由用户明确接受。

## 为什么每个 route 使用独立 Agent profile

Codex 的自定义 Agent profile 在启动时选择 Provider 和模型。route 专用 profile 能让 Provider 选择显式、稳定、可审计，同时不需要在对话中修改全局模型配置。

Codex 发送给网关的模型名是 route 名称；网关再把它解析为上游 Provider、协议、Base URL、凭据来源和真实模型 ID。

## 请求路径

### 原生 Responses

Codex 向本机网关发送 Responses JSON。网关把 route 名称替换成上游模型 ID，只移除该 preset 已知不支持的字段，然后把上游响应流式返回。

### OpenAI Chat Completions

网关把 Responses 消息、函数调用、工具输出和自定义工具转换为 Chat Completions。上游完成一轮后，网关再把文本或工具调用转换为 Responses 输出项，并返回 JSON 或 SSE 事件序列。

### Anthropic Messages

网关转换 system 文本、消息、工具定义、`tool_use` 和 `tool_result`。返回的文本和工具调用会使用同一套下游构建器转换为 Responses 输出项。

## 信任边界

- 主 Agent 与子 Agent 共享 Codex 工作区和沙箱策略。
- 网关只绑定 loopback 地址。
- 配置的上游会收到选中的提示词上下文和工具 schema。
- API Key 命令与自定义 URL 属于用户信任的本地配置。
- 任务简报是 workspace 明文文件，不会扩大权限。
