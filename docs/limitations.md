# 限制与设计取舍

## Responses 不只是端点名称

Provider 可能暴露 `/responses`，但不支持状态、加密推理、自定义工具、内置工具或特定 SSE 事件。Preset 记录已知差异，live probe 才能确认当前行为。

## 工具转换存在损耗

OpenAI Chat Completions 和 Anthropic Messages 都有函数/工具原语，但不一定实现 Responses 的全部工具类型。网关只转换普通函数和自定义文本工具，不模拟 Provider 自带工具。

Responses 自定义工具在上游会被表示为只有一个字符串属性 `input` 的函数。只有当模型保留工具名并生成合法 JSON 参数时才可靠。

## 转换协议的流式输出会缓冲

原生 Responses 直接透传。Chat 与 Anthropic 转换路径会先完成一轮上游请求，再发出下游 Responses SSE 序列，优先保证工具调用重建的确定性，而不是 token 级延迟。

## 状态由 Codex 输入重建

转换路径不实现 Provider 侧 `previous_response_id` 状态，而是把 Codex 每轮提供的 input 转换给上游。如果中转站丢弃历史，仍可能失败；brief 只能提供任务合同，不能重建任意对话历史。

## 模型能力不由适配器补齐

适配器不能让纯文本模型准确调用工具、扩大上下文窗口、移除内容策略限制或保证补丁正确。主 Agent 必须限制任务范围并核验输出。

## 计费分开

外部子 Agent token 由选中的 API 或中转站计费。主 Codex Agent 仍会因为委派、监控、核验和最终输出使用 Codex 计划或主 Provider 额度。
