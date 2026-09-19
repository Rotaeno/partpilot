"""Run predeclared cases without external APIs. Gold labels never enter the agent."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.store import Store
from app.service import Service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "data/eval_holdout.json")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/evaluation.json"
    )
    args = parser.parse_args()
    config = Settings(db_path=ROOT / ".tmp" / f"eval-{uuid.uuid4().hex}.db")
    store = Store(config.db_path, config.catalog_path)
    service = Service(store, config)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    rows = []
    for case in cases:
        s = store.create_session()
        start = time.perf_counter()
        for text in case["turns"]:
            s = service.turn(
                s["id"],
                dict(action="message", text=text, expected_revision=s["revision"]),
            )
        if case.get("search"):
            s = service.turn(
                s["id"], dict(action="search", text="", expected_revision=s["revision"])
            )
        ids = [p["id"] for p in s["results"]]
        checks = {"status": s["status"] == case["status"]}
        if "must_include" in case:
            checks["include"] = case["must_include"] in ids
        if "must_exclude" in case:
            checks["exclude"] = case["must_exclude"] not in ids
        if "total" in case:
            checks["total"] = case["total"] == s["total"]
        if "min_total" in case:
            checks["min_total"] = s["total"] >= case["min_total"]
        if case.get("no_query"):
            checks["no_query"] = s["query_id"] is None
        if case.get("diagnostic"):
            checks["diagnostic"] = bool(s["diagnostics"])
        rows.append(
            {
                "id": case["id"],
                "passed": all(checks.values()),
                "checks": checks,
                "status": s["status"],
                "returned_ids": ids,
                "total": s["total"],
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                "tool_calls": sum(t["tool"] != "interpret_request" for t in s["trace"]),
            }
        )
    report = {
        "mode": "offline lexical baseline + LangGraph",
        "synthetic_data": True,
        "external_model_calls": 0,
        "passed": sum(r["passed"] for r in rows),
        "cases": len(rows),
        "results": rows,
        "caveat": "These are synthetic flow assertions, not retrieval accuracy on industrial data or live LLM Agent success.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "results"}, ensure_ascii=False
        )
    )
    return 0 if report["passed"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
