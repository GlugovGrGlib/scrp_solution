"""SQLAlchemy models for pipeline entities."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all models."""


class Campaign(Base):
    """Campaign record."""

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ContentItem(Base):
    """Content item to be processed."""

    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    source_url: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(20), default="video")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Failure(Base):
    """Pipeline failure record."""

    __tablename__ = "failures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    stage: Mapped[str] = mapped_column(String(30))
    error: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    failed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
