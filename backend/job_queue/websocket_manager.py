"""
WebSocket Manager for real-time job updates.

This module provides a WebSocket server for real-time job status updates
with tenant isolation.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
import jwt

from backend.config import settings
from backend.middleware.tenant_context import get_tenant_id

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager for real-time job updates.
    """
    
    def __init__(self):
        """
        Initialize the connection manager.
        """
        # Store active connections by tenant_id and user_id
        self.active_connections: Dict[uuid.UUID, Dict[uuid.UUID, List[WebSocket]]] = {}
        # Store job subscriptions by connection
        self.job_subscriptions: Dict[WebSocket, Set[uuid.UUID]] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, tenant_id: uuid.UUID, user_id: uuid.UUID):
        """
        Connect a WebSocket client.
        
        Args:
            websocket: WebSocket connection
            tenant_id: Tenant ID
            user_id: User ID
        """
        await websocket.accept()
        
        async with self._lock:
            # Initialize tenant dict if not exists
            if tenant_id not in self.active_connections:
                self.active_connections[tenant_id] = {}
                
            # Initialize user list if not exists
            if user_id not in self.active_connections[tenant_id]:
                self.active_connections[tenant_id][user_id] = []
                
            # Add connection to user list
            self.active_connections[tenant_id][user_id].append(websocket)
            
            # Initialize job subscriptions
            self.job_subscriptions[websocket] = set()
            
        logger.info(f"Client connected: tenant_id={tenant_id}, user_id={user_id}")
        
    async def disconnect(self, websocket: WebSocket, tenant_id: uuid.UUID, user_id: uuid.UUID):
        """
        Disconnect a WebSocket client.
        
        Args:
            websocket: WebSocket connection
            tenant_id: Tenant ID
            user_id: User ID
        """
        async with self._lock:
            # Remove connection from user list
            if (tenant_id in self.active_connections and 
                user_id in self.active_connections[tenant_id]):
                if websocket in self.active_connections[tenant_id][user_id]:
                    self.active_connections[tenant_id][user_id].remove(websocket)
                    
                # Remove user if no connections
                if not self.active_connections[tenant_id][user_id]:
                    del self.active_connections[tenant_id][user_id]
                    
                # Remove tenant if no users
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]
                    
            # Remove job subscriptions
            if websocket in self.job_subscriptions:
                del self.job_subscriptions[websocket]
                
        logger.info(f"Client disconnected: tenant_id={tenant_id}, user_id={user_id}")
        
    async def subscribe_to_job(self, websocket: WebSocket, job_id: uuid.UUID):
        """
        Subscribe to job updates.
        
        Args:
            websocket: WebSocket connection
            job_id: Job ID
        """
        async with self._lock:
            if websocket in self.job_subscriptions:
                self.job_subscriptions[websocket].add(job_id)
                
        logger.info(f"Client subscribed to job {job_id}")
        
    async def unsubscribe_from_job(self, websocket: WebSocket, job_id: uuid.UUID):
        """
        Unsubscribe from job updates.
        
        Args:
            websocket: WebSocket connection
            job_id: Job ID
        """
        async with self._lock:
            if websocket in self.job_subscriptions:
                if job_id in self.job_subscriptions[websocket]:
                    self.job_subscriptions[websocket].remove(job_id)
                    
        logger.info(f"Client unsubscribed from job {job_id}")
        
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        Send a message to a specific client.
        
        Args:
            message: Message to send
            websocket: WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to client: {str(e)}")
            
    async def broadcast_to_tenant(self, message: Dict[str, Any], tenant_id: uuid.UUID):
        """
        Broadcast a message to all clients in a tenant.
        
        Args:
            message: Message to send
            tenant_id: Tenant ID
        """
        if tenant_id not in self.active_connections:
            return
            
        for user_id, connections in self.active_connections[tenant_id].items():
            for connection in connections:
                await self.send_personal_message(message, connection)
                
    async def broadcast_to_user(self, message: Dict[str, Any], tenant_id: uuid.UUID, user_id: uuid.UUID):
        """
        Broadcast a message to all clients of a user.
        
        Args:
            message: Message to send
            tenant_id: Tenant ID
            user_id: User ID
        """
        if (tenant_id not in self.active_connections or 
            user_id not in self.active_connections[tenant_id]):
            return
            
        for connection in self.active_connections[tenant_id][user_id]:
            await self.send_personal_message(message, connection)
            
    async def broadcast_job_update(self, job_id: uuid.UUID, tenant_id: uuid.UUID, user_id: uuid.UUID, 
                                  status: str, result: Optional[Dict[str, Any]] = None):
        """
        Broadcast a job update to all subscribed clients.
        
        Args:
            job_id: Job ID
            tenant_id: Tenant ID
            user_id: User ID
            status: Job status
            result: Job result
        """
        message = {
            "type": "job_update",
            "job_id": str(job_id),
            "status": status
        }
        
        if result:
            message["result"] = result
            
        # Find all connections subscribed to this job
        subscribed_connections = []
        
        async with self._lock:
            for connection, subscriptions in self.job_subscriptions.items():
                if job_id in subscriptions:
                    subscribed_connections.append(connection)
                    
        # Send message to all subscribed connections
        for connection in subscribed_connections:
            await self.send_personal_message(message, connection)
            
        # Also send to all connections of the job owner
        await self.broadcast_to_user(message, tenant_id, user_id)


# Create global connection manager instance
connection_manager = ConnectionManager()


async def get_token_data(token: str) -> Dict[str, Any]:
    """
    Get token data from JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        Token data
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def websocket_auth(websocket: WebSocket) -> Dict[str, Any]:
    """
    Authenticate WebSocket connection.
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        Token data
        
    Raises:
        WebSocketDisconnect: If authentication fails
    """
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        
        if not token:
            # Try to get token from headers
            headers = dict(websocket.headers)
            auth_header = headers.get("authorization")
            
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                
        if not token:
            await websocket.close(code=1008, reason="Missing authentication token")
            raise WebSocketDisconnect(code=1008)
            
        # Validate token
        token_data = await get_token_data(token)
        
        return token_data
    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")
        raise WebSocketDisconnect(code=1008)
