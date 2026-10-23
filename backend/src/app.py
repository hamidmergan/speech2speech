"""The app: one page, one conversation, two languages."""

import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Where the browser talks from, comma separated. The frontend container is the default.
_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3100,http://localhost:3000").split(",")
    if o.strip()
]


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


def create_app() -> FastAPI:
    _configure_logging()

    application = FastAPI(title="speech2speech")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return application


app = create_app()
