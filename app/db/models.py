"""SQLAlchemy models for shortened URLs and click analytics."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for application ORM models."""


class URL(Base):
    """A short code and its destination URL."""

    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class URLClick(Base):
    """A recorded visit to a shortened URL."""

    __tablename__ = "url_clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("urls.short_code"), index=True, nullable=False
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)