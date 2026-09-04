from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from smithy_cloud.models import (
    AgentStatus,
    CommandType,
    DeploymentStatus,
    LogLevel,
    LogSource,
    QueueItemStatus,
    RunStatus,
)

# --- Agent schemas ---


class AgentCreate(BaseModel):
    name: str
    url: str
    capabilities: list[str] = Field(default_factory=list)


class DeploymentAck(BaseModel):
    status: Literal["deployed", "failed"]
    error: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    status: AgentStatus
    last_heartbeat: datetime | None
    capabilities: list[str]
    created_at: datetime


class AgentRegisterResponse(AgentResponse):
    """Returned once at registration/rotation — the only time the secret is visible."""

    secret: str


class AgentHeartbeat(BaseModel):
    status: AgentStatus = AgentStatus.ONLINE


class AgentCommand(BaseModel):
    command: CommandType
    process_id: uuid.UUID
    run_id: uuid.UUID | None = None
    process_data: dict[str, Any] | None = None  # files, entry_point, requirements for deploy


# --- User auth schemas ---


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or len(normalized) > 320:
            raise ValueError("Invalid email address")
        return normalized


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


# --- Process schemas ---


class ProcessCreate(BaseModel):
    name: str
    description: str | None = None
    entry_point: str = "main.py"
    files: dict[str, str] = Field(default_factory=dict)
    requirements: list[str] = Field(default_factory=list)


class ProcessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    entry_point: str | None = None
    files: dict[str, str] | None = None
    requirements: list[str] | None = None


class ProcessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    entry_point: str
    files: dict[str, str]
    requirements: list[str]
    created_at: datetime
    updated_at: datetime


# --- ProcessDeployment schemas ---


class DeployRequest(BaseModel):
    agent_id: uuid.UUID


class RunRequest(BaseModel):
    agent_id: uuid.UUID


class ProcessDeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    process_id: uuid.UUID
    agent_id: uuid.UUID
    status: DeploymentStatus
    deployed_at: datetime | None


# --- ProcessRun schemas ---


class ProcessRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    process_id: uuid.UUID
    agent_id: uuid.UUID
    deployment_id: uuid.UUID | None
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


# --- ProcessLog schemas ---


class AgentLogEntry(BaseModel):
    timestamp: datetime
    level: LogLevel = LogLevel.INFO
    source: LogSource = LogSource.STDOUT
    message: str
    details: dict[str, Any] | None = None


class AgentLogPush(BaseModel):
    run_id: uuid.UUID
    logs: list[AgentLogEntry]


class AgentStatusUpdate(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    error: str | None = None


class ProcessLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    timestamp: datetime
    level: LogLevel
    source: LogSource
    message: str
    details: dict[str, Any] | None


class ProcessLogEntry(ProcessLogResponse):
    """A log row annotated with its process (for the global Logs page)."""

    process_id: uuid.UUID
    process_name: str


# --- Trigger schemas (one-shot scheduled runs) ---


class TriggerCreate(BaseModel):
    name: str
    agent_id: uuid.UUID
    process_id: uuid.UUID
    run_at: AwareDatetime
    enabled: bool = True


class TriggerUpdate(BaseModel):
    enabled: bool | None = None
    run_at: AwareDatetime | None = None


class TriggerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    agent_id: uuid.UUID
    process_id: uuid.UUID
    agent_name: str
    process_name: str
    run_at: datetime
    enabled: bool
    fired_at: datetime | None
    last_run_id: uuid.UUID | None
    created_at: datetime
    status: Literal["scheduled", "fired", "disabled"]


# --- Queue schemas (transactional items, REFramework-style) ---


class QueueCreate(BaseModel):
    name: str
    max_attempts: int = Field(default=3, ge=1)


class QueueCounts(BaseModel):
    new: int = 0
    in_progress: int = 0
    success: int = 0
    business_failed: int = 0
    system_failed: int = 0


class QueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    max_attempts: int
    created_at: datetime


class QueueWithCounts(QueueResponse):
    counts: QueueCounts


class QueueItemAdd(BaseModel):
    payload: dict[str, Any]
    idempotency_key: str | None = None


class QueueItemsAddRequest(BaseModel):
    items: list[QueueItemAdd]


class QueueItemCreated(BaseModel):
    id: uuid.UUID
    status: QueueItemStatus
    attempts: int


class ClaimRequest(BaseModel):
    run_id: uuid.UUID
    lease_seconds: int = Field(default=300, ge=1)


class ClaimedItem(BaseModel):
    id: uuid.UUID
    payload: dict[str, Any]
    attempts: int
    lease_expires_at: datetime


class ClaimResponse(BaseModel):
    item: ClaimedItem | None


class CompleteRequest(BaseModel):
    run_id: uuid.UUID
    status: Literal["success", "business_failed", "system_failed"]
    error: str | None = None
    result: dict[str, Any] | None = None


class QueueItemState(BaseModel):
    id: uuid.UUID
    status: QueueItemStatus
    attempts: int


class HeartbeatRequest(BaseModel):
    run_id: uuid.UUID
    lease_seconds: int = Field(default=300, ge=1)


class HeartbeatResponse(BaseModel):
    id: uuid.UUID
    lease_expires_at: datetime
