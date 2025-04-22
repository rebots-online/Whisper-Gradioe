"""
Workflow models for multi-tenant support.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import uuid


class WorkflowBase(BaseModel):
    """
    Base workflow model.
    """
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    is_template: bool = False
    is_public: bool = False


class WorkflowCreate(WorkflowBase):
    """
    Workflow creation model.
    """
    pass


class WorkflowUpdate(BaseModel):
    """
    Workflow update model.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_template: Optional[bool] = None
    is_public: Optional[bool] = None


class WorkflowResponse(WorkflowBase):
    """
    Workflow response model.
    """
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class JobBase(BaseModel):
    """
    Base job model.
    """
    workflow_id: Optional[uuid.UUID] = None
    file_path: str


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
            allowed_statuses = ["queued", "processing", "completed", "failed"]
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
