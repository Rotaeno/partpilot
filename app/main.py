import json
from dataclasses import replace
import sqlite3
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from .config import ROOT, Settings
from .schemas import TurnRequest, ConfirmRequest, RenameRequest
from .service import Service, Conflict
from .store import Store, now
from .research_agent import ResearchService


class ResearchTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    expected_revision: int = Field(ge=0)


class ResearchSave(BaseModel):
    expected_revision: int = Field(ge=0)


def create_app(settings=None, *, interpreter=None, tools=None):
    cfg = settings or Settings.from_env()
    store = Store(cfg.db_path, cfg.catalog_path)
    # Preserve v0.1 as a deterministic comparison workspace even when research is online.
    baseline_cfg = replace(cfg, mode="demo", enable_paid_api=False, budget_cny=0)
    service = Service(store, baseline_cfg, interpreter=interpreter, tools=tools)
    app = FastAPI(
        title="PartPilot",
        version="0.2.0",
        description="个人项目 · 合成配件数据 · 单用户本地运行",
    )
    app.state.service = service
    app.state.store = store
    research = ResearchService(store, cfg)
    app.state.research = research

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method in ("POST", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse(
                    status_code=403, content={"detail": "仅接受当前页面的操作。"}
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": "未找到该会话或配件。"})

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(sqlite3.Error)
    async def database_failure(request, exc):
        return JSONResponse(
            status_code=503,
            content={"detail": "本地数据库暂时不可用，操作未确认完成，请重试。"},
        )

    @app.get("/")
    def home():
        return FileResponse(ROOT / "static" / "research.html")

    @app.get("/baseline")
    def baseline_home():
        return FileResponse(ROOT / "static" / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": cfg.mode}

    @app.get("/api/config")
    def config():
        return dict(
            mode=baseline_cfg.mode,
            model=cfg.model,
            budget_cny=baseline_cfg.budget_cny,
            external_calls_enabled=baseline_cfg.external_calls_enabled,
            equipment_count=len(store.equipment()),
            part_count=len(store.parts()),
            usage=store.usage(),
        )

    @app.get("/api/equipment")
    def equipment():
        return {"items": store.equipment()}

    @app.get("/api/sessions")
    def sessions():
        return {"items": store.sessions()}

    @app.post("/api/sessions", status_code=201)
    def create_session():
        return store.create_session()

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        return store.get(session_id)

    @app.post("/api/sessions/{session_id}/turn")
    def turn(session_id: str, body: TurnRequest):
        return service.turn(session_id, body.model_dump())

    @app.post("/api/sessions/{session_id}/confirm")
    def confirm(session_id: str, body: ConfirmRequest):
        return service.confirm(session_id, body.model_dump())

    @app.patch("/api/sessions/{session_id}")
    def rename(session_id: str, body: RenameRequest):
        return service.rename(session_id, body.title)

    @app.delete("/api/sessions/{session_id}")
    def delete(session_id: str):
        service.delete(session_id)
        return {"deleted": True}

    @app.get("/api/parts/{part_id}")
    def part(part_id: str):
        return service.tools.get_part_details(part_id)

    @app.get("/api/sessions/{session_id}/export")
    def export(session_id: str):
        s = store.get(session_id)
        body = {
            "project": "PartPilot",
            "synthetic_data": True,
            "mode": baseline_cfg.mode,
            "exported_at": now(),
            "session": s,
            "selections": store.selections(session_id),
        }
        return Response(
            json.dumps(body, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="partpilot-{s["id"]}.json"'
            },
        )

    @app.get("/research")
    def research_home():
        return FileResponse(ROOT / "static/research.html")

    @app.get("/api/research/config")
    def research_config():
        return dict(
            mode=research.policy.name,
            model=cfg.model,
            budget_cny=cfg.budget_cny,
            usage=store.usage(),
            sources=research.corpus.sources,
            part_count=len(research.corpus.parts),
            document_count=len(research.corpus.docs),
        )

    @app.get("/api/research/runs")
    def research_runs():
        return {"items": research.list()}

    @app.post("/api/research/runs", status_code=201)
    def research_create():
        return research.create()

    @app.get("/api/research/runs/{run_id}")
    def research_get(run_id: str):
        return research.get(run_id)

    @app.post("/api/research/runs/{run_id}/turn")
    def research_turn(run_id: str, body: ResearchTurn):
        return research.turn(run_id, body.message, body.expected_revision)

    @app.post("/api/research/runs/{run_id}/save")
    def research_save(run_id: str, body: ResearchSave):
        return research.save_report(run_id, body.expected_revision)

    @app.get("/api/research/runs/{run_id}/export")
    def research_export(run_id: str):
        r = research.get(run_id)
        return Response(
            json.dumps(
                {
                    "project": "PartPilot",
                    "public_data": True,
                    "sources": research.corpus.sources,
                    "run": r,
                },
                ensure_ascii=False,
                indent=2,
            ),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="partpilot-research-{r["id"]}.json"'
            },
        )

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
