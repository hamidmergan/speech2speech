"""The app: one page, one conversation, two languages."""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src import access, providers
from src.database import init_db
from src.i18n import parse_accept_language, t
from src.routes import access as access_routes
from src.routes import health, interpreter

# Where the browser talks from, comma separated. The frontend container is the default.
_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3100,http://localhost:3000").split(",")
    if o.strip()
]

# Routes that answer without the access cookie, otherwise nobody could sign in.
_OPEN_PATHS = {"/health", "/config", "/access", "/access/login", "/access/logout"}


def _configure_logging() -> None:
    """Log to stdout only, Docker captures it."""
    logger.remove()
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="INFO",
        colorize=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database ready")
    missing = providers.check_required()
    for line in missing:
        logger.warning("No chat model configured: {}", line)
    for name, present in providers.configured().items():
        logger.info("Model {}: {}", name, "configured" if present else "not configured")
    if not access.required():
        logger.warning("ACCESS_PASSWORD is not set, everybody who reaches this port may use it")
    yield


def create_app() -> FastAPI:
    _configure_logging()

    application = FastAPI(title="speech2speech", lifespan=lifespan)

    @application.middleware("http")
    async def access_gate(request: Request, call_next) -> Response:
        """With a password set, every other route wants the signed cookie."""
        if request.method == "OPTIONS" or not access.required():
            return await call_next(request)
        if request.url.path in _OPEN_PATHS:
            return await call_next(request)
        if access.token_valid(request.cookies.get(access.COOKIE_NAME)):
            return await call_next(request)
        locale = parse_accept_language(request.headers.get("accept-language"))
        return JSONResponse(status_code=401, content={"detail": t("access.needed", locale)})

    # Registered last, so this is the outer middleware and the 401 the gate
    # answers with carries the header too. A cached 401 would lock the page out.
    @application.middleware("http")
    async def no_cache(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    # Allow direct browser requests, bypassing the page's own proxy.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(access_routes.router)
    application.include_router(interpreter.router)

    return application


app = create_app()
