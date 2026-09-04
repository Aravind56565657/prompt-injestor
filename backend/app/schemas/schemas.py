from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class HeaderItem(BaseModel):
    key: str
    value: str


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    url: str = Field(min_length=1, max_length=2048)
    http_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    auth_type: Literal["none", "bearer", "api_key", "basic"] = "none"
    auth_token: Optional[str] = None
    request_template: dict[str, Any] = Field(default_factory=dict)
    payload_path: str = Field(default="message")
    response_path: Optional[str] = None
    timeout: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=2, ge=0, le=10)
    retry_backoff: float = Field(default=1.0, ge=0, le=60)
    max_conversation_turns: int = Field(default=0, ge=0, le=50)
    adapter_type: Literal["http", "openai", "mock"] = "http"
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def url_must_be_http(self) -> "TargetCreate":
        v = self.url
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return self


class TargetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    http_method: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    request_template: Optional[dict[str, Any]] = None
    payload_path: Optional[str] = None
    response_path: Optional[str] = None
    timeout: Optional[int] = None
    retry_count: Optional[int] = None
    retry_backoff: Optional[float] = None
    max_conversation_turns: Optional[int] = None
    adapter_type: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    url: str
    http_method: str
    headers: dict[str, str] = {}
    auth_type: str = "none"
    request_template: dict[str, Any] = {}
    payload_path: str = "message"
    response_path: Optional[str] = None
    timeout: int = 30
    retry_count: int = 2
    retry_backoff: float = 1.0
    max_conversation_turns: int = 0
    adapter_type: str = "http"
    meta: dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScanConfig(BaseModel):
    attack_categories: Optional[list[str]] = None
    attack_ids: Optional[list[str]] = None
    max_attacks: int = Field(default=50, ge=1, le=500)
    concurrency: int = Field(default=5, ge=1, le=32)
    include_generated: bool = True
    include_mutations: bool = True
    mutation_count_per_attack: int = Field(default=3, ge=0, le=10)
    multi_turn_enabled: bool = True
    max_turns: int = Field(default=3, ge=1, le=10)
    rate_limit_per_second: float = Field(default=10, gt=0, le=100)
    timeout: int = Field(default=30, ge=1, le=300)
    regard_severity_filter: Optional[int] = None


class ScanCreate(BaseModel):
    target_id: int
    name: Optional[str] = None
    config: ScanConfig = Field(default_factory=ScanConfig)


class ScanSummary(BaseModel):
    total: int = 0
    success: int = 0
    partial: int = 0
    blocked: int = 0
    uncertain: int = 0
    error: int = 0
    overall_risk: str = "unknown"
    avg_confidence: float = 0.0


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: int
    name: Optional[str] = None
    status: str
    attack_count: int = 0
    config: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class TestResultOut(BaseModel):
    id: int
    test_run_id: int
    attack_id: int
    payload: str
    response: Optional[str] = None
    http_status: Optional[int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    classification: str
    confidence: float
    severity: str
    evidence: dict[str, Any] = {}
    layer_results: dict[str, Any] = {}
    attack_meta: Optional[dict[str, Any]] = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    test_run_id: int
    title: str
    category: str
    severity: str
    confidence: float
    attack_id: Optional[str] = None
    attack_objective: Optional[str] = None
    payload: Optional[str] = None
    target_response: Optional[str] = None
    evidence: Optional[str] = None
    violated_boundary: Optional[str] = None
    root_cause: Optional[str] = None
    remediation: Optional[str] = None
    reproduction: dict[str, Any] = {}
    created_at: Optional[datetime] = None


class AttackInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    attack_id: str
    category: str
    objective: str
    severity: str
    template: str
    tags: list[str] = []
    is_original: bool = True
    base_attack_id: Optional[str] = None


class RerunRequest(BaseModel):
    config: Optional[ScanConfig] = None