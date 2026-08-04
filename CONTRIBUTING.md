# 贡献指南

保持改动与 Provider 无关，并以能力为基础。新增 Provider preset 时必须链接官方文档，标明真实协议，不写入固定凭据；如果新增转换行为，还要补充离线测试。

提交前运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile skill/external-model-executor/scripts/external_executor.py \
  skill/external-model-executor/scripts/external_executor_lib/*.py
```

不要提交包含用户提示词、API Key、私有 URL 或专有源代码的真实 API 响应。
