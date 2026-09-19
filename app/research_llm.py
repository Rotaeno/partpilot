"""Native Qwen function calling, with the same persistent project budget ledger."""

import json
import os
import time
import httpx
from .providers import ProviderError
from .research_tools import FUNCTIONS


class QwenPolicy:
    name = "qwen"

    def __init__(self, settings, store, transport=None, tool_names=None):
        self.settings, self.store, self.transport = settings, store, transport
        self.functions = [
            f
            for f in FUNCTIONS
            if not tool_names or f["function"]["name"] in tool_names
        ]

    def choose(self, messages, state):
        cfg = self.settings
        if not cfg.external_calls_enabled:
            raise ProviderError("真实Agent调用未启用或预算为0。")
        key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
        if not key:
            raise ProviderError("缺少DASHSCOPE_API_KEY。")
        if min(cfg.input_cny_per_million, cfg.output_cny_per_million) <= 0:
            raise ProviderError("请先配置有效的模型计费单价。")
        payload = {
            "model": cfg.model,
            "messages": messages,
            "tools": self.functions,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "enable_thinking": False,
            "max_tokens": cfg.max_output_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        reserve = (
            (len(body) + 2048) * cfg.input_cny_per_million
            + cfg.max_output_tokens * cfg.output_cny_per_million
        ) / 1e6
        for attempt in range(cfg.retries + 1):
            try:
                call_id = self.store.reserve_usage(
                    reserve, cfg.budget_cny, cfg.max_calls
                )
            except ValueError as exc:
                raise ProviderError(str(exc)) from exc
            start = time.perf_counter()
            cost = prompt = completion = None
            try:
                with httpx.Client(
                    timeout=cfg.timeout_seconds,
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    r = client.post(
                        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                        content=body,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                    )
                r.raise_for_status()
                data = r.json()
                usage = data.get("usage", {})
                prompt, completion = usage.get("prompt_tokens"), usage.get(
                    "completion_tokens"
                )
                if (
                    type(prompt) == int
                    and type(completion) == int
                    and min(prompt, completion) >= 0
                ):
                    cost = (
                        prompt * cfg.input_cny_per_million
                        + completion * cfg.output_cny_per_million
                    ) / 1e6
                self.store.finish_usage(
                    call_id,
                    status="received",
                    cost=cost,
                    prompt=prompt,
                    completion=completion,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                )
                choice = data["choices"][0]
                message = choice["message"]
                calls = message.get("tool_calls") or []
                if len(calls) != 1 or choice.get("finish_reason") not in (
                    "tool_calls",
                    "stop",
                ):
                    raise ValueError("exactly one complete tool call required")
                call = calls[0]
                if call["function"]["name"] not in {
                    t["function"]["name"] for t in self.functions
                }:
                    raise ValueError("model selected unavailable tool")
                arguments = json.loads(call["function"]["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be object")
                return {
                    "tool": call["function"]["name"],
                    "arguments": arguments,
                    "call_id": call["id"],
                    "usage": {
                        "prompt_tokens": prompt,
                        "completion_tokens": completion,
                        "estimated_cny": cost,
                    },
                    "model_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                self.store.finish_usage(
                    call_id,
                    status="uncertain",
                    error=type(exc).__name__,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                )
                if attempt < cfg.retries:
                    continue
                raise ProviderError(
                    "模型请求超时或网络失败，已保留费用预留；可以稍后重试。"
                ) from exc
            except (
                httpx.HTTPStatusError,
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                AttributeError,
            ) as exc:
                known = {
                    "model selected unavailable tool": "tool_not_available",
                    "exactly one complete tool call required": "expected_single_tool",
                    "arguments must be object": "arguments_not_object",
                }
                failure = known.get(str(exc), type(exc).__name__)
                self.store.finish_usage(
                    call_id,
                    status="failed",
                    cost=cost,
                    prompt=prompt,
                    completion=completion,
                    error=type(exc).__name__,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                )
                raise ProviderError(
                    f"模型工具调用结构无效或服务拒绝请求；未执行该动作（{failure}）。"
                ) from exc
