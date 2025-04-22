"""
Job router for job status polling.
"""

import logging
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session

from backend.db.db_instance import get_db_session
from backend.models.workflow import Job
from backend.middleware.tenant_context import tenant_required
from backend.utils.tenant_utils import (
    get_tenant_record_or_404,
    get_tenant_records,
    create_tenant_record,
    update_tenant_record,
    delete_tenant_record
)
from backend.job_queue import enqueue_job
from .models import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobDetailResponse,
    JobStatusResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

job_router = APIRouter()


@job_router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
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
            model=Job,
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
    
    # Enqueue job for processing
    enqueue_job(job.id, auth["tenant_id"], job_data.priority)
    
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


@job_router.get("/", response_model=List[JobResponse])
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


@job_router.get("/{job_id}", response_model=JobDetailResponse)
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


@job_router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    response: Response,
    etag: Optional[str] = None,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Get job status.
    
    Args:
        job_id: Job ID
        response: Response object
        etag: ETag for conditional request
        db: Database session
        auth: Authentication data
        
    Returns:
        Job status
        
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
    
    # Generate ETag based on job status and updated_at
    current_etag = f"\"{job.status}_{job.updated_at.isoformat()}\""
    
    # Set ETag header
    response.headers["ETag"] = current_etag
    
    # Check if ETag matches
    if etag and etag == current_etag:
        # Return 304 Not Modified if ETag matches
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return None
    
    # Prepare result
    result = None
    if job.status == "completed" and job.result_path:
        result = {
            "path": job.result_path
        }
    elif job.status == "failed" and job.error:
        result = {
            "error": job.error
        }
    
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        result=result,
        updated_at=job.updated_at
    )


@job_router.put("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Cancel a job.
    
    Args:
        job_id: Job ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Updated job
        
    Raises:
        HTTPException: If the job is not found, the user is not authorized, or the job cannot be canceled
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
            detail="Not authorized to cancel this job"
        )
    
    # Check if job can be canceled
    if job.status not in ["queued", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job cannot be canceled in status: {job.status}"
        )
    
    # Update job status
    job_data = {
        "status": "canceled"
    }
    
    updated_job = update_tenant_record(
        db=db,
        model=Job,
        record_id=job_id,
        data=job_data,
        tenant_id=auth["tenant_id"]
    )
    
    if not updated_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return JobResponse(
        id=updated_job.id,
        tenant_id=updated_job.tenant_id,
        user_id=updated_job.user_id,
        workflow_id=updated_job.workflow_id,
        status=updated_job.status,
        file_path=updated_job.file_path,
        result_path=updated_job.result_path,
        created_at=updated_job.created_at
    )


@job_router.put("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    auth: dict = Depends(tenant_required())
):
    """
    Retry a failed job.
    
    Args:
        job_id: Job ID
        db: Database session
        auth: Authentication data
        
    Returns:
        Updated job
        
    Raises:
        HTTPException: If the job is not found, the user is not authorized, or the job cannot be retried
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
            detail="Not authorized to retry this job"
        )
    
    # Check if job can be retried
    if job.status not in ["failed", "canceled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job cannot be retried in status: {job.status}"
        )
    
    # Update job status
    job_data = {
        "status": "queued",
        "error": None
    }
    
    updated_job = update_tenant_record(
        db=db,
        model=Job,
        record_id=job_id,
        data=job_data,
        tenant_id=auth["tenant_id"]
    )
    
    if not updated_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Enqueue job for processing
    enqueue_job(updated_job.id, auth["tenant_id"])
    
    return JobResponse(
        id=updated_job.id,
        tenant_id=updated_job.tenant_id,
        user_id=updated_job.user_id,
        workflow_id=updated_job.workflow_id,
        status=updated_job.status,
        file_path=updated_job.file_path,
        result_path=updated_job.result_path,
        created_at=updated_job.created_at
    )
