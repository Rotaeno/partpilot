"""Summarize saved development runs without any additional model requests."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"


def read(name):
    return json.loads((ART / name).read_text(encoding="utf-8"))["results"]


agent = read("research-agent-final.json") + read("research-agent-paraphrase-fixed.json")
fixed = [
    r
    for name in (
        "research-fixed-rag-v3-smoke.json",
        "research-fixed-rag-v3-batch.json",
        "research-fixed-rag-multiturn.json",
        "research-fixed-rag-paraphrase.json",
    )
    for r in read(name)
]
rows = []
for a in agent:
    b = next(x for x in fixed if x["id"] == a["id"])
    row = {
        "case": a["id"],
        "agent_pass": a["passed"],
        "fixed_rag_pass": b["passed"],
        "agent_status": a["status"],
        "fixed_rag_status": b["status"],
        "agent_seconds": a["elapsed_seconds"],
        "fixed_seconds": b["elapsed_seconds"],
    }
    for name, result in [("agent", a), ("fixed", b)]:
        row[name + "_model_calls"] = sum(bool(t.get("usage")) for t in result["trace"])
        row[name + "_cost_cny"] = round(
            sum(
                (t.get("usage") or {}).get("estimated_cny", 0) or 0
                for t in result["trace"]
            ),
            8,
        )
    rows.append(row)
report = {
    "note": "Exploratory development scenarios, one sampled run per row; R08 was repaired after a failed run. Not a held-out benchmark or general proof of Agent superiority. Same corpus/tools/model; fixed RAG uses one original-query retrieval per index and one Qwen synthesis per turn, without LLM query rewriting.",
    "rows": rows,
    "agent_passed": sum(r["agent_pass"] for r in rows),
    "fixed_passed": sum(r["fixed_rag_pass"] for r in rows),
}
for kind in ("agent", "fixed"):
    report[kind + "_mean_seconds"] = round(
        sum(r[kind + "_seconds"] for r in rows) / len(rows), 2
    )
    report[kind + "_total_cny"] = round(sum(r[kind + "_cost_cny"] for r in rows), 8)
(ART / "research-comparison.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False))
