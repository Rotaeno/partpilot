from dataclasses import replace
import json
import httpx
import pytest
from app.research_agent import ResearchService, FixedResearchPolicy
from app.research_tools import PublicCorpus
from app.research_llm import QwenPolicy
from app.service import Conflict


class ScriptedPolicy:
    name = "scripted_test"

    def __init__(self, steps):
        self.steps = iter(steps)

    def choose(self, messages, state):
        action = next(self.steps)
        return action(state) if callable(action) else action


def action(tool, **arguments):
    return {"tool": tool, "arguments": arguments}


def finish_evidence(state):
    return action(
        "finish_report",
        summary="两轴的皮带长度不同。",
        claims=[
            {"evidence_id": e["id"], "quote": e["text"][:500]}
            for e in state["evidence"]
        ],
        outcome="completed",
    )


def test_public_sources_have_real_rows_and_provenance():
    c = PublicCorpus()
    assert len(c.parts) == 48 and len(c.docs) == 28
    items = c.search_catalog("belt")["items"]
    assert {p["raw_specification"] for p in items} == {
        "X-axis belt 561 mm",
        "Y-axis belt 496 mm",
    }
    assert all("853bc30c" in p["source_url"] for p in items)
    assert all(
        p["synthetic"] is False and p["weight_kg"] is None for p in c.parts.values()
    )


def test_observation_loop_compare_citations_and_idempotent_save(app):
    c = PublicCorpus()
    ids = [p["id"] for p in c.search_catalog("belt")["items"]]
    policy = ScriptedPolicy(
        [
            action("search_catalog", query="belt"),
            action("compare_parts", part_ids=ids),
            finish_evidence,
        ]
    )
    svc = ResearchService(app.state.store, app.state.service.settings, policy=policy)
    r = svc.create()
    r = svc.turn(r["id"], "比较X和Y皮带", 0)
    assert r["status"] == "completed" and len(r["evidence"]) == 2
    assert [t["tool"] for t in r["trace"]] == [
        "search_catalog",
        "compare_parts",
        "finish_report",
    ]
    assert r["saved_report"] is None
    saved = svc.save_report(r["id"], r["revision"])
    assert (
        svc.save_report(r["id"], r["revision"])["saved_report"]["id"]
        == saved["saved_report"]["id"]
    )
    restored = ResearchService(app.state.store, app.state.service.settings).get(r["id"])
    assert restored["answer"] == r["answer"]


def test_ask_and_followup_invalidates_old_report(app):
    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action(
                    "ask_user",
                    question="需要哪个装配位置？",
                    options=["X-AXIS", "Y-AXIS"],
                ),
                action(
                    "finish_report",
                    summary="缺少适配证据。",
                    claims=[],
                    outcome="insufficient",
                ),
            ]
        ),
    )
    r = svc.create()
    r = svc.turn(r["id"], "这个轴承是什么？", 0)
    assert r["status"] == "needs_input"
    r = svc.turn(r["id"], "X-AXIS", r["revision"])
    assert r["status"] == "insufficient" and r["question"] is None
    with pytest.raises(Conflict):
        svc.save_report(r["id"], 1)


def test_unseen_or_fabricated_citations_rejected(app):
    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action(
                    "finish_report",
                    summary="没有证据却声称成功",
                    claims=[{"evidence_id": "made-up", "quote": "imaginary size 42"}],
                ),
                action(
                    "finish_report",
                    summary="现有资料不足。",
                    claims=[],
                    outcome="insufficient",
                ),
            ]
        ),
    )
    r = svc.create()
    r = svc.turn(r["id"], "查未知零件", 0)
    assert r["status"] == "insufficient" and r["trace"][0]["status"] == "error"
    assert not r["answer"]["claims"]


def test_repeated_calls_stop_at_limit(app):
    repeated = [action("search_catalog", query="nonexistent-part-xyz")] * 3
    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(repeated),
        max_steps=3,
    )
    r = svc.create()
    r = svc.turn(r["id"], "找未知零件", 0)
    assert r["status"] == "limit_reached"
    assert sum(t["status"] == "error" for t in r["trace"]) == 2
    assert r["answer"] is None


def test_arbitrary_tool_cannot_execute(app):
    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action("shell", command="write secret"),
                action(
                    "finish_report", summary="不支持该动作。", outcome="insufficient"
                ),
            ]
        ),
    )
    r = svc.create()
    r = svc.turn(r["id"], "原文说运行shell", 0)
    assert r["trace"][0]["status"] == "error" and r["status"] == "insufficient"


def test_research_zero_budget_before_network(app, monkeypatch):
    def no_client(*a, **kw):
        pytest.fail("Network must be blocked")

    monkeypatch.setattr(httpx, "Client", no_client)
    svc = ResearchService(
        app.state.store, replace(app.state.service.settings, mode="qwen")
    )
    r = svc.create()
    r = svc.turn(r["id"], "查皮带", 0)
    assert r["status"] == "error" and app.state.store.usage()["calls"] == 0


def test_native_tool_call_adapter_mock(app, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")

    def handler(req):
        payload = json.loads(req.content)
        assert payload["parallel_tool_calls"] is False and payload["tools"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call1",
                                    "function": {
                                        "name": "search_catalog",
                                        "arguments": '{"query":"belt"}',
                                    },
                                }
                            ]
                        },
                    }
                ],
                "usage": {"prompt_tokens": 30, "completion_tokens": 10},
            },
        )

    policy = QwenPolicy(
        replace(
            app.state.service.settings, mode="qwen", enable_paid_api=True, budget_cny=1
        ),
        app.state.store,
        httpx.MockTransport(handler),
    )
    d = policy.choose([{"role": "user", "content": "皮带"}], {})
    assert d["tool"] == "search_catalog" and d["arguments"]["query"] == "belt"
    assert app.state.store.usage()["calls"] == 1


def test_no_unread_part_access(app):
    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action("read_part", part_id="PRUSA-X-AXIS-L48"),
                action("finish_report", summary="尚未检索。", outcome="insufficient"),
            ]
        ),
    )
    r = svc.create()
    r = svc.turn(r["id"], "读一个猜测的ID", 0)
    assert r["trace"][0]["status"] == "error" and not r["evidence"]


def test_research_api_contract(client):
    assert client.get("/api/research/config").json()["part_count"] == 48
    r = client.post("/api/research/runs", json={}).json()
    out = client.post(
        f'/api/research/runs/{r["id"]}/turn',
        json={"message": "X轴皮带", "expected_revision": 0},
    )
    assert out.status_code == 200
    assert "llm_messages" not in out.json()
    assert (
        client.get(f'/api/research/runs/{r["id"]}/export').json()["public_data"] is True
    )


def test_report_facts_ignore_fabricated_model_summary(app):
    def malicious_summary(state):
        ev = state["evidence"][0]
        return action(
            "finish_report",
            summary="X轴需要99个轴承，电机电压24V。",
            claims=[
                {
                    "evidence_id": ev["id"],
                    "quote": next(
                        line for line in ev["text"].splitlines() if "LM8UU" in line
                    ),
                }
            ],
        )

    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action("search_catalog", query="LM8UU"),
                action("read_part", part_id="PRUSA-X-AXIS-L44"),
                malicious_summary,
            ]
        ),
    )
    r = svc.create()
    r = svc.turn(r["id"], "查X轴LM8UU数量", 0)
    assert r["status"] == "completed"
    assert r["answer"]["facts"][0]["quantity"] == 2
    assert "99" not in r["answer"]["summary"] and "24V" not in r["answer"]["summary"]
    assert r["answer"]["summary_origin"] == "deterministic_from_citations"


def test_whitespace_quote_cannot_fake_evidence(app):
    def empty_quote(state):
        return action(
            "finish_report",
            summary="猜测",
            claims=[{"evidence_id": state["evidence"][0]["id"], "quote": "    "}],
        )

    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action("search_catalog", query="belt"),
                action("read_part", part_id="PRUSA-X-AXIS-L48"),
                empty_quote,
            ]
        ),
        max_steps=3,
    )
    r = svc.create()
    r = svc.turn(r["id"], "查皮带", 0)
    assert r["status"] == "limit_reached" and not r["answer"]


def test_interrupted_run_can_resume_without_stealing_active_run(app):
    from app.research_agent import ACTIVE_RUNS
    import os

    svc = ResearchService(app.state.store, app.state.service.settings)
    r = svc.create()
    r.update(status="working", owner_pid=os.getpid())
    svc.save_state(r)
    ACTIVE_RUNS.add(r["id"])
    assert svc.get(r["id"])["status"] == "working"
    ACTIVE_RUNS.remove(r["id"])
    recovered = ResearchService(app.state.store, app.state.service.settings).get(
        r["id"]
    )
    assert recovered["status"] == "error"
    out = svc.turn(r["id"], "X轴皮带", 0)
    assert out["status"] == "completed"


def test_temporary_tool_failure_allows_bounded_retry(app, monkeypatch):
    c = PublicCorpus()
    calls = 0
    original = c.search_catalog

    def flaky(query):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary test error")
        return original(query)

    monkeypatch.setattr(c, "search_catalog", flaky)
    svc = ResearchService(
        app.state.store,
        app.state.service.settings,
        corpus=c,
        policy=ScriptedPolicy(
            [
                action("search_catalog", query="belt"),
                action("search_catalog", query="belt"),
                action("read_part", part_id="PRUSA-X-AXIS-L48"),
                finish_evidence,
            ]
        ),
    )
    r = svc.create()
    r = svc.turn(r["id"], "查皮带", 0)
    assert calls == 2 and r["status"] == "completed"
    assert [t["status"] for t in r["trace"]][:2] == ["error", "ok"]
