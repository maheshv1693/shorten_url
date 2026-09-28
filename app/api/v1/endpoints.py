"""Version 1 API endpoints for URL creation and analytics."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.cache import cache
from app.db.repository import AliasAlreadyExistsError, URLRepository
from app.db.session import SessionLocal, get_db
from app.api.v1.schemas import AnalyticsResponse, URLCreate, URLResponse

router = APIRouter(prefix="/api/v1")


def _cache_ttl(expires_at: datetime | None) -> int:
    """Return a cache TTL no longer than the URL's remaining lifetime."""
    if expires_at is None:
        return 300
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    remaining_seconds = (expires_at - datetime.now(timezone.utc)).total_seconds()
    return max(0, min(300, int(remaining_seconds)))


@router.post(
    "/urls",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_url(
    payload: URLCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> URLResponse:
    """Create a short URL and return its absolute address."""
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
        if payload.expires_in_hours is not None
        else None
    )
    try:
        url_obj = URLRepository.create_url(
            db,
            original_url=str(payload.url),
            custom_alias=payload.custom_alias,
            expires_at=expires_at,
        )
    except AliasAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alias already in use",
        ) from error

    cache.set(
        url_obj.short_code,
        url_obj.original_url,
        ttl_seconds=_cache_ttl(url_obj.expires_at),
    )
    return URLResponse(
        short_code=url_obj.short_code,
        short_url=f"{request.base_url}{url_obj.short_code}",
        original_url=url_obj.original_url,
        created_at=url_obj.created_at,
        expires_at=url_obj.expires_at,
    )


@router.get(
    "/urls/{short_code}/analytics",
    response_model=AnalyticsResponse,
)
def get_analytics(
    short_code: str,
    db: Session = Depends(get_db),
) -> AnalyticsResponse:
    """Return click totals and recent events for an active short URL."""
    if URLRepository.get_by_short_code(db, short_code) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found",
        )

    analytics = URLRepository.get_analytics(db, short_code)
    return AnalyticsResponse(short_code=short_code, **analytics)


def _persist_click_event(
    short_code: str,
    referrer: str | None,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    """Persist one click using a short-lived synchronous database session."""
    with SessionLocal() as db:
        URLRepository.record_click(
            db,
            short_code,
            referrer=referrer,
            user_agent=user_agent,
            ip_address=ip_address,
        )


async def record_click_event(
    short_code: str,
    referrer: str | None,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    """Record click telemetry without blocking the async event loop."""
    await run_in_threadpool(
        _persist_click_event,
        short_code,
        referrer,
        user_agent,
        ip_address,
    )