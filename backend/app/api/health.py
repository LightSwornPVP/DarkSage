"""Health (liveness) and readiness endpoints.

/health   — the process is up. Never touches the database.
/ready    — the app is ready to serve traffic (database reachable).
Per SECURITY_RULES.md "Fail Closed": readiness reports not-ready rather
than guessing when the database check fails.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from backend.app.database.session import check_database_connection

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str


class ReadinessStatus(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", response_model=ReadinessStatus)
async def ready(response: Response) -> ReadinessStatus:
    db_ok = await check_database_connection()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessStatus(status="not_ready", database="unreachable")
    return ReadinessStatus(status="ready", database="ok")
