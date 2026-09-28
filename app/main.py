"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.endpoints import record_click_event, router
from app.core.cache import cache
from app.db.repository import URLRepository
from app.db.session import get_db, init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize persistent tables when the application starts."""
    init_db()
    yield


app = FastAPI(
    title="High-Performance URL Shortener",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> JSONResponse:
    """Report application health based on a lightweight database probe."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected"},
        )
    return JSONResponse(
        content={"status": "healthy", "database": "connected", "version": "1.0.0"}
    )


@app.get("/{short_code}", name="redirect_url")
def redirect_url(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect to a cached or persisted destination and record the click."""
    target_url = cache.get(short_code)

    if target_url is None:
        url_obj = URLRepository.get_by_short_code(db, short_code)
        if url_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short URL not found",
            )
        target_url = url_obj.original_url

        expires_at = url_obj.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="URL has expired",
                )
            ttl_seconds = max(
                0,
                min(300, int((expires_at - datetime.now(timezone.utc)).total_seconds())),
            )
            cache.set(short_code, target_url, ttl_seconds=ttl_seconds)
        else:
            cache.set(short_code, target_url)

    background_tasks.add_task(
        record_click_event,
        short_code,
        request.headers.get("referer"),
        request.headers.get("user-agent"),
        request.client.host if request.client is not None else None,
    )
    return RedirectResponse(
        url=target_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )