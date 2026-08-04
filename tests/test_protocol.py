from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "external-model-executor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from external_executor_lib.protocol import (  # noqa: E402
    anthropic_to_response,
    chat_to_response,
    response_sse_events,
    responses_to_anthropic,
    responses_to_chat,
)


class ProtocolTests(unittest.TestCase):
    def test_responses_to_chat_preserves_messages_and_functions(self) -> None:
        payload, custom = responses_to_chat(
            {
                "instructions": "Be precise.",
                "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Hi"}]}],
                "tools": [
                    {
                        "type": "function",
                        "name": "lookup",
                        "description": "Lookup a value",
                        "parameters": {"type": "object", "properties": {"id": {"type": "string"}}},
                    }
                ],
            },
            "upstream-model",
        )
        self.assertEqual(payload["model"], "upstream-model")
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "Be precise."})
        self.assertEqual(payload["messages"][1], {"role": "user", "content": "Hi"})
        self.assertEqual(payload["tools"][0]["function"]["name"], "lookup")
        self.assertEqual(custom, set())

    def test_tool_history_is_reconstructed_for_chat(self) -> None:
        payload, _ = responses_to_chat(
            {
                "input": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "inspect",
                        "arguments": "{}",
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "file contents",
                    },
                ]
            },
            "model",
        )
        self.assertEqual(payload["messages"][0]["role"], "assistant")
        self.assertEqual(payload["messages"][0]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(payload["messages"][1], {"role": "tool", "tool_call_id": "call_1", "content": "file contents"})

    def test_forced_tool_choice_is_translated(self) -> None:
        payload, _ = responses_to_chat(
            {
                "input": "Inspect",
                "tools": [{"type": "function", "name": "inspect", "parameters": {"type": "object"}}],
                "tool_choice": {"type": "function", "name": "inspect"},
            },
            "model",
        )
        self.assertEqual(payload["tool_choice"], {"type": "function", "function": {"name": "inspect"}})

    def test_custom_tool_round_trip(self) -> None:
        request, custom = responses_to_chat(
            {
                "input": "Patch the file",
                "tools": [{"type": "custom", "name": "apply_patch", "description": "Apply a patch"}],
            },
            "model",
        )
        self.assertEqual(custom, {"apply_patch"})
        schema = request["tools"][0]["function"]["parameters"]
        self.assertEqual(schema["required"], ["input"])
        response = chat_to_response(
            {
                "model": "model",
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "apply_patch",
                                        "arguments": json.dumps({"input": "*** Begin Patch"}),
                                    },
                                }
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
            custom,
        )
        item = response["output"][0]
        self.assertEqual(item["type"], "custom_tool_call")
        self.assertEqual(item["input"], "*** Begin Patch")

    def test_anthropic_tool_round_trip(self) -> None:
        request, custom = responses_to_anthropic(
            {
                "instructions": "Use tools.",
                "input": "Inspect the project",
                "tools": [
                    {
                        "type": "function",
                        "name": "inspect",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
            },
            "claude-model",
        )
        self.assertEqual(request["system"], "Use tools.")
        self.assertEqual(request["tools"][0]["name"], "inspect")
        response = anthropic_to_response(
            {
                "model": "claude-model",
                "content": [{"type": "tool_use", "id": "tool_1", "name": "inspect", "input": {}}],
                "usage": {"input_tokens": 8, "output_tokens": 2},
            },
            custom,
        )
        self.assertEqual(response["output"][0]["type"], "function_call")

    def test_sse_has_required_terminal_event(self) -> None:
        response = chat_to_response(
            {
                "model": "model",
                "choices": [{"message": {"content": "done"}}],
                "usage": {},
            },
            set(),
        )
        events = list(response_sse_events(response))
        self.assertEqual(events[0][0], "response.created")
        self.assertIn("response.output_text.delta", [name for name, _ in events])
        self.assertEqual(events[-1][0], "response.completed")


if __name__ == "__main__":
    unittest.main()
