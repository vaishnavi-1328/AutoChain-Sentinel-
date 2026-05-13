"""ChainPulse FastAPI — Phase 2 scaffold.

Mounts: /health, /auth/*, /onboarding/profile, /profile/me.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

from chainpulse.backend.config.settings import get_settings
from chainpulse.backend.db import neo4j as neo4j_db
from chainpulse.backend.db import postgres as pg
from chainpulse.backend.db import redis as redis_db
from chainpulse.backend.routers import auth as auth_router
from chainpulse.backend.routers import events as events_router
from chainpulse.backend.routers import graph as graph_router
from chainpulse.backend.routers import profile as profile_router
from chainpulse.backend.routers import websocket as ws_router
from chainpulse.backend.services.ratelimit import limiter

log = logging.getLogger("chainpulse.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    log.info("starting chainpulse app env=%s", s.app_env)
    yield
    log.info("shutting down chainpulse app")
    for name, fn in (("redis", redis_db.dispose), ("postgres", pg.dispose)):
        try:
            await fn()
        except Exception:
            log.exception("%s dispose failed", name)
    try:
        neo4j_db.dispose()
    except Exception:
        log.exception("neo4j dispose failed")


app = FastAPI(title="ChainPulse API", version="0.3.0", lifespan=lifespan)
_settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# slowapi
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "rate limit exceeded", "retry_after": str(exc.detail)},
    )


app.include_router(auth_router.router)
app.include_router(profile_router.router)
app.include_router(events_router.router)
app.include_router(graph_router.router)
app.include_router(ws_router.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
