"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from jaa import __version__
from jaa.clock import SystemClock
from jaa.config import Settings
from jaa.ids import Uuid4Factory
from jaa.providers.registry import build_provider
from jaa.storage.db import create_db_engine
from jaa.storage.repo import Repository
from jaa.truth.lexicon import SkillLexicon
from jaa.web.routes_api import router as api_router
from jaa.web.routes_html import router as html_router
from jaa.web.security import HostAndHeadersMiddleware, generate_csrf_token

_STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


def _configure_logging() -> None:
    for name in (
        "anthropic",
        "openai",
        "httpx",
        "httpx2",
        "google_genai",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    provider = app.state.provider
    close = getattr(provider, "aclose", None)
    if close is not None:
        await close()
    google_client = getattr(provider, "_google_client", None)
    if google_client is not None:
        aio = getattr(google_client, "aio", None)
        if aio is not None:
            aclose = getattr(aio, "aclose", None)
            if aclose is not None:
                await aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app with security middleware and routes."""
    _configure_logging()
    cfg = settings or Settings.from_env()
    engine = create_db_engine(cfg.db_path)
    lexicon = SkillLexicon.load(cfg.skills_file)
    clock = SystemClock()
    ids = Uuid4Factory()
    repo = Repository(engine, clock, ids, lexicon)
    provider = build_provider(cfg)

    app = FastAPI(title="Job Application Assistant", lifespan=lifespan)
    app.state.settings = cfg
    app.state.engine = engine
    app.state.repo = repo
    app.state.provider = provider
    app.state.lexicon = lexicon
    app.state.clock = clock
    app.state.ids = ids
    app.state.csrf_token = generate_csrf_token()

    app.add_middleware(HostAndHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(html_router)
    app.include_router(api_router)

    @app.get("/healthz", response_model=None)
    def healthz() -> JSONResponse | dict[str, Any]:
        db_status = "ok"
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db_status = "error"
        body: dict[str, Any] = {
            "status": "ok" if db_status == "ok" else "degraded",
            "version": __version__,
            "provider": cfg.provider,
            "db": db_status,
        }
        body["instance"] = cfg.instance_nonce
        if db_status != "ok":
            return JSONResponse(status_code=503, content=body)
        return body

    return app
