"""
Workflow router for multi-tenant support.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import uuid

from backend.db.db_instance import get_db_session
from backend.models.workflow import Workflow, Job
from backend.middleware.tenant_context import tenant_required, get_tenant_id
from backend.utils.tenant_utils import (
    get_tenant_record_or_404,
    get_tenant_records,
    create_tenant_record,
    update_tenant_record,
    delete_tenant_record
)
from .models import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    JobCreate,
    JobResponse,
    JobDetailResponse
)

workflow_router = APIRouter()


@workflow_router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowCreate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Create a new workflow.
    
    Args:
        workflow_data: Workflow data
        db: Database session
        auth: Authentication data
        
    Returns:
        Created workflow
    """
    # Create workflow with tenant context
    workflow = create_tenant_record(
        db=db,
        model=Workflow,
        data={
            "name": workflow_data.name,
            "description": workflow_data.description,
            "config": workflow_data.config,
            "is_template": workflow_data.is_template,
            "is_public": workflow_data.is_public,
            "user_id": auth["user_id"]
        },
        tenant_id=auth["tenant_id"]
    )
    
    return WorkflowResponse(
        id=workflow.id,
        tenant_id=workflow.tenant_id,
        user_id=workflow.user_id,
        name=workflow.name,
        description=workflow.description,
        config=workflow.config,
        is_template=workflow.is_template,
        is_public=workflow.is_public,
        created_at=workflow.created_at
    )


@workflow_router.get("/", response_model=List[WorkflowResponse])
async def get_workflows(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    is_template: Optional[bool] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Get all workflows for the current tenant.
    
    Args:
        skip: Number of workflows to skip
        limit: Maximum number of workflows to return
        name: Filter by name
        is_template: Filter by template status
        is_public: Filter by public status
        db: Database session
        auth: Authentication data
        
    Returns:
        List of workflows
    """
    # Build query
    query = db.query(Workflow).filter(Workflow.tenant_id == auth["tenant_id"])
    
    # Apply filters
    if name:
        query = query.filter(Workflow.name.ilike(f"%{name}%"))
    
    if is_template is not None:
        query = query.filter(Workflow.is_template == is_template)
    
    if is_public is not None:
        query = query.filter(Workflow.is_public == is_public)
    
    # Get workflows
    workflows = query.offset(skip).limit(limit).all()
    
    return workflows


@workflow_router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Get a workflow by ID.
    
    Args:
        workflow_id: Workflow ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Workflow
        
    Raises:
        HTTPException: If the workflow is not found
    """
    # Get workflow with tenant isolation
    workflow = get_tenant_record_or_404(
        db=db,
        model=Workflow,
        record_id=workflow_id,
        tenant_id=auth["tenant_id"]
    )
    
    # Check if user has access to the workflow
    if not workflow.is_public and str(workflow.user_id) != str(auth["user_id"]) and auth["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this workflow"
        )
    
    return workflow


@workflow_router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    workflow_data: WorkflowUpdate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Update a workflow.
    
    Args:
        workflow_id: Workflow ID
        workflow_data: Workflow data
        db: Database session
        auth: Authentication data
        
    Returns:
        Updated workflow
        
    Raises:
        HTTPException: If the workflow is not found or the user is not authorized
    """
    # Get workflow with tenant isolation
    workflow = get_tenant_record_or_404(
        db=db,
        model=Workflow,
        record_id=workflow_id,
        tenant_id=auth["tenant_id"]
    )
    
    # Check if user has permission to update the workflow
    if str(workflow.user_id) != str(auth["user_id"]) and auth["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this workflow"
        )
    
    # Update workflow
    updated_workflow = update_tenant_record(
        db=db,
        model=Workflow,
        record_id=workflow_id,
        data=workflow_data.dict(exclude_unset=True),
        tenant_id=auth["tenant_id"]
    )
    
    if not updated_workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    return updated_workflow


@workflow_router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Delete a workflow.
    
    Args:
        workflow_id: Workflow ID
        db: Database session
        auth: Authentication data
        
    Raises:
        HTTPException: If the workflow is not found or the user is not authorized
    """
    # Get workflow with tenant isolation
    workflow = get_tenant_record_or_404(
        db=db,
        model=Workflow,
        record_id=workflow_id,
        tenant_id=auth["tenant_id"]
    )
    
    # Check if user has permission to delete the workflow
    if str(workflow.user_id) != str(auth["user_id"]) and auth["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this workflow"
        )
    
    # Delete workflow
    success = delete_tenant_record(
        db=db,
        model=Workflow,
        record_id=workflow_id,
        tenant_id=auth["tenant_id"]
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    return None


# Job endpoints

@workflow_router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Create a new job.
    
    Args:
        job_data: Job data
        db: Database session
        auth: Authentication data
        
    Returns:
        Created job
        
    Raises:
        HTTPException: If the workflow is not found
    """
    # Check if workflow exists and user has access
    if job_data.workflow_id:
        workflow = get_tenant_record_or_404(
            db=db,
            model=Workflow,
            record_id=job_data.workflow_id,
            tenant_id=auth["tenant_id"]
        )
        
        # Check if user has access to the workflow
        if not workflow.is_public and str(workflow.user_id) != str(auth["user_id"]) and auth["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to use this workflow"
            )
    
    # Create job with tenant context
    job = create_tenant_record(
        db=db,
        model=Job,
        data={
            "workflow_id": job_data.workflow_id,
            "file_path": job_data.file_path,
            "status": "queued",
            "user_id": auth["user_id"]
        },
        tenant_id=auth["tenant_id"]
    )
    
    return JobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        user_id=job.user_id,
        workflow_id=job.workflow_id,
        status=job.status,
        file_path=job.file_path,
        result_path=job.result_path,
        created_at=job.created_at
    )


@workflow_router.get("/jobs", response_model=List[JobResponse])
async def get_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    workflow_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Get all jobs for the current tenant.
    
    Args:
        skip: Number of jobs to skip
        limit: Maximum number of jobs to return
        status: Filter by status
        workflow_id: Filter by workflow ID
        db: Database session
        auth: Authentication data
        
    Returns:
        List of jobs
    """
    # Build query
    query = db.query(Job).filter(Job.tenant_id == auth["tenant_id"])
    
    # Apply filters
    if status:
        query = query.filter(Job.status == status)
    
    if workflow_id:
        query = query.filter(Job.workflow_id == workflow_id)
    
    # Filter by user if not admin
    if auth["role"] != "admin":
        query = query.filter(Job.user_id == auth["user_id"])
    
    # Get jobs
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    return jobs


@workflow_router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Get a job by ID.
    
    Args:
        job_id: Job ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Job
        
    Raises:
        HTTPException: If the job is not found or the user is not authorized
    """
    # Get job with tenant isolation
    job = get_tenant_record_or_404(
        db=db,
        model=Job,
        record_id=job_id,
        tenant_id=auth["tenant_id"]
    )
    
    # Check if user has access to the job
    if str(job.user_id) != str(auth["user_id"]) and auth["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job"
        )
    
    return JobDetailResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        user_id=job.user_id,
        workflow_id=job.workflow_id,
        status=job.status,
        file_path=job.file_path,
        result_path=job.result_path,
        error=job.error,
        processing_time=job.processing_time,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        workflow=job.workflow
    )
