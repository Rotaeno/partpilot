"""Deterministic tools. Catalog text is data, never executable instructions."""

import time
from .schemas import SLOT_LABELS


class ToolError(Exception):
    pass


def values(slots):
    out = {k: v["value"] for k, v in slots.items() if v.get("confirmed")}
    for bound in ("min_weight", "max_weight"):
        v = slots.get(bound + "_kg", {})
        if v.get("confirmed") and not v.get("inclusive", True):
            out[bound + "_exclusive"] = True
    return out


class Tools:
    def __init__(self, store):
        self.store = store

    def lookup_equipment(self, code):
        return next((x for x in self.store.equipment() if x["code"] == code), None)

    def search_parts(self, filters, *, limit=10):
        if not filters.get("equipment_code"):
            raise ToolError("缺少设备编码，未执行检索。")
        found = []
        for p in self.store.parts():
            if filters["equipment_code"] not in p["equipment_codes"]:
                continue
            reasons = [f"适用设备 {filters['equipment_code']}"]
            if (
                filters.get("part_code")
                and filters["part_code"].upper() != p["id"].upper()
            ):
                continue
            if filters.get("material") and filters["material"] != p["material"]:
                continue
            weight = p.get("weight_kg")
            if "max_weight_kg" in filters and (
                weight is None or weight > filters["max_weight_kg"]
            ):
                continue
            if "min_weight_kg" in filters and (
                weight is None or weight < filters["min_weight_kg"]
            ):
                continue
            if filters.get("min_weight_exclusive") and weight == filters.get(
                "min_weight_kg"
            ):
                continue
            if filters.get("max_weight_exclusive") and weight == filters.get(
                "max_weight_kg"
            ):
                continue
            if filters.get("location") and filters["location"] not in "/".join(
                p["assembly_path"]
            ):
                continue
            score = 0
            if name := filters.get("name"):
                terms = [p["name"], *p["aliases"]]
                exact = name in terms
                partial = any(name in term for term in terms)
                if not partial:
                    continue
                score += 10 if exact else 4
                reasons.append(f"{'名称/别名匹配' if exact else '名称包含'}「{name}」")
            for k in (
                "part_code",
                "material",
                "min_weight_kg",
                "max_weight_kg",
                "location",
            ):
                if k in filters:
                    exclusive = (
                        filters.get(k.replace("_kg", "_exclusive"), False)
                        if "weight" in k
                        else False
                    )
                    reasons.append(
                        f"{SLOT_LABELS[k]}：{filters[k]}"
                        + ("（不含边界）" if exclusive else "")
                    )
            found.append({**p, "reasons": reasons, "_rank": score})
        found.sort(key=lambda x: (-x["_rank"], x["id"]))
        for x in found:
            x.pop("_rank")
        return {"items": found[:limit], "total": len(found), "limit": limit}

    def diagnose_no_results(self, filters):
        diagnostics = []
        for key in filters:
            if key == "equipment_code" or key not in SLOT_LABELS:
                continue
            reduced = {k: v for k, v in filters.items() if k != key}
            if "weight" in key:
                reduced.pop(key.replace("_kg", "_exclusive"), None)
            result = self.search_parts(reduced, limit=0)
            diagnostics.append(
                {
                    "slot": key,
                    "label": SLOT_LABELS[key],
                    "without_count": result["total"],
                }
            )
        return sorted(diagnostics, key=lambda x: -x["without_count"])

    def get_part_details(self, part_id):
        return self.store.part(part_id)


def run_tool(state, name, function, *args, **kwargs):
    start = time.perf_counter()
    from .store import now

    try:
        result = function(*args, **kwargs)
    except (ToolError, TimeoutError, OSError) as exc:
        state["trace"].append(
            {
                "tool": name,
                "status": "error",
                "summary": (
                    "工具超时" if isinstance(exc, TimeoutError) else "工具执行失败"
                ),
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                "at": now(),
            }
        )
        raise ToolError("查询服务暂时不可用，请重试。") from exc
    summary = "执行成功"
    if name == "lookup_equipment":
        summary = "设备存在" if result else "未找到设备编码"
    elif name == "search_parts":
        summary = f"匹配 {result['total']} 条，返回 {len(result['items'])} 条"
    elif name == "diagnose_no_results":
        summary = "逐项移除条件并检查实际数量；未修改生效条件"
    state["trace"].append(
        {
            "tool": name,
            "status": "ok",
            "summary": summary,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "at": now(),
        }
    )
    return result
