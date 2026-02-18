"""SQLAlchemy database client."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.models import Base, Campaign, ContentItem, Failure

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def get_session() -> Session:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory()


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def create_campaign(name: str) -> Campaign:
    with get_session() as session:
        campaign = Campaign(id=str(uuid.uuid4()), name=name)
        session.add(campaign)
        session.commit()
        session.refresh(campaign)
        return campaign


def get_campaign(campaign_id: str) -> Campaign | None:
    with get_session() as session:
        return session.get(Campaign, campaign_id)


def update_campaign_status(campaign_id: str, status: str) -> None:
    with get_session() as session:
        campaign = session.get(Campaign, campaign_id)
        if campaign:
            campaign.status = status
            session.commit()


def create_item(
    campaign_id: str,
    source_url: str,
    item_type: str = "video",
    audio_url: str | None = None,
) -> ContentItem:
    with get_session() as session:
        item = ContentItem(
            id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            source_url=source_url,
            type=item_type,
            audio_url=audio_url,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


def get_item(item_id: str) -> ContentItem | None:
    with get_session() as session:
        return session.get(ContentItem, item_id)


def get_campaign_items(campaign_id: str) -> list[ContentItem]:
    with get_session() as session:
        return list(session.query(ContentItem).filter(ContentItem.campaign_id == campaign_id))


def update_item_status(item_id: str, status: str) -> None:
    with get_session() as session:
        item = session.get(ContentItem, item_id)
        if item:
            item.status = status
            session.commit()


def create_failure(
    item_id: str,
    campaign_id: str,
    stage: str,
    error: str,
    message: str,
) -> Failure:
    with get_session() as session:
        failure = Failure(
            id=str(uuid.uuid4()),
            item_id=item_id,
            campaign_id=campaign_id,
            stage=stage,
            error=error,
            message=message,
        )
        session.add(failure)
        session.commit()
        session.refresh(failure)
        return failure
