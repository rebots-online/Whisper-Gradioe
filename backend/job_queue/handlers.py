"""
Job handlers for processing different types of jobs.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, Any

from backend.db.db_instance import get_db_session
from backend.models.workflow import Job
from backend.utils.tenant_utils import get_tenant_storage_path
from backend.job_queue.websocket_manager import connection_manager
from backend.routers.transcription.router import get_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def transcription_handler(job_data: Dict[str, Any], tenant_id: uuid.UUID):
    """
    Handler for transcription jobs.
    
    Args:
        job_data: Job data
        tenant_id: Tenant ID
    """
    job_id = uuid.UUID(job_data["job_id"])
    user_id = uuid.UUID(job_data["user_id"])
    file_path = job_data["file_path"]
    workflow_config = job_data.get("workflow_config", {})
    
    logger.info(f"Processing transcription job {job_id} for tenant {tenant_id}")
    
    # Get tenant-specific storage path
    tenant_storage_path = get_tenant_storage_path(tenant_id)
    output_dir = os.path.join(tenant_storage_path, "outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"transcription_{timestamp}_{job_id}.json"
    output_path = os.path.join(output_dir, output_filename)
    
    # Extract transcription parameters from workflow config
    transcription_params = {}
    if "nodes" in workflow_config:
        for node in workflow_config["nodes"]:
            if "type" in node and "transcription" in node["type"].lower():
                if "data" in node:
                    node_data = node["data"]
                    
                    # Extract parameters
                    if "modelSize" in node_data:
                        transcription_params["model_size"] = node_data["modelSize"]
                    if "whisperType" in node_data:
                        transcription_params["whisper_type"] = node_data["whisperType"]
                    if "language" in node_data:
                        transcription_params["language"] = node_data["language"]
                    if "computeType" in node_data:
                        transcription_params["compute_type"] = node_data["computeType"]
                    if "vad" in node_data:
                        transcription_params["vad"] = node_data["vad"]
                    if "diarization" in node_data:
                        transcription_params["diarization"] = node_data["diarization"]
    
    # Get transcription pipeline
    pipeline = get_pipeline()
    
    # Send progress update
    await connection_manager.broadcast_job_update(
        job_id=job_id,
        tenant_id=tenant_id,
        user_id=user_id,
        status="processing",
        result={"progress": 0}
    )
    
    try:
        # Record start time
        start_time = time.time()
        
        # Process transcription
        result = await asyncio.to_thread(
            pipeline.transcribe,
            audio=file_path,
            **transcription_params
        )
        
        # Calculate processing time
        processing_time = int(time.time() - start_time)
        
        # Save result to file
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
            
        # Update job in database
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            
            if job:
                job.status = "completed"
                job.result_path = output_path
                job.processing_time = processing_time
                job.completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.commit()
                
        # Send completion update
        await connection_manager.broadcast_job_update(
            job_id=job_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="completed",
            result={"path": output_path}
        )
        
        logger.info(f"Completed transcription job {job_id} in {processing_time} seconds")
        
    except Exception as e:
        logger.error(f"Error processing transcription job {job_id}: {str(e)}")
        
        # Update job in database
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            
            if job:
                job.status = "failed"
                job.error = str(e)
                job.updated_at = datetime.utcnow()
                db.commit()
                
        # Send error update
        await connection_manager.broadcast_job_update(
            job_id=job_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="failed",
            result={"error": str(e)}
        )
        
        # Re-raise exception
        raise


# Register handlers
def register_handlers():
    """
    Register job handlers.
    """
    from backend.job_queue import register_handler
    
    register_handler("transcription", transcription_handler)
