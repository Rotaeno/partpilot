"""Application boundary: serialization, optimistic revisions, explicit writes."""

import threading
from .agent import Agent
from .providers import DemoInterpreter, QwenInterpreter
from .store import now
from .tools import Tools


class Conflict(Exception):
    pass


class Service:
    def __init__(self, store, settings, interpreter=None, tools=None):
        self.store, self.settings = store, settings
        self.lock = threading.RLock()
        self.tools = tools or Tools(store)
        if settings.mode not in ("demo", "qwen"):
            raise ValueError("PARTPILOT_MODE 必须是 demo 或 qwen")
        self.interpreter = interpreter or (
            DemoInterpreter(store)
            if settings.mode == "demo"
            else QwenInterpreter(settings, store)
        )
        self.agent = Agent(self.tools, self.interpreter)

    def turn(self, session_id, request):
        with self.lock:
            s = self.store.get(session_id)
            if request["expected_revision"] != s["revision"]:
                raise Conflict("会话已被更新，请刷新后再操作。旧结果不能继续使用。")
            if request["action"] == "message" and not request.get("text", "").strip():
                raise ValueError("请输入配件描述。")
            if request["action"] == "clear_slot" and not request.get("slot"):
                raise ValueError("请选择要移除的条件。")
            result = self.agent.run(s, request)
            self.store.save(result)
            return result

    def confirm(self, session_id, request):
        with self.lock:
            s = self.store.get(session_id)
            if (
                s.get("selection")
                and s["selection"]["query_id"] == request["query_id"]
                and s["selection"]["part_id"] == request["part_id"]
            ):
                return s  # Safe replay after a response was lost; no second write.
            if request["expected_revision"] != s["revision"]:
                raise Conflict("条件已变化，旧候选不能确认，请重新检索。")
            if (
                s["status"] != "results"
                or request["query_id"] != s.get("query_id")
                or s["query_revision"] != s["revision"]
            ):
                raise Conflict("本次查询已失效或已确认，请重新检索。")
            part = next(
                (x for x in s["results"] if x["id"] == request["part_id"]), None
            )
            if part is None:
                raise Conflict("只能确认当前查询返回的候选配件。")
            s["revision"] += 1
            s["messages"].extend(
                [
                    {
                        "role": "user",
                        "content": f"确认选择：{part['name']} · {part['id']}",
                        "at": now(),
                    },
                    {
                        "role": "assistant",
                        "content": f"已保存你的选择：{part['name']}（{part['id']}）。这是本地查找确认记录，不代表下单或生产适配认证。",
                        "at": now(),
                    },
                ]
            )
            s["trace"].append(
                {
                    "tool": "confirm_selection",
                    "status": "ok",
                    "summary": "显式确认，原子写入本地记录（同查询幂等）",
                    "elapsed_ms": 0,
                    "at": now(),
                }
            )
            s["suggestions"] = []
            self.store.confirm(s, part["id"])
            return s

    def rename(self, session_id, title):
        with self.lock:
            s = self.store.get(session_id)
            s["title"] = title
            self.store.save(s)
            return s

    def delete(self, session_id):
        with self.lock:
            self.store.delete(session_id)
