# Contributing

Keep changes provider-agnostic and capability-based. A new provider preset must
link to primary documentation, identify its real protocol, avoid hard-coded
credentials, and include an offline translation test when it adds behavior.

Run before submitting:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile skill/external-model-executor/scripts/external_executor.py \
  skill/external-model-executor/scripts/external_executor_lib/*.py
```

Do not commit real API responses containing user prompts, API keys, private URLs,
or proprietary source code.
