# 部署

Codex External Executor 采用本机优先设计。网关只监听 `127.0.0.1`；外部模型流量只从本机网关发往当前 route 选择的 Provider 或中转站。

## 1. 从源码运行

适合开发、评审和本地测试：

```bash
git clone https://github.com/shrekcg/codex-external-executor.git
cd codex-external-executor
python3 -m unittest discover -s tests -v
python3 skill/external-model-executor/scripts/external_executor.py providers
```

## 2. 安装到当前用户的 Codex

配置并验证 route 后，预览并安装一个原生 Codex 子 Agent profile：

```bash
python3 skill/external-model-executor/scripts/external_executor.py codex preview --route deepseek
python3 skill/external-model-executor/scripts/external_executor.py codex install --route deepseek --apply
```

重启 Codex 后再测试生成的 profile。它不会改变主对话模型，也不会覆盖无关的 Codex profile。

## 3. 后台启动本机网关

Skill 需要时会启动网关。若同一登录会话中会重复执行任务，也可以单独启动：

```bash
python3 skill/external-model-executor/scripts/external_executor.py gateway start
```

网关仍然只在本机工作。用 `validate` 检查状态，并参考 `gateway --help` 使用对应的停止命令。

## 4. OS 用户服务

高级用户可以自行用 macOS `launchd`、Linux `systemd --user` 或 Windows 任务计划包装相同的网关命令。本项目不会自动安装系统服务，因为服务归属、Python 路径、日志保留和凭据暴露应由用户控制。

创建服务时必须保持：

- 只绑定 `127.0.0.1`，不能绑定局域网或公网地址；
- 通过环境管理器或安全的本地命令提供凭据，不把凭据写入 service 文件；
- 使用专用用户和受限文件权限；
- 先测试重启行为与 API Key 可用性，再长期运行。

## 移除

先预览，再应用；共享 Skill 文件会保留：

```bash
python3 skill/external-model-executor/scripts/external_executor.py codex uninstall --route deepseek
python3 skill/external-model-executor/scripts/external_executor.py codex uninstall --route deepseek --apply
```
