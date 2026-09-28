"""Pydantic schemas for URL creation and analytics API responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class URLCreate(BaseModel):
    """Validated input for creating a shortened URL."""

    url: HttpUrl
    custom_alias: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=16,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=720)

    @field_validator("custom_alias", mode="before")
    @classmethod
    def normalize_custom_alias(cls, value: object) -> object:
        """Treat an empty or whitespace-only alias as a request for generation."""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("url")
    @classmethod
    def require_http_scheme(cls, url: HttpUrl) -> HttpUrl:
        """Allow only HTTP and HTTPS destinations."""
        if url.scheme not in {"http", "https"}:
            raise ValueError("URL scheme must be http or https")
        return url


class URLResponse(BaseModel):
    """Public representation of a shortened URL."""

    model_config = ConfigDict(from_attributes=True)

    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class ClickMetric(BaseModel):
    """Public click metadata, excluding the visitor's IP address."""

    model_config = ConfigDict(from_attributes=True)

    clicked_at: datetime
    referrer: Optional[str] = None
    user_agent: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """Aggregate and recent click metrics for a shortened URL."""

    short_code: str
    total_clicks: int = Field(ge=0)
    recent_clicks: List[ClickMetric]