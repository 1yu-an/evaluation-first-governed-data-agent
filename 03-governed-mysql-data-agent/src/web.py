"""Thin same-origin web adapter for the governed data agent."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .agent import DataAgent
from .executor import ExecutionError, executor_from_env


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_DB_PATH = PROJECT_ROOT / "demo.db"
WEB_ROOT = PROJECT_ROOT / "web"
DEMO_META_PATH = WEB_ROOT / "demo-meta.json"
MAX_QUESTION_LENGTH = 500
LOGGER = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


def _load_demo_meta() -> dict:
    return json.loads(DEMO_META_PATH.read_text(encoding="utf-8"))


def _executor_mode() -> str:
    return os.environ.get("DATA_AGENT_EXECUTOR", "sqlite").strip().lower()


def _demo_ready(db_path: Path) -> bool:
    mode = _executor_mode()
    if mode == "sqlite":
        return db_path.is_file()
    if mode == "mysql":
        try:
            executor_from_env(db_path)
        except ExecutionError:
            return False
        return True
    return False


def _default_agent_provider(db_path: Path) -> Callable[[], DataAgent]:
    def provide_agent() -> DataAgent:
        executor = executor_from_env(db_path)
        return DataAgent(db_path=db_path, executor=executor)

    return provide_agent


def create_app(
    *,
    agent_provider: Callable[[], DataAgent] | None = None,
    db_path: str | Path = DEMO_DB_PATH,
) -> FastAPI:
    """Create an adapter that delegates every business query to DataAgent."""
    resolved_db_path = Path(db_path)
    app = FastAPI(
        title="Governed Data Agent Web Demo",
        version="interview-demo-v1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.agent_provider = agent_provider or _default_agent_provider(
        resolved_db_path
    )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @app.get("/api/health")
    def health() -> dict:
        ready = _demo_ready(resolved_db_path)
        return {
            "status": "ok" if ready else "degraded",
            "executor": _executor_mode(),
            "demo_ready": ready,
        }

    @app.get("/api/demo-meta")
    def demo_meta() -> dict:
        return _load_demo_meta()

    @app.post("/api/query")
    def query(payload: QueryRequest):
        try:
            agent = app.state.agent_provider()
            return agent.answer(payload.question)
        except Exception:
            LOGGER.exception("Web query failed")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "ERROR",
                    "reason": "internal server error / 服务内部错误",
                    "trace": [],
                },
            )

    app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")
    return app


app = create_app()
