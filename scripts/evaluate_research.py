"""Comparable evidence-coverage checks; live mode must be explicitly requested."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.store import Store
from app.research_agent import (
    ResearchService,
    FixedResearchPolicy,
    FixedContextQwenPolicy,
)

CASES = [
    {
        "id": "R01",
        "question": "Original Prusa MINI 的 X 轴和 Y 轴皮带规格一样吗？给出原文依据。",
        "required": ["X-axis belt 561 mm", "Y-axis belt 496 mm"],
        "status": ["completed"],
    },
    {
        "id": "R02",
        "question": "X 轴和 Y 轴分别需要多少 LM8UU 轴承？请区分装配位置并给出原文。",
        "required": ["LM8UU linear bearing|2", "LM8UU linear bearing|3"],
        "status": ["completed"],
    },
    {
        "id": "R03",
        "question": "我想换一个轴承，但不知道型号，应该先确认哪个装配位置？",
        "required": [],
        "status": ["needs_input"],
    },
    {
        "id": "R04",
        "question": "可以把 X 轴皮带直接换成 Y 轴那条吗？长度规格和兼容性要分开说明。",
        "required": ["X-axis belt 561 mm", "Y-axis belt 496 mm"],
        "status": ["completed", "insufficient"],
        "limitation": True,
    },
    {
        "id": "R05",
        "question": "Original Prusa MINI 的 Z-AXIS 紧固件里面 M3x8 螺丝需要多少？请查完整原文而非选摘目录。",
        "required": ["M3x8"],
        "status": ["completed"],
    },
    {
        "id": "R06",
        "question": "这个固定版本BOM能确定PRUSA-MINI-SNAPSHOT的电机额定工作电压是48V吗？没有证据就明确说不能确定。",
        "required": [],
        "status": ["insufficient"],
        "limitation": True,
    },
    {
        "id": "R07",
        "question": "我准备更换那根传动带，但还没确认是哪一轴。先帮我明确要补什么信息。",
        "followup": "X轴。",
        "first_status": "needs_input",
        "required": ["X-axis belt 561 mm"],
        "status": ["completed"],
    },
    {
        "id": "R08",
        "question": "送丝时咬住塑料丝往里推的那个带齿小轮，在这台机器的物料表里叫什么？我不知道英文术语，请查原文，不要仅靠常识回答。",
        "required": ["MINI filament spur"],
        "status": ["completed"],
    },
]


def run_eval(live, selected, output, fixed_rag=False):
    settings = Settings()
    if live or fixed_rag:
        settings = replace(
            settings,
            mode="qwen",
            enable_paid_api=True,
            budget_cny=50,
            max_calls=200,
            max_output_tokens=1200,
        )
    # Shared production ledger means all real evaluations count toward the same 50 CNY cap.
    store = Store(settings.db_path, settings.catalog_path)
    policy = (
        FixedContextQwenPolicy(settings, store)
        if fixed_rag
        else None if live else FixedResearchPolicy()
    )
    svc = ResearchService(store, settings, policy=policy)
    before = store.usage()
    rows = []
    for case in CASES:
        if selected and case["id"] not in selected:
            continue
        r = svc.create()
        start = time.perf_counter()
        r = svc.turn(r["id"], case["question"], 0)
        first_status = r["status"]
        if case.get("followup"):
            r = svc.turn(r["id"], case["followup"], r["revision"])
        answer = r.get("answer") or {}
        quotes = "\n".join(c["quote"] for c in answer.get("claims", []))
        normalized = lambda s: "".join(s.lower().split())
        # Coverage is necessary, not sufficient: a human still checks the summary's meaning.
        coverage = all(normalized(t) in normalized(quotes) for t in case["required"])
        cited_urls = " ".join(c["source_url"] for c in answer.get("claims", []))
        if case["id"] in ("R01", "R02", "R04"):
            coverage = (
                coverage
                and "BOM/X-AXIS.md" in cited_urls
                and "BOM/Y-AXIS.md" in cited_urls
            )
        if case["id"] == "R05":
            coverage = coverage and "BOM/Z-AXIS.md" in cited_urls
        passed = (
            r["status"] in case["status"]
            and coverage
            and (not case.get("limitation") or bool(answer.get("limitations")))
            and (not case.get("first_status") or first_status == case["first_status"])
        )
        rows.append(
            {
                "id": case["id"],
                "question": case["question"],
                "passed": passed,
                "evidence_coverage": coverage,
                "status": r["status"],
                "first_status": first_status,
                "followup": case.get("followup"),
                "elapsed_seconds": round(time.perf_counter() - start, 2),
                "run_id": r["id"],
                "trace": r["trace"],
                "answer": answer,
                "question_back": r.get("question"),
            }
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "mode": (
                        "fixed_rag_qwen"
                        if fixed_rag
                        else "qwen_live" if live else "fixed_baseline"
                    ),
                    "before": before,
                    "after": store.usage(),
                    "results": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "case": case["id"],
                    "passed": passed,
                    "status": r["status"],
                    "steps": len(r["trace"]),
                    "seconds": rows[-1]["elapsed_seconds"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true")
    p.add_argument("--fixed-rag", action="store_true")
    p.add_argument("--cases", nargs="*")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    out = a.output or ROOT / "artifacts" / (
        "research-live.json" if a.live else "research-fixed.json"
    )
    run_eval(a.live, a.cases, out, a.fixed_rag)
