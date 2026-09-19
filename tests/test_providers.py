from dataclasses import replace
import json
import httpx
import pytest
from app.config import Settings
from app.providers import QwenInterpreter, ProviderError
from app.schemas import Proposal


def test_zero_budget_blocks_before_network(app, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Zero budget must not create a network client")

    monkeypatch.setattr(httpx, "Client", forbidden)
    provider = QwenInterpreter(
        replace(app.state.service.settings, mode="qwen"), app.state.store
    )
    with pytest.raises(ProviderError, match="预算为 0"):
        provider.interpret("找滤芯", {})
    assert app.state.store.usage()["calls"] == 0


def provider_fixture(app, monkeypatch, handler, **kwargs):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-not-real")
    cfg = replace(
        app.state.service.settings,
        mode="qwen",
        enable_paid_api=True,
        budget_cny=1,
        **kwargs
    )
    return QwenInterpreter(cfg, app.state.store, transport=httpx.MockTransport(handler))


def test_mock_qwen_adapter_structured_output_and_usage(app, monkeypatch):
    def handler(req):
        assert req.url.host == "dashscope.aliyuncs.com"
        data = json.loads(req.content)
        assert data["model"] == "qwen3.8-flash" and data["enable_thinking"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "changes": {
                                        "name": {"value": "滤芯", "evidence": "滤芯"}
                                    },
                                    "action": "update",
                                }
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            },
        )

    p = provider_fixture(app, monkeypatch, handler)
    result = p.interpret("找滤芯", {})
    assert result.changes["name"].value == "滤芯"
    usage = app.state.store.usage()
    assert usage["calls"] == 1 and usage["accounted_cny"] == pytest.approx(
        (100 * 0.8 + 30 * 2.7) / 1e6
    )


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps(
            {"changes": {"name": {"value": "滤芯", "evidence": "不存在的证据"}}}
        ),
        json.dumps({"action": "confirm"}),
    ],
)
def test_invalid_model_output_never_applied(app, monkeypatch, content):
    p = provider_fixture(
        app,
        monkeypatch,
        lambda req: httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        ),
    )
    with pytest.raises(ProviderError, match="校验失败"):
        p.interpret("找滤芯", {})
    assert app.state.store.usage()["calls"] == 1


def test_timeout_keeps_reservation_and_respects_retry_limit(app, monkeypatch):
    count = 0

    def handler(req):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("timeout")

    p = provider_fixture(app, monkeypatch, handler, retries=1)
    with pytest.raises(ProviderError, match="超时"):
        p.interpret("找滤芯", {})
    assert count == 2 and app.state.store.usage()["calls"] == 2
    assert app.state.store.usage()["accounted_cny"] > 0


def test_call_limit_is_durable(app, monkeypatch):
    def handler(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    p = provider_fixture(app, monkeypatch, handler, max_calls=1)
    p.interpret("找滤芯", {})
    p2 = QwenInterpreter(
        p.settings, app.state.store, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError, match="上限"):
        p2.interpret("再找滤芯", {})


@pytest.mark.parametrize(
    "content",
    [
        {
            "changes": {
                "material": {"value": "不锈钢", "evidence": "滤芯", "inferred": False}
            }
        },
        {"action": "fallback"},
        {"action": "search"},
        {"clear": ["name"]},
    ],
)
def test_model_cannot_invent_values_or_authorization(app, monkeypatch, content):
    p = provider_fixture(
        app,
        monkeypatch,
        lambda req: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(content)},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        ),
    )
    with pytest.raises(ProviderError):
        p.interpret("这个滤芯材质是什么意思？", {})


@pytest.mark.parametrize(
    "data",
    [
        {"choices": None},
        {"choices": [None]},
        [],
        {"choices": [{"finish_reason": "stop", "message": None}]},
    ],
)
def test_malformed_envelope_is_controlled_error(app, monkeypatch, data):
    p = provider_fixture(app, monkeypatch, lambda req: httpx.Response(200, json=data))
    with pytest.raises(ProviderError):
        p.interpret("找滤芯", {})
