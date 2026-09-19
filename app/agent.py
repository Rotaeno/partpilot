"""A bounded LangGraph workflow: interpretation -> guard -> tools -> grounded reply.

The model proposes; Python guards decide whether a proposal is executable.
Snapshots persist at completed turn boundaries; no hidden model chain-of-thought.
"""

from copy import deepcopy
import os

# A local demo must not inherit tracing exports from another project.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
from typing import TypedDict
import time
import uuid
from langgraph.graph import StateGraph, START, END
from .providers import ProviderError
from .schemas import Proposal, SLOT_LABELS
from .store import now
from .tools import values, run_tool, ToolError


class GraphState(TypedDict, total=False):
    session: dict
    request: dict
    route: str
    reply: str


def invalidate(s):
    s.update(
        results=[],
        total=0,
        query_id=None,
        query_revision=None,
        diagnostics=[],
        selection=None,
    )


class Agent:
    def __init__(self, tools, interpreter):
        self.tools, self.interpreter = tools, interpreter
        graph = StateGraph(GraphState)
        graph.add_node("interpret", self.interpret)
        graph.add_node("guard", self.guard)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("diagnose", self.diagnose)
        graph.add_node("respond", self.respond)
        graph.add_edge(START, "interpret")
        graph.add_edge("interpret", "guard")
        graph.add_conditional_edges(
            "guard",
            lambda s: s["route"],
            {"retrieve": "retrieve", "respond": "respond"},
        )
        graph.add_conditional_edges(
            "retrieve",
            lambda s: s["route"],
            {"diagnose": "diagnose", "respond": "respond"},
        )
        graph.add_edge("diagnose", "respond")
        graph.add_edge("respond", END)
        self.graph = graph.compile()

    def run(self, session, request):
        state = deepcopy(session)
        state["revision"] += 1
        state["suggestions"] = []
        state["advisories"] = []
        return self.graph.invoke(
            {"session": state, "request": request, "route": "respond", "reply": ""},
            {"recursion_limit": 10},
        )["session"]

    def interpret(self, ctx):
        s, req = ctx["session"], ctx["request"]
        action = req["action"]
        text = req.get("text", "").strip()
        label = {
            "search": "启动检索",
            "fallback": "仅按设备重新检索",
            "clear_slot": f"移除条件：{SLOT_LABELS.get(req.get('slot'),'')}",
        }.get(action, text)
        s["messages"].append({"role": "user", "content": label, "at": now()})
        if s["title"] == "新的配件查找" and text:
            s["title"] = text[:28]
        ctx["route"] = "respond"
        if action == "search":
            ctx["route"] = "retrieve"
            return ctx
        if action == "fallback":
            if "equipment_code" in s.get("conflict_map", {}):
                ctx["reply"] = "设备仍有冲突，请先明确一个设备编码。"
                return ctx
            s["slots"] = {k: v for k, v in s["slots"].items() if k == "equipment_code"}
            s["pending_conflicts"] = []
            s["conflict_map"] = {}
            invalidate(s)
            ctx["route"] = "retrieve"
            return ctx
        if action == "clear_slot":
            slot = req.get("slot")
            if slot == "equipment_code":
                ctx["reply"] = "设备编码为必填项，请直接输入新的设备编码。"
                return ctx
            s["slots"].pop(slot, None)
            cmap = s.setdefault("conflict_map", {})
            cmap.pop(slot, None)
            if slot in ("min_weight_kg", "max_weight_kg"):
                cmap.pop("_weight_range", None)
            s["pending_conflicts"] = list(cmap.values())
            invalidate(s)
            return ctx
        invalidate(s)
        if not text:
            ctx["reply"] = "请描述要查找的配件。"
            return ctx
        start = time.perf_counter()
        try:
            proposal = self.interpreter.interpret(text, s["slots"])
            if not isinstance(proposal, Proposal):
                raise ProviderError("解析器未返回有效结构。")
            s["trace"].append(
                {
                    "tool": "interpret_request",
                    "status": "ok",
                    "summary": (
                        "离线规则解析"
                        if self.interpreter.__class__.__name__ == "DemoInterpreter"
                        else "模型结构化解析"
                    ),
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                    "at": now(),
                }
            )
            cmap = s.setdefault("conflict_map", {})
            for key in [*proposal.changes, *proposal.clear]:
                # Only a direct, unambiguous correction resolves that field's conflict.
                if key not in proposal.changes or not proposal.changes[key].inferred:
                    cmap.pop(key, None)
            if proposal.changes or proposal.clear:
                cmap.pop("_weight_range", None)
                if "_proposal" in cmap:
                    cmap.pop("_proposal")
            if proposal.conflicts:
                for key in proposal.conflict_fields or ["_proposal"]:
                    cmap[key] = " ".join(proposal.conflicts)
            s["pending_conflicts"] = list(cmap.values())
            for key in proposal.clear:
                if key != "equipment_code":
                    s["slots"].pop(key, None)
            for key, change in proposal.changes.items():
                if change.inferred and s["slots"].get(key, {}).get("confirmed"):
                    s["advisories"].append(
                        f"{SLOT_LABELS[key]}的新描述尚不确定，原有已确认条件仍保留；请明确更正或移除该条件。"
                    )
                    continue
                value = change.value
                if "weight" in key:
                    try:
                        value = float(value)
                        if not 0 <= value <= 100000 or value != value:
                            raise ValueError()
                    except (ValueError, TypeError):
                        cmap[key] = "重量必须是有效的非负数（kg）。"
                        s["pending_conflicts"] = list(cmap.values())
                        continue
                else:
                    value = str(value).strip()[:120]
                    if not value:
                        continue
                    if key in ("equipment_code", "part_code"):
                        value = value.upper()
                s["slots"][key] = {
                    "value": value,
                    "source": "inferred" if change.inferred else "user",
                    "confirmed": not change.inferred,
                    "inclusive": change.inclusive,
                }
            if proposal.action == "fallback":
                if "equipment_code" not in s.get("conflict_map", {}):
                    s["slots"] = {
                        k: v for k, v in s["slots"].items() if k == "equipment_code"
                    }
                    s["pending_conflicts"] = []
                    s["conflict_map"] = {}
                    ctx["route"] = "retrieve"
            elif proposal.action == "search":
                ctx["route"] = "retrieve"
            if proposal.question:
                # Model-authored free text cannot claim a tool succeeded. Deterministic reply only.
                ctx["reply"] = (
                    proposal.question
                    if self.interpreter.__class__.__name__ == "DemoInterpreter"
                    else "请补充或明确配件名称、设备编码、材质或重量。当前尚未执行查询或保存选择。"
                )
        except ProviderError as exc:
            s["status"] = "error"
            s["trace"].append(
                {
                    "tool": "interpret_request",
                    "status": "error",
                    "summary": str(exc),
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                    "at": now(),
                }
            )
            ctx["reply"] = str(exc)
            ctx["route"] = "error"
        return ctx

    def guard(self, ctx):
        s = ctx["session"]
        if ctx["route"] == "error":
            ctx["route"] = "respond"
            return ctx
        f = values(s["slots"])
        if not f.get("equipment_code"):
            s["status"] = "collecting"
            ctx.update(
                route="respond",
                reply="先补充设备编码，才能确定适用的配件范围。演示设备可选择 DEMO-EX-001、DEMO-EX-002 或 DEMO-EX-003。",
            )
            s["suggestions"] = ["设备编码 DEMO-EX-001", "设备编码 DEMO-EX-002"]
            if s["pending_conflicts"]:
                s["status"] = "conflict"
                ctx["reply"] = " ".join(s["pending_conflicts"])
            return ctx
        try:
            equipment = run_tool(
                s, "lookup_equipment", self.tools.lookup_equipment, f["equipment_code"]
            )
        except ToolError as exc:
            invalidate(s)
            s["status"] = "error"
            ctx.update(route="respond", reply=str(exc))
            return ctx
        if not equipment:
            s["status"] = "collecting"
            ctx.update(
                route="respond",
                reply=f"目录中没有设备 {f['equipment_code']}。请核对编码，不会自动替换成其他设备。",
            )
            s["suggestions"] = ["设备编码 DEMO-EX-001", "设备编码 DEMO-EX-002"]
            return ctx
        low, high = f.get("min_weight_kg", 0), f.get("max_weight_kg", float("inf"))
        if low > high or (
            low == high
            and (f.get("min_weight_exclusive") or f.get("max_weight_exclusive"))
        ):
            conflict = "重量下限大于上限，请修改重量或移除冲突条件。"
            s.setdefault("conflict_map", {})["_weight_range"] = conflict
        else:
            s.setdefault("conflict_map", {}).pop("_weight_range", None)
        s["pending_conflicts"] = list(s["conflict_map"].values())
        if s["pending_conflicts"]:
            s["status"] = "conflict"
            invalidate(s)
            ctx.update(route="respond", reply=" ".join(s["pending_conflicts"]))
            s["suggestions"] = ["重量不限"]
            return ctx
        if ctx["route"] != "retrieve":
            s["status"] = "ready"
            desc = "；".join(
                f"{SLOT_LABELS[k]}：{v}"
                + ("（不含边界）" if f.get(k.replace("_kg", "_exclusive")) else "")
                for k, v in f.items()
                if k in SLOT_LABELS
            )
            inferred = [
                SLOT_LABELS[k] for k, v in s["slots"].items() if not v["confirmed"]
            ]
            note = (
                f" { '、'.join(inferred) }是未确认信息，不会用于筛除配件。"
                if inferred
                else ""
            )
            note += " ".join(s.get("advisories", []))
            ctx["reply"] = (
                ctx["reply"] or f"已整理条件：{desc}。{note}请确认后点击“启动检索”。"
            )
            s["suggestions"] = ["启动检索"]
        return ctx

    def retrieve(self, ctx):
        s = ctx["session"]
        invalidate(s)
        try:
            result = run_tool(
                s, "search_parts", self.tools.search_parts, values(s["slots"])
            )
            s.update(
                results=result["items"],
                total=result["total"],
                query_id=str(uuid.uuid4()),
                query_revision=s["revision"],
            )
            if result["total"]:
                s["status"] = "results"
                ctx.update(
                    route="respond",
                    reply=f"在当前设备范围内找到 {result['total']} 个匹配配件，展示前 {len(result['items'])} 个。请查看规格和安装层级；只有点击“就是这个”并确认后才会保存选择。",
                )
                s["suggestions"] = ["重量不超过2公斤", "仅按设备重新检索"]
            else:
                s["status"] = "no_results"
                ctx["route"] = "diagnose"
        except ToolError as exc:
            s["status"] = "error"
            ctx.update(route="respond", reply=str(exc))
            s["suggestions"] = ["启动检索"]
        return ctx

    def diagnose(self, ctx):
        s = ctx["session"]
        try:
            diagnostics = run_tool(
                s,
                "diagnose_no_results",
                self.tools.diagnose_no_results,
                values(s["slots"]),
            )
            s["diagnostics"] = diagnostics
            improved = [x for x in diagnostics if x["without_count"] > 0]
            reason = "；".join(
                f"移除“{x['label']}”后可找到 {x['without_count']} 条"
                for x in improved[:3]
            )
            ctx["reply"] = (
                "当前条件没有匹配结果。"
                + (
                    reason + "。"
                    if reason
                    else "逐项检查后，没有单个条件能独立解除限制。"
                )
                + "条件尚未放宽。你可以修改条件，或选择“仅按设备重新检索”。"
            )
            s["suggestions"] = ["仅按设备重新检索"]
        except ToolError:
            ctx["reply"] = (
                "当前查询没有匹配结果，但原因诊断工具暂时不可用。可以重试，或主动选择仅按设备重新检索。"
            )
        return ctx

    def respond(self, ctx):
        s = ctx["session"]
        s["messages"].append(
            {
                "role": "assistant",
                "content": ctx["reply"] or "请补充条件后继续。",
                "at": now(),
            }
        )
        return ctx
