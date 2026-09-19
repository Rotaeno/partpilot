import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.tools import ToolError
from .conftest import turn


def ready(client, s):
    return turn(client, s, "设备编码 DEMO-EX-001，找液压回油滤芯")


def search(client, s):
    return turn(client, s, action="search")


def test_complete_flow_and_idempotent_confirmation(client, session, app):
    s = ready(client, session)
    assert s["status"] == "ready" and s["results"] == []
    s = search(client, s)
    assert {x["id"] for x in s["results"]} >= {"PP-1001", "PP-1002"}
    body = dict(
        part_id="PP-1001", query_id=s["query_id"], expected_revision=s["revision"]
    )
    r = client.post(f'/api/sessions/{s["id"]}/confirm', json=body)
    assert r.status_code == 200
    done = r.json()
    assert done["status"] == "confirmed" and done["selection"]["part_id"] == "PP-1001"
    replay = client.post(f'/api/sessions/{s["id"]}/confirm', json=body).json()
    assert replay["selection"]["id"] == done["selection"]["id"]
    assert len(app.state.store.selections(s["id"])) == 1


def test_missing_device_asks_without_search(client, session):
    s = turn(client, session, "找液压回油滤芯")
    assert s["status"] == "collecting"
    assert "设备编码" in s["messages"][-1]["content"]
    assert not any(t["tool"] == "search_parts" for t in s["trace"])
    s = search(client, s)
    assert not s["query_id"]


def test_unknown_device_never_guessed(client, session):
    s = turn(client, session, "设备编码 DEMO-EX-999，找滤芯")
    s = search(client, s)
    assert s["status"] == "collecting" and not s["results"]
    assert s["slots"]["equipment_code"]["value"] == "DEMO-EX-999"


def test_changed_device_invalidates_old_query(client, session):
    s = search(client, ready(client, session))
    old = dict(
        part_id="PP-1001", query_id=s["query_id"], expected_revision=s["revision"]
    )
    s = turn(client, s, "设备改为 DEMO-EX-002")
    assert not s["results"] and s["query_id"] is None
    r = client.post(f'/api/sessions/{s["id"]}/confirm', json=old)
    assert r.status_code == 409
    old["expected_revision"] = s["revision"]
    assert client.post(f'/api/sessions/{s["id"]}/confirm', json=old).status_code == 409
    s = search(client, s)
    assert s["results"] and all(
        "DEMO-EX-002" in p["equipment_codes"] for p in s["results"]
    )
    assert all(p["id"] != "PP-1001" for p in s["results"])


def test_conflicting_weight_blocked_and_resolved(client, session):
    s = turn(client, ready(client, session), "至少5公斤，不超过2公斤")
    assert s["status"] == "conflict"
    s = search(client, s)
    assert s["status"] == "conflict" and not s["query_id"]
    s = turn(client, s, "重量不限")
    assert s["status"] == "ready"
    s = search(client, s)
    assert s["results"]


def test_two_equipment_conflict(client, session):
    s = turn(client, session, "DEMO-EX-001 或 DEMO-EX-002 的滤芯")
    assert s["status"] == "conflict"
    s = turn(client, s, "设备编码 DEMO-EX-001")
    assert s["status"] == "ready"


def test_no_results_diagnosis_and_explicit_fallback(client, session):
    s = turn(client, ready(client, session), "重量至少100公斤")
    s = search(client, s)
    assert s["status"] == "no_results"
    d = next(d for d in s["diagnostics"] if d["slot"] == "min_weight_kg")
    assert d["without_count"] >= 2
    assert s["slots"]["min_weight_kg"]["value"] == 100
    s = turn(client, s, action="fallback")
    assert list(s["slots"]) == ["equipment_code"]
    assert s["status"] == "results"


@pytest.mark.parametrize("failure", [ToolError("fault"), TimeoutError("timeout")])
def test_tool_error_is_not_empty_result(client, session, app, monkeypatch, failure):
    s = ready(client, session)
    original = app.state.service.tools.search_parts

    def broken(*args, **kwargs):
        raise failure

    monkeypatch.setattr(app.state.service.tools, "search_parts", broken)
    s = search(client, s)
    assert s["status"] == "error" and s["query_id"] is None
    assert s["trace"][-1]["status"] == "error"
    monkeypatch.setattr(app.state.service.tools, "search_parts", original)
    assert search(client, s)["status"] == "results"


def test_units_equivalent(client, session):
    s = turn(client, ready(client, session), "重量不超过2000g")
    first = search(client, s)
    assert [p["id"] for p in first["results"]] == ["PP-1001"]
    second = search(client, turn(client, first, "重量不超过2公斤"))
    assert [p["id"] for p in second["results"]] == ["PP-1001"]


def test_unknown_weight_is_not_zero(app):
    result = app.state.service.tools.search_parts(
        {"equipment_code": "DEMO-EX-001", "max_weight_kg": 100000}, limit=100
    )
    assert all(p["weight_kg"] is not None for p in result["items"])


def test_uncertain_attributes_do_not_filter(client, session):
    s = turn(client, ready(client, session), "大概不超过1公斤")
    assert not s["slots"]["max_weight_kg"]["confirmed"]
    s = search(client, s)
    assert any(p["id"] == "PP-1002" for p in s["results"])


def test_non_candidate_confirmation_rejected(client, session):
    s = search(client, ready(client, session))
    body = dict(
        part_id="PP-1003", query_id=s["query_id"], expected_revision=s["revision"]
    )
    assert client.post(f'/api/sessions/{s["id"]}/confirm', json=body).status_code == 409


def test_sessions_survive_restart_and_history_crud(client, session, app):
    s = search(client, ready(client, session))
    fresh = create_app(app.state.service.settings)
    with TestClient(fresh) as other:
        restored = other.get(f'/api/sessions/{s["id"]}').json()
        assert restored["query_id"] == s["query_id"]
        assert restored["results"] == s["results"]
        renamed = other.patch(
            f'/api/sessions/{s["id"]}', json={"title": "滤芯查找记录"}
        ).json()
        assert renamed["title"] == "滤芯查找记录"
        assert (
            other.get(f'/api/sessions/{s["id"]}/export').json()["synthetic_data"]
            is True
        )
        new = other.post("/api/sessions", json={}).json()
        assert not new["slots"] and not new["results"]
        assert other.delete(f'/api/sessions/{s["id"]}').status_code == 200
        assert other.get(f'/api/sessions/{s["id"]}').status_code == 404


def test_concurrent_revision_rejected(client, session):
    turn(client, session, "找滤芯")
    assert (
        client.post(
            f'/api/sessions/{session["id"]}/turn',
            json={"action": "search", "expected_revision": 0},
        ).status_code
        == 409
    )


def test_invalid_and_cross_origin_requests(client, session):
    assert (
        client.post(
            f'/api/sessions/{session["id"]}/turn',
            json={"action": "delete_all", "expected_revision": 0},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/sessions", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f'/api/sessions/{session["id"]}/turn',
            json={"action": "message", "text": " ", "expected_revision": 0},
        ).status_code
        == 422
    )


def test_unrelated_change_does_not_resolve_device_conflict(client, session):
    s = ready(client, session)
    s = turn(client, s, "DEMO-EX-001 或 DEMO-EX-002")
    assert s["status"] == "conflict"
    s = turn(client, s, "材质不锈钢")
    assert s["status"] == "conflict"
    s = turn(client, s, action="fallback")
    assert s["status"] == "conflict"
    assert not s["query_id"]
    s = turn(client, s, "设备编码 DEMO-EX-002")
    assert s["status"] == "ready"


def test_material_correction_uses_new_value(client, session):
    s = turn(client, ready(client, session), "材质不锈钢")
    s = turn(client, s, "材质从不锈钢改为铝合金")
    assert s["slots"]["material"]["value"] == "铝合金"


@pytest.mark.parametrize(
    "text,included",
    [
        ("重量大于1.2公斤", False),
        ("重量至少1.2公斤", True),
        ("重量小于1.2公斤", False),
        ("重量不超过1.2公斤", True),
    ],
)
def test_strict_weight_boundary(client, session, text, included):
    s = search(client, turn(client, ready(client, session), text))
    assert ("PP-1001" in [p["id"] for p in s["results"]]) is included


def test_model_question_cannot_claim_success(app):
    from app.service import Service
    from app.schemas import Proposal

    class UntrustedInterpreter:
        def interpret(self, text, slots):
            return Proposal(action="ask", question="已保存你的配件选择 PP-1001。")

    svc = Service(
        app.state.store, app.state.service.settings, interpreter=UntrustedInterpreter()
    )
    s = app.state.store.create_session()
    s["slots"] = {
        "equipment_code": {"value": "DEMO-EX-001", "confirmed": True, "source": "user"}
    }
    app.state.store.save(s)
    result = svc.turn(
        s["id"],
        dict(action="message", text="这个材质是什么意思？", expected_revision=0),
    )
    assert "已保存" not in result["messages"][-1]["content"]
    assert not app.state.store.selections(s["id"])
