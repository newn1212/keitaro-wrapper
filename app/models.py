from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CampaignRecord(Base):
    """Кампании, которые создали через наш «создаватель»."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    alias: Mapped[str] = mapped_column(String(64))
    geo: Mapped[str] = mapped_column(String(100))
    offer_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeLog(Base):
    """Журнал: какой оффер добавили/удалили/пересчитали в потоке."""

    __tablename__ = "change_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None]
    stream_id: Mapped[int]
    action: Mapped[str] = mapped_column(String(32))
    offer_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
