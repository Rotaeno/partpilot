"""Regressions from independent review: source row integrity and recovery CAS.

All policies are local scripts. The race is orchestrated with events rather than
sleep timing, and uses the normal persisted LangGraph service turn.
"""

import threading

import app.research_agent as research_module
from app.research_agent import ACTIVE_RUNS, ResearchService


def action(tool, **arguments):
    return {"tool": tool, "arguments": arguments}


class ScriptedPolicy:
    name = "review_scripted"

    def __init__(self, actions):
        self.actions = iter(actions)

    def choose(self, messages, state):
        step = next(self.actions)
        return step(state) if callable(step) else step


def test_flattened_citation_cannot_create_composite_bom_fact(app):
    """Collapsing real source rows must not create a fake name/quantity pair."""

    def flattened_quote(state):
        evidence = state["evidence"][0]
        lines = evidence["text"].splitlines()
        start = next(i for i, line in enumerate(lines) if "LM8UU" in line)
        return action(
            "finish_report",
            summary="模型尝试把多个源行拼成一项。",
            claims=[
                {
                    "evidence_id": evidence["id"],
                    "quote": " ".join(lines[start : start + 3]),
                }
            ],
            outcome="completed",
        )

    def corrected_quote(state):
        evidence = state["evidence"][0]
        source_line = next(
            line for line in evidence["text"].splitlines() if "LM8UU" in line
        )
        return action(
            "finish_report",
            summary="数量应依据原始完整表格行。",
            claims=[{"evidence_id": evidence["id"], "quote": source_line}],
            outcome="completed",
        )

    service = ResearchService(
        app.state.store,
        app.state.service.settings,
        policy=ScriptedPolicy(
            [
                action("search_catalog", query="LM8UU"),
                action("read_part", part_id="PRUSA-X-AXIS-L44"),
                flattened_quote,
                corrected_quote,
            ]
        ),
    )
    run = service.create()
    run = service.turn(run["id"], "X轴LM8UU轴承的原文数量是多少？", 0)

    assert run["trace"][2]["tool"] == "finish_report"
    assert run["trace"][2]["status"] == "error"
    assert run["status"] == "completed"
    assert [(fact["name"], fact["quantity"]) for fact in run["answer"]["facts"]] == [
        ("LM8UU linear bearing", 2)
    ]
    assert all("|" not in fact["name"] for fact in run["answer"]["facts"])


def test_stale_poll_recovery_cannot_overwrite_newly_finished_report(app, monkeypatch):
    """GET reads working, worker finishes, then GET evaluates stale liveness."""
    worker_started = threading.Event()
    allow_worker_finish = threading.Event()
    poll_has_old_snapshot = threading.Event()
    allow_poll_liveness = threading.Event()
    worker_result = {}
    poll_result = {}
    failures = []

    class WaitingPolicy:
        name = "review_waiting"

        def choose(self, messages, state):
            worker_started.set()
            assert allow_worker_finish.wait(
                timeout=10
            ), "review worker synchronization timed out"
            return action(
                "finish_report", summary="没有适配资料。", outcome="insufficient"
            )

    service = ResearchService(
        app.state.store, app.state.service.settings, policy=WaitingPolicy()
    )
    run = service.create()
    observer = ResearchService(app.state.store, app.state.service.settings)

    def worker():
        try:
            worker_result["run"] = service.turn(run["id"], "查一个没有资料的替代件", 0)
        except BaseException as error:
            failures.append(error)

    def poll():
        try:
            poll_result["run"] = observer.get(run["id"])
        except BaseException as error:
            failures.append(error)

    worker_thread = threading.Thread(target=worker, name="research-review-worker")
    poll_thread = threading.Thread(target=poll, name="research-review-poll")
    original_alive = research_module.process_alive

    def pause_after_snapshot_read(pid):
        # get() has loaded its SQLite payload before it calls process_alive().
        if (
            threading.current_thread() is poll_thread
            and not poll_has_old_snapshot.is_set()
        ):
            poll_has_old_snapshot.set()
            assert allow_poll_liveness.wait(
                timeout=10
            ), "review poll synchronization timed out"
        return original_alive(pid)

    try:
        worker_thread.start()
        assert worker_started.wait(timeout=10)
        assert run["id"] in ACTIVE_RUNS
        assert observer.get(run["id"])["status"] == "working"
        monkeypatch.setattr(research_module, "process_alive", pause_after_snapshot_read)

        poll_thread.start()
        assert poll_has_old_snapshot.wait(timeout=10)
        allow_worker_finish.set()
        worker_thread.join(timeout=10)
        assert not worker_thread.is_alive()
        assert not failures
        assert run["id"] not in ACTIVE_RUNS

        completed = service.get(run["id"])
        assert completed["status"] == "insufficient"
        assert completed["answer"] is not None

        allow_poll_liveness.set()
        poll_thread.join(timeout=10)
        assert not poll_thread.is_alive()
        assert not failures

        persisted = service.get(run["id"])
        assert poll_result["run"]["status"] == completed["status"]
        assert poll_result["run"]["answer"] == completed["answer"]
        assert persisted["status"] == completed["status"]
        assert persisted["answer"] == completed["answer"]
        assert persisted["messages"] == completed["messages"]
        assert worker_result["run"]["answer"] == persisted["answer"]
    finally:
        allow_worker_finish.set()
        allow_poll_liveness.set()
        if worker_thread.ident is not None:
            worker_thread.join(timeout=10)
        if poll_thread.ident is not None:
            poll_thread.join(timeout=10)
