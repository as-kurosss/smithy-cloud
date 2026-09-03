from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from smithy_cloud.models import (
    AgentStatus,
    CommandType,
    DeploymentStatus,
    LogLevel,
    LogSource,
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
