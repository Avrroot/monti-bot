"""FastAPI app for health checks and (auth-gated) internal diagnostics.
Telegram is the product's real interface — this exists purely for
container orchestration health probes and operator diagnostics.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis
from app.db.session import engine

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="SaveBot API", docs_url=None, redoc_url=None)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    checks = {"database": False, "redis": False}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_db_check_failed", error=str(exc))

    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_redis_check_failed", error=str(exc))

    ok = all(checks.values())
    if not ok:
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ok", **checks}


async def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    settings = get_settings()
    if not settings.admin_api_token or x_admin_token != settings.admin_api_token:
        raise HTTPException(status_code=403, detail="forbidden")


@app.get("/admin/stats", dependencies=[Depends(require_admin_token)])
async def admin_stats() -> dict:
    from sqlalchemy import func, select

    from app.db.models.saved_item import SavedItem
    from app.db.models.user import User
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        user_count = (await session.execute(select(func.count(User.id)))).scalar_one()
        item_count = (await session.execute(select(func.count(SavedItem.id)))).scalar_one()

    return {"users": user_count, "saved_items": item_count}
