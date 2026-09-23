from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class SearchJob(Base):
    __tablename__ = 'search_jobs'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases_json: Mapped[str] = mapped_column(Text, default='[]')
    keywords_json: Mapped[str] = mapped_column(Text, default='[]')
    providers_json: Mapped[str] = mapped_column(Text, default='[]')
    status: Mapped[str] = mapped_column(String(32), default='queued', index=True)
    progress_json: Mapped[str] = mapped_column(Text, default='{}')
    diagnostics_json: Mapped[str] = mapped_column(Text, default='{}')
    error: Mapped[str] = mapped_column(Text, default='')
    result_limit: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list['EvidenceItem']] = relationship(back_populates='job', cascade='all, delete-orphan')


class EvidenceItem(Base):
    __tablename__ = 'evidence_items'
    __table_args__ = (UniqueConstraint('job_id', 'dedup_hash', name='uq_job_dedup_hash'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('search_jobs.id', ondelete='CASCADE'), index=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(300), default='')
    author: Mapped[str] = mapped_column(String(300), default='')
    text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, default='')
    url: Mapped[str] = mapped_column(Text, default='')
    published_at: Mapped[str] = mapped_column(String(80), default='')
    query: Mapped[str] = mapped_column(Text, default='')
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    risk_band: Mapped[str] = mapped_column(String(32), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    reasons_json: Mapped[str] = mapped_column(Text, default='[]')
    signals_json: Mapped[str] = mapped_column(Text, default='{}')
    analysis_version: Mapped[str] = mapped_column(String(40), default='rules-v2.0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[SearchJob] = relationship(back_populates='items')
