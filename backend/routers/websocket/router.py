"""
WebSocket router for real-time job updates.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from backend.db.db_instance import get_db_session
from backend.models.workflow import Job
from backend.job_queue.websocket_manager import connection_manager, websocket_auth
from backend.utils.tenant_utils import get_tenant_record_or_404

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time job updates.
    """
    try:
        # Authenticate WebSocket connection
        token_data = await websocket_auth(websocket)
        
        # Extract tenant_id and user_id from token
        tenant_id = uuid.UUID(token_data.get("tenant_id"))
        user_id = uuid.UUID(token_data.get("sub"))
        
        # Connect WebSocket client
        await connection_manager.connect(websocket, tenant_id, user_id)
        
        try:
            # Process messages
            while True:
                # Receive message
                message = await websocket.receive_text()
                
                try:
                    # Parse message
                    data = json.loads(message)
                    
                    # Process message
                    await process_message(data, websocket, tenant_id, user_id)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON message: {message}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON message"
                    })
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
        except WebSocketDisconnect:
            # Disconnect WebSocket client
            await connection_manager.disconnect(websocket, tenant_id, user_id)
    except WebSocketDisconnect:
        # Authentication failed
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


async def process_message(data: Dict[str, Any], websocket: WebSocket, tenant_id: uuid.UUID, user_id: uuid.UUID):
    """
    Process WebSocket message.
    
    Args:
        data: Message data
        websocket: WebSocket connection
        tenant_id: Tenant ID
        user_id: User ID
    """
    message_type = data.get("type")
    
    if message_type == "subscribe":
        # Subscribe to job updates
        job_id = uuid.UUID(data.get("job_id"))
        
        # Verify job exists and user has access
        with get_db_session() as db:
            job = get_tenant_record_or_404(
                db=db,
                model=Job,
                record_id=job_id,
                tenant_id=tenant_id
            )
            
            # Check if user has access to the job
            if str(job.user_id) != str(user_id) and data.get("role") != "admin":
                await websocket.send_json({
                    "type": "error",
                    "message": "Not authorized to access this job"
                })
                return
                
        # Subscribe to job updates
        await connection_manager.subscribe_to_job(websocket, job_id)
        
        # Send acknowledgement
        await websocket.send_json({
            "type": "subscribed",
            "job_id": str(job_id)
        })
        
        # Send current job status
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            
            if job:
                result = None
                if job.status == "completed" and job.result_path:
                    result = {
                        "path": job.result_path
                    }
                    
                await websocket.send_json({
                    "type": "job_update",
                    "job_id": str(job_id),
                    "status": job.status,
                    "result": result
                })
    elif message_type == "unsubscribe":
        # Unsubscribe from job updates
        job_id = uuid.UUID(data.get("job_id"))
        
        # Unsubscribe from job updates
        await connection_manager.unsubscribe_from_job(websocket, job_id)
        
        # Send acknowledgement
        await websocket.send_json({
            "type": "unsubscribed",
            "job_id": str(job_id)
        })
    elif message_type == "ping":
        # Ping-pong for connection keep-alive
        await websocket.send_json({
            "type": "pong"
        })
    else:
        # Unknown message type
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        })
