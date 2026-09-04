from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    http_method: Mapped[str] = mapped_column(String(16), default="POST")

    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    auth_type: Mapped[str] = mapped_column(String(32), default="none")
    auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    request_template: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_path: Mapped[str] = mapped_column(String(256), default="message")
    response_path: Mapped[str | None] = mapped_column(String(256), nullable=True)

    timeout: Mapped[int] = mapped_column(Integer, default=30)
    retry_count: Mapped[int] = mapped_column(Integer, default=2)
    retry_backoff: Mapped[float] = mapped_column(Float, default=1.0)
    max_conversation_turns: Mapped[int] = mapped_column(Integer, default=0)

    adapter_type: Mapped[str] = mapped_column(String(32), default="http")

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    scans: Mapped[list["TestRun"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )

    def redacted(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "http_method": self.http_method,
            "auth_type": self.auth_type,
            "headers": self.headers,
            "request_template": self.request_template,
            "payload_path": self.payload_path,
            "response_path": self.response_path,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_backoff": self.retry_backoff,
            "max_conversation_turns": self.max_conversation_turns,
            "adapter_type": self.adapter_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        return data


class Attack(Base):
    __tablename__ = "attacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attack_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    objective: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    template: Mapped[str] = mapped_column(Text)
    expected_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)

    is_original: Mapped[bool] = mapped_column(Boolean, default=True)
    base_attack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    variants: Mapped[list["AttackVariant"]] = relationship(
        back_populates="attack", cascade="all, delete-orphan"
    )
    results: Mapped[list["TestResult"]] = relationship(back_populates="attack")


class AttackVariant(Base):
    __tablename__ = "attack_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attack_id: Mapped[int] = mapped_column(
        ForeignKey("attacks.id", ondelete="CASCADE"), index=True
    )

    mutation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mutation_strategy: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attack: Mapped[Attack] = relationship(back_populates="variants")
    results: Mapped[list["TestResult"]] = relationship(back_populates="variant")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True
    )  # pending|running|completed|failed|cancelled

    config: Mapped[dict] = mapped_column(JSON, default=dict)
    attack_count: Mapped[int] = mapped_column(Integer, default=0)

    summary: Mapped[dict] = mapped_column(JSON, default=dict)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="scans")
    results: Mapped[list["TestResult"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="test_run")


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    attack_id: Mapped[int] = mapped_column(
        ForeignKey("attacks.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("attack_variants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    payload: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)

    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    classification: Mapped[str] = mapped_column(
        String(16), default="uncertain", index=True
    )  # blocked|partial|success|uncertain|error
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(16), default="info")

    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    layer_results: Mapped[dict] = mapped_column(JSON, default=dict)

    conversation: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    test_run: Mapped[TestRun] = relationship(back_populates="results")
    attack: Mapped[Attack] = relationship(back_populates="results")
    variant: Mapped[AttackVariant | None] = relationship(back_populates="results")

    @property
    def cached_evidence(self) -> dict:
        return self.evidence or {}


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    test_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_results.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    attack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attack_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    violated_boundary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reproduction: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    test_run: Mapped[TestRun] = relationship(back_populates="findings")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )

    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    breakdown: Mapped[list] = mapped_column(JSON, default=list)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    format: Mapped[str] = mapped_column(String(16), default="json")

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    test_run: Mapped[TestRun] = relationship(back_populates="reports")