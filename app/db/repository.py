"""Database operations for URL mappings and click analytics."""

import secrets
from datetime import datetime
from typing import TypeAlias

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.base62 import ALPHABET
from app.db.models import URL, URLClick

AnalyticsData: TypeAlias = dict[str, int | list[URLClick]]
GENERATED_CODE_LENGTH = 7
MAX_CODE_GENERATION_ATTEMPTS = 3


def _generate_short_code() -> str:
    """Generate a cryptographically secure seven-character Base62 code."""
    return "".join(secrets.choice(ALPHABET) for _ in range(GENERATED_CODE_LENGTH))


class AliasAlreadyExistsError(Exception):
    """Raised when a custom short-code alias is already in use."""


class URLRepository:
    """Persistence operations for shortened URLs and their click events."""

    @staticmethod
    def create_url(
        db: Session,
        original_url: str,
        custom_alias: str | None = None,
        expires_at: datetime | None = None,
    ) -> URL:
        """Create a URL using its custom alias or a collision-checked random code."""
        if custom_alias is not None:
            url = URL(
                short_code=custom_alias,
                original_url=original_url,
                expires_at=expires_at,
            )
            db.add(url)
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise AliasAlreadyExistsError(
                    f"The short-code alias {custom_alias!r} is already in use"
                ) from error
            db.refresh(url)
            return url

        for attempt in range(MAX_CODE_GENERATION_ATTEMPTS):
            url = URL(
                short_code=_generate_short_code(),
                original_url=original_url,
                expires_at=expires_at,
            )
            db.add(url)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if attempt == MAX_CODE_GENERATION_ATTEMPTS - 1:
                    raise
            else:
                db.refresh(url)
                return url

        raise RuntimeError("short-code generation attempts exhausted unexpectedly")

    @staticmethod
    def get_by_short_code(db: Session, short_code: str) -> URL | None:
        """Return an active URL matching the short code, if one exists."""
        statement = select(URL).where(
            URL.short_code == short_code,
            URL.is_active.is_(True),
        )
        return db.scalar(statement)

    @staticmethod
    def record_click(
        db: Session,
        short_code: str,
        referrer: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> URLClick:
        """Persist a click event for an existing short code."""
        click = URLClick(
            short_code=short_code,
            referrer=referrer,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(click)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise
        db.refresh(click)
        return click

    @staticmethod
    def get_analytics(db: Session, short_code: str) -> AnalyticsData:
        """Return the total click count and up to 100 newest click events."""
        count_statement = (
            select(func.count())
            .select_from(URLClick)
            .where(URLClick.short_code == short_code)
        )
        total_clicks = db.scalar(count_statement) or 0

        recent_statement = (
            select(URLClick)
            .where(URLClick.short_code == short_code)
            .order_by(URLClick.clicked_at.desc(), URLClick.id.desc())
            .limit(100)
        )
        recent_clicks = list(db.scalars(recent_statement).all())
        return {"total_clicks": total_clicks, "recent_clicks": recent_clicks}