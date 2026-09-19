import json
import sqlite3
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from .config import ROOT, Settings
from .schemas import TurnRequest, ConfirmRequest, RenameRequest
from .service import Service, Conflict
from .store import Store, now


def create_app(settings=None, *, interpreter=None, tools=None):
    cfg = settings or Settings.from_env()
    store = Store(cfg.db_path, cfg.catalog_path)
    service = Service(store, cfg, interpreter=interpreter, tools=tools)
    app = FastAPI(
        title="PartPilot",
        version="0.1.0",
        description="个人项目 · 合成配件数据 · 单用户本地运行",
    )
    app.state.service = service
    app.state.store = store

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
        return FileResponse(ROOT / "static" / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": cfg.mode}

    @app.get("/api/config")
    def config():
        return dict(
            mode=cfg.mode,
            model=cfg.model,
            budget_cny=cfg.budget_cny,
            external_calls_enabled=cfg.external_calls_enabled,
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
            "mode": cfg.mode,
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

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
