"""Atomic per-turn snapshots. SQLite, not process memory, is the source of truth."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def dumps(value):
    return json.dumps(value, ensure_ascii=False)


class Store:
    def __init__(self, path: Path, catalog_path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        if not catalog["meta"]["synthetic"]:
            raise ValueError("演示目录必须明确标为 synthetic")
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS equipment(code TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS parts(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, title TEXT, status TEXT, updated_at TEXT, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS selections(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    query_id TEXT NOT NULL, part_id TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(session_id,query_id));
                CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY, status TEXT NOT NULL, reserved_cny REAL NOT NULL,
                    cost_cny REAL, prompt_tokens INTEGER, completion_tokens INTEGER, elapsed_ms REAL, error TEXT, created_at TEXT NOT NULL);
            """
            )
            # Seed once; application sessions never mutate the catalog.
            if con.execute("SELECT count(*) FROM parts").fetchone()[0] == 0:
                con.executemany(
                    "INSERT INTO equipment VALUES (?,?)",
                    [(x["code"], dumps(x)) for x in catalog["equipment"]],
                )
                con.executemany(
                    "INSERT INTO parts VALUES (?,?)",
                    [(x["id"], dumps(x)) for x in catalog["parts"]],
                )

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def equipment(self):
        with self.connect() as c:
            return [
                json.loads(r[0])
                for r in c.execute("SELECT payload FROM equipment ORDER BY code")
            ]

    def parts(self):
        with self.connect() as c:
            return [
                json.loads(r[0])
                for r in c.execute("SELECT payload FROM parts ORDER BY id")
            ]

    def part(self, part_id):
        with self.connect() as c:
            row = c.execute(
                "SELECT payload FROM parts WHERE id=?", (part_id,)
            ).fetchone()
        if row is None:
            raise KeyError(part_id)
        return json.loads(row[0])

    def create_session(self):
        stamp = now()
        state = dict(
            id=str(uuid.uuid4()),
            title="新的配件查找",
            status="collecting",
            revision=0,
            slots={},
            pending_conflicts=[],
            messages=[],
            results=[],
            query_id=None,
            query_revision=None,
            total=0,
            diagnostics=[],
            trace=[],
            selection=None,
            created_at=stamp,
            updated_at=stamp,
            suggestions=["找液压回油滤芯", "设备编码 DEMO-EX-001"],
        )
        self.save(state)
        return state

    def save(self, state, con=None):
        state["updated_at"] = now()
        values = (
            state["id"],
            state["title"],
            state["status"],
            state["updated_at"],
            dumps(state),
        )
        sql = "INSERT INTO sessions VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,status=excluded.status,updated_at=excluded.updated_at,payload=excluded.payload"
        if con is not None:
            con.execute(sql, values)
        else:
            with self.connect() as c:
                c.execute(sql, values)

    def get(self, session_id):
        with self.connect() as c:
            row = c.execute(
                "SELECT payload FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return json.loads(row[0])

    def sessions(self):
        with self.connect() as c:
            return [
                dict(x)
                for x in c.execute(
                    "SELECT id,title,status,updated_at FROM sessions ORDER BY updated_at DESC"
                )
            ]

    def delete(self, session_id):
        with self.connect() as c:
            cur = c.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            if cur.rowcount == 0:
                raise KeyError(session_id)

    def selections(self, session_id):
        with self.connect() as c:
            return [
                dict(x)
                for x in c.execute(
                    "SELECT * FROM selections WHERE session_id=? ORDER BY created_at",
                    (session_id,),
                )
            ]

    def confirm(self, state, part_id):
        record = dict(
            id=str(uuid.uuid4()),
            session_id=state["id"],
            query_id=state["query_id"],
            part_id=part_id,
            created_at=now(),
        )
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute(
                "SELECT * FROM selections WHERE session_id=? AND query_id=?",
                (state["id"], state["query_id"]),
            ).fetchone()
            if existing:
                if existing["part_id"] != part_id:
                    raise ValueError("本次查询已确认其他配件，请发起新检索。")
                record = dict(existing)
            else:
                c.execute(
                    "INSERT INTO selections VALUES (?,?,?,?,?)", tuple(record.values())
                )
            state["selection"] = record
            state["status"] = "confirmed"
            self.save(state, c)
        return record

    def reserve_usage(self, reserve, budget, max_calls):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            used, count = c.execute(
                "SELECT COALESCE(SUM(COALESCE(cost_cny,reserved_cny)),0),COUNT(*) FROM usage"
            ).fetchone()
            if count >= max_calls or used + reserve > budget:
                raise ValueError("模型预算或调用次数已达到上限。")
            call_id = str(uuid.uuid4())
            c.execute(
                "INSERT INTO usage(id,status,reserved_cny,created_at) VALUES (?,?,?,?)",
                (call_id, "reserved", reserve, now()),
            )
            return call_id

    def finish_usage(
        self,
        call_id,
        *,
        status,
        cost=None,
        prompt=None,
        completion=None,
        elapsed_ms=0,
        error=None
    ):
        with self.connect() as c:
            c.execute(
                "UPDATE usage SET status=?,cost_cny=?,prompt_tokens=?,completion_tokens=?,elapsed_ms=?,error=? WHERE id=?",
                (status, cost, prompt, completion, elapsed_ms, error, call_id),
            )

    def usage(self):
        with self.connect() as c:
            row = c.execute(
                "SELECT COUNT(*) AS calls,COALESCE(SUM(COALESCE(cost_cny,reserved_cny)),0) AS accounted_cny FROM usage"
            ).fetchone()
            return dict(row)
