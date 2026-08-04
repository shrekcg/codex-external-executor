# Codex External Executor

<p align="center"><img src="assets/readme/hero.svg" alt="Codex 保持主控，将指定子任务通过本地网关路由到外部 API" width="100%"></p>

在不切换 Codex 主对话模型的情况下，把某一次任务临时交给官方或第三方模型 API 驱动的原生子 Agent。

主 Agent 始终负责权限、范围、验证和最终交付；只有明确选中的子任务使用外部 API。英文完整说明见 [README.md](README.md)。

## 这套方案做了什么

- 不指定外部 route 时，原有 Codex 与 Team Mode 工作流完全不变。
- 指定 route 时，为该 route 使用一个生成的 Codex 原生子 Agent 配置，而非全局切换主模型。
- 本机回环网关在 Responses、OpenAI Chat Completions、Anthropic Messages 三种协议之间适配。
- API Key 不写入仓库或 Codex provider 配置。

日常调用不需要了解内部任务名、父子 Agent 关系或任务简报：

```text
使用 $external-model-executor，让 DeepSeek route 在当前项目创建并验证一个简单 JSON 文件，完成后告诉我路径和验证结果。
```

## Provider 分类

| 分类 | 内置预设 | 协议路径 |
|---|---|---|
| 海外官方 API | OpenAI、Anthropic Claude、Groq | Responses / Anthropic Messages |
| 国内官方 API | DeepSeek、Kimi、MiniMax、智谱 GLM、阿里千问 | Responses / OpenAI Chat Completions |
| 第三方中转或自建 API | 任意兼容 Responses、OpenAI Chat、Anthropic 的端点 | 显式选择通用适配器 |

完整的预设、区域端点和验证分级见 [Provider catalog](docs/providers.md)。

### TokenDance 示例

TokenDance 作为第三方中转站接入，不需要写死为专用 provider。若目标模型真实支持 Responses 端点，可以使用通用 Responses 适配器：

```bash
python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route tokendance-deepseek \
  --provider custom-responses \
  --model deepseek-v4-flash-0731 \
  --base-url https://tokendance.space/gateway/v1 \
  --api-key-env TOKENDANCE_API_KEY
```

中转站的模型可用性、协议、工具能力和隐私条款都可能变化；安装 route 前务必进行 live 验证。

## 架构与部署形式

<p align="center"><img src="assets/readme/architecture.svg" alt="Codex External Executor 的控制层、适配层和 Provider 层" width="100%"></p>

Skill 负责发起配置或委派；生成的原生子 Agent 固定到指定 route；只监听 `127.0.0.1` 的本地网关完成协议透传或转换；主 Agent 最后核验结果。

当前支持四种部署形态：

1. 从源码目录运行，适合开发与本地测试。
2. 安装到当前用户的 Codex 配置，适合日常使用。
3. 用 CLI 后台启动本机回环网关，适合一个用户会话中的重复调用。
4. 高级用户可自行用 `launchd`、`systemd` 或 Windows 任务计划包装本机网关；项目不会自动安装系统服务。

详细命令与边界见 [部署说明](docs/deployment.md) 和 [架构说明](docs/architecture.md)。

## 快速开始

```bash
git clone https://github.com/YOUR_ACCOUNT/codex-external-executor.git
cd codex-external-executor

python3 skill/external-model-executor/scripts/external_executor.py providers

python3 skill/external-model-executor/scripts/external_executor.py configure \
  --route deepseek \
  --provider deepseek \
  --model deepseek-v4-flash \
  --api-key-env DEEPSEEK_API_KEY

python3 skill/external-model-executor/scripts/external_executor.py validate --route deepseek

python3 skill/external-model-executor/scripts/external_executor.py codex install \
  --route deepseek --apply
```

重启 Codex 后，在新会话中使用前述调用示例。

## 验证、安全与限制

`HTTP 200` 只能证明连通，不能证明足以可靠执行 Codex 子任务。应依次验证配置解析、文本调用、工具调用和真实子任务。

```bash
# 不发起外部请求
python3 skill/external-model-executor/scripts/external_executor.py validate

# 发起外部文本与工具探测，会消耗 API 额度
python3 skill/external-model-executor/scripts/external_executor.py validate --route deepseek --live --tools

# 纯本地离线测试
python3 -m unittest discover -s tests -v
```

任务简报仅在上游 API 或中转站不能可靠保留原生协作消息时作为降级机制。默认只传递完成任务所需的上下文，不自动发送主对话完整历史。简报是 workspace 中的明文文件，不能包含 API Key、秘密文件内容或无关历史。

外部 API 费用、缓存和数据保留均由上游 provider 控制；Codex 主 Agent 的调度与最终核验仍会使用 Codex 额度。使用敏感代码前，请阅读 [限制说明](docs/limitations.md) 和 [安全说明](SECURITY.md)。

## 开发与许可

项目采用开放 Agent Skills 的可移植目录：精简 `SKILL.md`、按需加载的 `references/`、可执行 `scripts/` 与离线测试。

贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，许可证为 [MIT](LICENSE)。
