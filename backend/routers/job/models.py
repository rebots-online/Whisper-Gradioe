"""
Job models for job status polling.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import uuid

from backend.routers.workflow.models import WorkflowResponse


class JobBase(BaseModel):
    """
    Base job model.
    """
    workflow_id: Optional[uuid.UUID] = None
    file_path: str
    priority: int = 1

    @validator("priority")
    def validate_priority(cls, v):
        """
        Validate priority.
        """
        if v < 1 or v > 10:
            raise ValueError("Priority must be between 1 and 10")
        return v


class JobCreate(JobBase):
    """
    Job creation model.
    """
    pass


class JobUpdate(BaseModel):
    """
    Job update model.
    """
    status: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    processing_time: Optional[int] = None
    completed_at: Optional[datetime] = None

    @validator("status")
    def validate_status(cls, v):
        """
        Validate status.
        """
        if v is not None:
            allowed_statuses = ["queued", "processing", "completed", "failed", "canceled"]
            if v not in allowed_statuses:
                raise ValueError(f"Status must be one of {allowed_statuses}")
        return v


class JobResponse(BaseModel):
    """
    Job response model.
    """
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    file_path: str
    result_path: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class JobDetailResponse(JobResponse):
    """
    Detailed job response model.
    """
    error: Optional[str] = None
    processing_time: Optional[int] = None
    updated_at: datetime
    completed_at: Optional[datetime] = None
    workflow: Optional[WorkflowResponse] = None


class JobStatusResponse(BaseModel):
    """
    Job status response model.
    """
    id: uuid.UUID
    status: str
    result: Optional[Dict[str, Any]] = None
    updated_at: datetime

    class Config:
        orm_mode = True
