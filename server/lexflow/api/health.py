"""Liveness and database connectivity check."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from lexflow.db import get_engine

router = APIRouter(tags=["health"])
logger = logging.getLogger("lexflow.health")


class Health(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


@router.get(
    "/health",
    response_model=Health,
    responses={503: {"model": Health, "description": "The database is not reachable."}},
)
def health(engine: Engine = Depends(get_engine)) -> JSONResponse:
    """Report whether the API is up and can reach PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Never log the URL or the driver message: they can contain credentials.
        logger.warning("Database health check failed: %s", type(exc).__name__)
        body = Health(status="unavailable", database="unavailable")
        return JSONResponse(body.model_dump(), status_code=503)
    return JSONResponse(Health(status="ok", database="ok").model_dump())
