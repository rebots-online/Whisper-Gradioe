"""
Job Queue Manager for multi-tenant transcription processing.

This module provides a job queue system with tenant isolation for processing
transcription jobs in a multi-tenant environment.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable
import threading
import queue

from sqlalchemy.orm import Session

from backend.db.db_instance import get_db_session
from backend.models.workflow import Job, UsageRecord
from backend.models.tenant import Tenant
from backend.utils.tenant_utils import get_tenant_storage_path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobQueue:
    """
    Job queue for processing transcription jobs with tenant isolation.
    """
    
    def __init__(self):
        """
        Initialize the job queue.
        """
        self._queues: Dict[uuid.UUID, queue.PriorityQueue] = {}
        self._workers: Dict[uuid.UUID, threading.Thread] = {}
        self._running = False
        self._lock = threading.Lock()
        self._job_handlers: Dict[str, Callable[[Dict[str, Any], uuid.UUID], Awaitable[None]]] = {}
        self._max_workers_per_tenant = 2  # Default max workers per tenant
        
    def start(self):
        """
        Start the job queue.
        """
        if self._running:
            return
            
        self._running = True
        logger.info("Job queue started")
        
    def stop(self):
        """
        Stop the job queue.
        """
        if not self._running:
            return
            
        self._running = False
        
        # Stop all workers
        for tenant_id, worker in self._workers.items():
            logger.info(f"Stopping worker for tenant {tenant_id}")
            # Workers will check self._running and exit
            
        # Wait for all workers to stop
        for tenant_id, worker in self._workers.items():
            if worker.is_alive():
                worker.join(timeout=5.0)
                
        logger.info("Job queue stopped")
        
    def register_handler(self, job_type: str, handler: Callable[[Dict[str, Any], uuid.UUID], Awaitable[None]]):
        """
        Register a handler for a specific job type.
        
        Args:
            job_type: Type of job to handle
            handler: Async function to handle the job
        """
        self._job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
        
    def enqueue_job(self, job_id: uuid.UUID, tenant_id: uuid.UUID, priority: int = 1):
        """
        Enqueue a job for processing.
        
        Args:
            job_id: Job ID
            tenant_id: Tenant ID
            priority: Job priority (lower number = higher priority)
        """
        with self._lock:
            # Create queue for tenant if it doesn't exist
            if tenant_id not in self._queues:
                self._queues[tenant_id] = queue.PriorityQueue()
                
            # Create worker for tenant if it doesn't exist
            if tenant_id not in self._workers or not self._workers[tenant_id].is_alive():
                worker = threading.Thread(
                    target=self._worker_thread,
                    args=(tenant_id,),
                    daemon=True
                )
                self._workers[tenant_id] = worker
                worker.start()
                
            # Enqueue job
            self._queues[tenant_id].put((priority, job_id))
            logger.info(f"Enqueued job {job_id} for tenant {tenant_id} with priority {priority}")
            
    def _worker_thread(self, tenant_id: uuid.UUID):
        """
        Worker thread for processing jobs for a specific tenant.
        
        Args:
            tenant_id: Tenant ID
        """
        logger.info(f"Started worker thread for tenant {tenant_id}")
        
        while self._running:
            try:
                # Get job from queue with timeout
                try:
                    priority, job_id = self._queues[tenant_id].get(timeout=1.0)
                except queue.Empty:
                    continue
                    
                # Process job
                try:
                    logger.info(f"Processing job {job_id} for tenant {tenant_id}")
                    self._process_job(job_id, tenant_id)
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {str(e)}")
                    # Update job status to failed
                    self._update_job_status(job_id, "failed", error=str(e))
                finally:
                    # Mark job as done in queue
                    self._queues[tenant_id].task_done()
            except Exception as e:
                logger.error(f"Error in worker thread for tenant {tenant_id}: {str(e)}")
                time.sleep(1.0)  # Avoid tight loop on error
                
        logger.info(f"Stopped worker thread for tenant {tenant_id}")
        
    def _process_job(self, job_id: uuid.UUID, tenant_id: uuid.UUID):
        """
        Process a job.
        
        Args:
            job_id: Job ID
            tenant_id: Tenant ID
        """
        # Get job from database
        with get_db_session() as db:
            job = db.query(Job).filter(
                Job.id == job_id,
                Job.tenant_id == tenant_id
            ).first()
            
            if not job:
                logger.error(f"Job {job_id} not found for tenant {tenant_id}")
                return
                
            # Check if job is already being processed or completed
            if job.status in ["processing", "completed", "failed"]:
                logger.info(f"Job {job_id} is already {job.status}")
                return
                
            # Update job status to processing
            job.status = "processing"
            job.updated_at = datetime.utcnow()
            db.commit()
            
            # Get workflow configuration
            workflow_config = {}
            if job.workflow_id:
                workflow = job.workflow
                if workflow:
                    try:
                        workflow_config = json.loads(workflow.config)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid workflow configuration for workflow {workflow.id}")
                        workflow_config = {}
            
            # Prepare job data
            job_data = {
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "user_id": str(job.user_id),
                "file_path": job.file_path,
                "workflow_config": workflow_config
            }
            
        # Process job asynchronously
        asyncio.run(self._process_job_async(job_data, tenant_id))
        
    async def _process_job_async(self, job_data: Dict[str, Any], tenant_id: uuid.UUID):
        """
        Process a job asynchronously.
        
        Args:
            job_data: Job data
            tenant_id: Tenant ID
        """
        job_id = uuid.UUID(job_data["job_id"])
        
        try:
            # Determine job type from workflow config or file extension
            job_type = "transcription"  # Default job type
            
            if "job_type" in job_data:
                job_type = job_data["job_type"]
            elif "workflow_config" in job_data and job_data["workflow_config"]:
                # Extract job type from workflow config
                if "nodes" in job_data["workflow_config"]:
                    for node in job_data["workflow_config"]["nodes"]:
                        if "type" in node:
                            if "transcription" in node["type"].lower():
                                job_type = "transcription"
                            elif "translation" in node["type"].lower():
                                job_type = "translation"
                            elif "diarization" in node["type"].lower():
                                job_type = "diarization"
                            # Add more job types as needed
            
            # Check if handler exists for job type
            if job_type not in self._job_handlers:
                raise ValueError(f"No handler registered for job type: {job_type}")
                
            # Call handler
            await self._job_handlers[job_type](job_data, tenant_id)
            
            # Update job status to completed
            self._update_job_status(job_id, "completed")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            # Update job status to failed
            self._update_job_status(job_id, "failed", error=str(e))
            
    def _update_job_status(self, job_id: uuid.UUID, status: str, result_path: Optional[str] = None, 
                          error: Optional[str] = None, processing_time: Optional[int] = None):
        """
        Update job status in the database.
        
        Args:
            job_id: Job ID
            status: New status
            result_path: Path to result files
            error: Error message
            processing_time: Processing time in seconds
        """
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            
            if not job:
                logger.error(f"Job {job_id} not found")
                return
                
            job.status = status
            job.updated_at = datetime.utcnow()
            
            if status == "completed":
                job.completed_at = datetime.utcnow()
                
            if result_path:
                job.result_path = result_path
                
            if error:
                job.error = error
                
            if processing_time:
                job.processing_time = processing_time
                
            db.commit()
            
            # Record usage for completed jobs
            if status == "completed" and processing_time:
                self._record_usage(db, job, processing_time)
                
    def _record_usage(self, db: Session, job: Job, processing_time: int):
        """
        Record resource usage for a job.
        
        Args:
            db: Database session
            job: Job object
            processing_time: Processing time in seconds
        """
        # Record processing time usage
        processing_usage = UsageRecord(
            tenant_id=job.tenant_id,
            user_id=job.user_id,
            job_id=job.id,
            resource_type="processing",
            amount=processing_time,
            unit="seconds"
        )
        db.add(processing_usage)
        
        # Record storage usage if result path exists
        if job.result_path and os.path.exists(job.result_path):
            try:
                # Calculate file size in MB
                file_size_mb = os.path.getsize(job.result_path) / (1024 * 1024)
                
                storage_usage = UsageRecord(
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    job_id=job.id,
                    resource_type="storage",
                    amount=file_size_mb,
                    unit="MB"
                )
                db.add(storage_usage)
            except OSError as e:
                logger.error(f"Error calculating file size for {job.result_path}: {str(e)}")
                
        db.commit()
        
    def set_max_workers_per_tenant(self, tenant_id: uuid.UUID, max_workers: int):
        """
        Set the maximum number of worker threads for a tenant.
        
        Args:
            tenant_id: Tenant ID
            max_workers: Maximum number of worker threads
        """
        # Not implemented yet - would require multiple workers per tenant
        self._max_workers_per_tenant = max_workers
        
    def get_queue_length(self, tenant_id: uuid.UUID) -> int:
        """
        Get the number of jobs in the queue for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Number of jobs in the queue
        """
        with self._lock:
            if tenant_id not in self._queues:
                return 0
                
            return self._queues[tenant_id].qsize()
            
    def get_active_tenants(self) -> List[uuid.UUID]:
        """
        Get a list of tenant IDs with active queues.
        
        Returns:
            List of tenant IDs
        """
        with self._lock:
            return list(self._queues.keys())


# Create global job queue instance
job_queue = JobQueue()


def start_job_queue():
    """
    Start the job queue.
    """
    job_queue.start()
    
    
def stop_job_queue():
    """
    Stop the job queue.
    """
    job_queue.stop()
    
    
def enqueue_job(job_id: uuid.UUID, tenant_id: uuid.UUID, priority: int = 1):
    """
    Enqueue a job for processing.
    
    Args:
        job_id: Job ID
        tenant_id: Tenant ID
        priority: Job priority (lower number = higher priority)
    """
    job_queue.enqueue_job(job_id, tenant_id, priority)
    
    
def register_handler(job_type: str, handler: Callable[[Dict[str, Any], uuid.UUID], Awaitable[None]]):
    """
    Register a handler for a specific job type.
    
    Args:
        job_type: Type of job to handle
        handler: Async function to handle the job
    """
    job_queue.register_handler(job_type, handler)
