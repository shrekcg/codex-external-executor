"""Translate between Codex Responses payloads and common provider protocols."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterable


class ProtocolError(ValueError):
    """Raised when a request cannot be translated safely."""


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _text_parts(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    values: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind in {"input_text", "output_text", "text"}:
            values.append(str(part.get("text", "")))
    return "\n".join(value for value in values if value)


def _chat_content(content: Any) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind in {"input_text", "output_text", "text"}:
            parts.append({"type": "text", "text": str(part.get("text", ""))})
        elif kind in {"input_image", "image_url"}:
            image_url = part.get("image_url") or part.get("url")
            if image_url:
                parts.append({"type": "image_url", "image_url": {"url": image_url}})
    if not parts:
        return ""
    if all(part["type"] == "text" for part in parts):
        return "\n".join(part["text"] for part in parts)
    return parts


def _tool_definition(tool: dict[str, Any]) -> tuple[dict[str, Any], bool] | None:
    kind = tool.get("type")
    name = tool.get("name")
    if kind == "function" and isinstance(name, str):
        definition = {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            },
        }
        return definition, False
    if kind == "custom" and isinstance(name, str):
        description = tool.get("description") or tool.get("format", {}).get("description") or "Custom text tool"
        return (
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {"input": {"type": "string"}},
                        "required": ["input"],
                    },
                },
            },
            True,
        )
    return None


def responses_to_chat(body: dict[str, Any], model: str) -> tuple[dict[str, Any], set[str]]:
    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions:
        messages.append({"role": "system", "content": instructions})
    request_input = body.get("input", "")
    if isinstance(request_input, str):
        messages.append({"role": "user", "content": request_input})
    elif isinstance(request_input, list):
        for item in request_input:
            if not isinstance(item, dict):
                continue
            kind = item.get("type", "message")
            if kind == "message":
                role = item.get("role", "user")
                if role == "developer":
                    role = "system"
                messages.append({"role": role, "content": _chat_content(item.get("content", ""))})
            elif kind in {"function_call", "custom_tool_call"}:
                arguments = item.get("arguments")
                if kind == "custom_tool_call":
                    arguments = json.dumps({"input": item.get("input", "")}, ensure_ascii=False)
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": item.get("call_id") or item.get("id") or _id("call"),
                                "type": "function",
                                "function": {
                                    "name": item.get("name", "unknown_tool"),
                                    "arguments": arguments or "{}",
                                },
                            }
                        ],
                    }
                )
            elif kind in {"function_call_output", "custom_tool_call_output"}:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": item.get("call_id") or item.get("id") or "unknown_call",
                        "content": _text_parts(item.get("output", "")) or str(item.get("output", "")),
                    }
                )
            # Reasoning items and provider-specific metadata are intentionally dropped.
    else:
        raise ProtocolError("Responses input must be a string or array")

    custom_tools: set[str] = set()
    tools: list[dict[str, Any]] = []
    for tool in body.get("tools", []):
        if not isinstance(tool, dict):
            continue
        converted = _tool_definition(tool)
        if converted:
            definition, is_custom = converted
            tools.append(definition)
            if is_custom:
                custom_tools.add(definition["function"]["name"])

    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
        choice = body.get("tool_choice", "auto")
        if isinstance(choice, dict) and choice.get("type") in {"function", "custom"} and choice.get("name"):
            choice = {"type": "function", "function": {"name": choice["name"]}}
        payload["tool_choice"] = choice
    if isinstance(body.get("max_output_tokens"), int):
        payload["max_completion_tokens"] = body["max_output_tokens"]
    if isinstance(body.get("temperature"), (int, float)):
        payload["temperature"] = body["temperature"]
    if isinstance(body.get("top_p"), (int, float)):
        payload["top_p"] = body["top_p"]
    text_config = body.get("text")
    if isinstance(text_config, dict) and isinstance(text_config.get("format"), dict):
        format_type = text_config["format"].get("type")
        if format_type == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif format_type == "json_schema":
            response_format = text_config["format"]
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.get("name", "response"),
                    "schema": response_format.get("schema", {}),
                    "strict": response_format.get("strict", True),
                },
            }
    return payload, custom_tools


def _coalesce_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content", "")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
        if result and result[-1]["role"] == message["role"]:
            previous = result[-1]["content"]
            if not isinstance(previous, list):
                previous = [{"type": "text", "text": str(previous)}]
                result[-1]["content"] = previous
            previous.extend(blocks)
        else:
            result.append({"role": message["role"], "content": blocks})
    return result


def responses_to_anthropic(body: dict[str, Any], model: str) -> tuple[dict[str, Any], set[str]]:
    chat, custom_tools = responses_to_chat(body, model)
    system_parts: list[str] = []
    messages: list[dict[str, Any]] = []
    for message in chat["messages"]:
        role = message["role"]
        if role == "system":
            system_parts.append(_text_parts(message.get("content", "")) or str(message.get("content", "")))
            continue
        if role == "tool":
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": message.get("content", ""),
                        }
                    ],
                }
            )
            continue
        if role == "assistant" and message.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if message.get("content"):
                blocks.append({"type": "text", "text": str(message["content"])})
            for call in message["tool_calls"]:
                arguments = call["function"].get("arguments", "{}")
                try:
                    parsed = json.loads(arguments)
                except json.JSONDecodeError:
                    parsed = {"input": arguments}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": parsed,
                    }
                )
            messages.append({"role": "assistant", "content": blocks})
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            anthropic_parts: list[dict[str, Any]] = []
            for part in content:
                if part.get("type") == "text":
                    anthropic_parts.append(part)
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:") and ";base64," in url:
                        media, data = url.split(";base64,", 1)
                        anthropic_parts.append(
                            {
                                "type": "image",
                                "source": {"type": "base64", "media_type": media[5:], "data": data},
                            }
                        )
                    else:
                        anthropic_parts.append({"type": "text", "text": f"[Image URL: {url}]"})
            content = anthropic_parts
        messages.append({"role": role, "content": content})
    if not messages:
        messages.append({"role": "user", "content": "Continue."})
    payload: dict[str, Any] = {
        "model": model,
        "messages": _coalesce_anthropic_messages(messages),
        "max_tokens": body.get("max_output_tokens") or 8192,
        "stream": False,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    if chat.get("tools"):
        payload["tools"] = [
            {
                "name": tool["function"]["name"],
                "description": tool["function"].get("description", ""),
                "input_schema": tool["function"].get("parameters", {"type": "object", "properties": {}}),
            }
            for tool in chat["tools"]
        ]
        choice = chat.get("tool_choice", "auto")
        if choice == "none":
            payload.pop("tools", None)
        elif choice == "required":
            payload["tool_choice"] = {"type": "any"}
        elif isinstance(choice, dict):
            name = (choice.get("function") or {}).get("name")
            if name:
                payload["tool_choice"] = {"type": "tool", "name": name}
        else:
            payload["tool_choice"] = {"type": "auto"}
    return payload, custom_tools


def _usage_from_chat(usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
    cached = usage.get("cached_tokens")
    if cached is None:
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": int(cached or 0)},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": int(usage.get("total_tokens", input_tokens + output_tokens) or 0),
    }


def response_object(model: str, output: list[dict[str, Any]], usage: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": _id("resp"),
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": model,
        "output": output,
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning": {"effort": None, "summary": None},
        "store": False,
        "temperature": None,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
        "truncation": "disabled",
        "usage": _usage_from_chat(usage),
        "metadata": {},
    }


def chat_to_response(data: dict[str, Any], custom_tools: set[str]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProtocolError("Chat Completions response has no choices")
    message = choices[0].get("message", {})
    output: list[dict[str, Any]] = []
    content = message.get("content")
    if content:
        text_content = _text_parts(content) if isinstance(content, list) else str(content)
        output.append(
            {
                "id": _id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text_content, "annotations": []}],
            }
        )
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        name = function.get("name", "unknown_tool")
        arguments = function.get("arguments", "{}")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        call_id = call.get("id") or _id("call")
        if name in custom_tools:
            try:
                custom_input = json.loads(arguments).get("input", "")
            except (json.JSONDecodeError, AttributeError):
                custom_input = arguments
            output.append(
                {
                    "id": _id("ctc"),
                    "type": "custom_tool_call",
                    "status": "completed",
                    "call_id": call_id,
                    "name": name,
                    "input": custom_input,
                }
            )
        else:
            output.append(
                {
                    "id": _id("fc"),
                    "type": "function_call",
                    "status": "completed",
                    "call_id": call_id,
                    "name": name,
                    "arguments": arguments,
                }
            )
    if not output:
        raise ProtocolError("Chat Completions response contains neither text nor tool calls")
    return response_object(data.get("model", "unknown"), output, data.get("usage"))


def anthropic_to_response(data: dict[str, Any], custom_tools: set[str]) -> dict[str, Any]:
    output: list[dict[str, Any]] = []
    for block in data.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            output.append(
                {
                    "id": _id("msg"),
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": block["text"], "annotations": []}],
                }
            )
        elif block.get("type") == "tool_use":
            name = block.get("name", "unknown_tool")
            call_id = block.get("id") or _id("call")
            tool_input = block.get("input", {})
            if name in custom_tools:
                output.append(
                    {
                        "id": _id("ctc"),
                        "type": "custom_tool_call",
                        "status": "completed",
                        "call_id": call_id,
                        "name": name,
                        "input": tool_input.get("input", "") if isinstance(tool_input, dict) else str(tool_input),
                    }
                )
            else:
                output.append(
                    {
                        "id": _id("fc"),
                        "type": "function_call",
                        "status": "completed",
                        "call_id": call_id,
                        "name": name,
                        "arguments": json.dumps(tool_input, ensure_ascii=False),
                    }
                )
    if not output:
        raise ProtocolError("Anthropic response contains neither text nor tool calls")
    usage = data.get("usage") or {}
    normalized_usage = {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0),
        "cached_tokens": usage.get("cache_read_input_tokens", 0),
    }
    return response_object(data.get("model", "unknown"), output, normalized_usage)


def response_sse_events(response: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    pending = {**response, "status": "in_progress", "output": [], "usage": None}
    yield "response.created", {"type": "response.created", "response": pending}
    for index, item in enumerate(response["output"]):
        added = {**item, "status": "in_progress"}
        if item["type"] == "message":
            added["content"] = []
        yield "response.output_item.added", {
            "type": "response.output_item.added",
            "output_index": index,
            "item": added,
        }
        if item["type"] == "message":
            text = item["content"][0]["text"]
            yield "response.content_part.added", {
                "type": "response.content_part.added",
                "item_id": item["id"],
                "output_index": index,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            }
            yield "response.output_text.delta", {
                "type": "response.output_text.delta",
                "item_id": item["id"],
                "output_index": index,
                "content_index": 0,
                "delta": text,
            }
            yield "response.output_text.done", {
                "type": "response.output_text.done",
                "item_id": item["id"],
                "output_index": index,
                "content_index": 0,
                "text": text,
            }
            yield "response.content_part.done", {
                "type": "response.content_part.done",
                "item_id": item["id"],
                "output_index": index,
                "content_index": 0,
                "part": item["content"][0],
            }
        elif item["type"] == "function_call":
            yield "response.function_call_arguments.done", {
                "type": "response.function_call_arguments.done",
                "item_id": item["id"],
                "output_index": index,
                "arguments": item["arguments"],
            }
        elif item["type"] == "custom_tool_call":
            yield "response.custom_tool_call_input.done", {
                "type": "response.custom_tool_call_input.done",
                "item_id": item["id"],
                "output_index": index,
                "input": item["input"],
            }
        yield "response.output_item.done", {
            "type": "response.output_item.done",
            "output_index": index,
            "item": item,
        }
    yield "response.completed", {"type": "response.completed", "response": response}
