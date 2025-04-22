# Job Management and Polling System

This document describes the job management and polling system for the multi-tenant Whisper-WebUI application.

## Overview

The job management system provides a way to process transcription jobs asynchronously with tenant isolation. It includes:

1. **Job Queue**: A tenant-isolated queue for processing jobs
2. **WebSocket Server**: Real-time job status updates
3. **REST API**: Fallback polling mechanism for job status

## Job Queue

The job queue is implemented using Python's `queue.PriorityQueue` with tenant isolation. Each tenant has its own queue and worker thread to ensure fair resource allocation and prevent one tenant from monopolizing system resources.

### Key Features

- **Tenant Isolation**: Each tenant has its own queue and worker thread
- **Priority Queuing**: Jobs can be prioritized (lower number = higher priority)
- **Resource Allocation**: Resource usage is tracked and limited based on tenant subscription
- **Job Handlers**: Pluggable handlers for different job types (transcription, translation, etc.)

### Job Processing Flow

1. Job is created and stored in the database
2. Job is enqueued in the tenant's queue
3. Worker thread picks up the job and processes it
4. Job status is updated in the database
5. Job status updates are broadcast via WebSocket
6. Resource usage is recorded for billing purposes

## WebSocket Server

The WebSocket server provides real-time job status updates to clients. It supports:

- **Tenant Isolation**: Connections are authenticated and associated with a tenant
- **Job Subscriptions**: Clients can subscribe to specific job updates
- **Broadcast Updates**: Job status updates are broadcast to all subscribed clients
- **Connection Management**: Connections are tracked and managed by tenant and user

### WebSocket Protocol

#### Connection

Clients connect to the WebSocket server with a JWT token for authentication:

```
ws://example.com/ws?token=<jwt_token>
```

Or with an Authorization header:

```
Authorization: Bearer <jwt_token>
```

#### Messages

Clients can send the following messages:

1. **Subscribe to Job Updates**:
```json
{
  "type": "subscribe",
  "job_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

2. **Unsubscribe from Job Updates**:
```json
{
  "type": "unsubscribe",
  "job_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

3. **Ping** (keep-alive):
```json
{
  "type": "ping"
}
```

#### Server Responses

The server sends the following messages:

1. **Job Update**:
```json
{
  "type": "job_update",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "result": {
    "progress": 0.5
  }
}
```

2. **Subscription Confirmation**:
```json
{
  "type": "subscribed",
  "job_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

3. **Unsubscription Confirmation**:
```json
{
  "type": "unsubscribed",
  "job_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

4. **Pong** (keep-alive response):
```json
{
  "type": "pong"
}
```

5. **Error**:
```json
{
  "type": "error",
  "message": "Error message"
}
```

## REST API Polling

The REST API provides a fallback mechanism for clients that don't support WebSockets. It includes:

- **Job Creation**: Create new jobs
- **Job Status**: Get job status with ETag support for efficient polling
- **Job Management**: Cancel and retry jobs
- **Job Listing**: List jobs with filtering options

### Efficient Polling with ETags

The job status endpoint supports conditional requests with ETags to reduce unnecessary data transfer:

1. Client requests job status and receives an ETag
2. Client includes the ETag in subsequent requests
3. If the job status hasn't changed, the server returns 304 Not Modified
4. If the job status has changed, the server returns the new status with a new ETag

Example:

```http
GET /api/jobs/123e4567-e89b-12d3-a456-426614174000/status
If-None-Match: "processing_2023-04-22T12:34:56.789Z"
```

Response (no change):

```http
HTTP/1.1 304 Not Modified
ETag: "processing_2023-04-22T12:34:56.789Z"
```

Response (status changed):

```http
HTTP/1.1 200 OK
ETag: "completed_2023-04-22T12:35:00.000Z"
Content-Type: application/json

{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "result": {
    "path": "/storage/tenant-123/outputs/transcription_20230422_123500_123e4567-e89b-12d3-a456-426614174000.json"
  },
  "updated_at": "2023-04-22T12:35:00.000Z"
}
```

## Implementation Details

### Job Queue Manager

The job queue manager (`backend/job_queue/queue_manager.py`) provides:

- Job queue initialization and management
- Worker thread creation and management
- Job processing and status updates
- Resource usage tracking

### WebSocket Manager

The WebSocket manager (`backend/job_queue/websocket_manager.py`) provides:

- WebSocket connection management
- Job subscription management
- Message broadcasting
- Authentication and tenant isolation

### Job Router

The job router (`backend/routers/job/router.py`) provides:

- REST API endpoints for job management
- Job creation and listing
- Job status polling with ETag support
- Job cancellation and retry

## Usage Examples

### Creating a Job

```python
import requests

# Create a job
response = requests.post(
    "https://example.com/api/jobs",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
        "file_path": "/path/to/audio.mp3",
        "priority": 1
    }
)

job = response.json()
job_id = job["id"]
```

### Polling Job Status

```python
import requests
import time

# Poll job status
etag = None
while True:
    headers = {"Authorization": f"Bearer {token}"}
    if etag:
        headers["If-None-Match"] = etag
        
    response = requests.get(
        f"https://example.com/api/jobs/{job_id}/status",
        headers=headers
    )
    
    if response.status_code == 304:
        # No change, wait and try again
        time.sleep(1)
        continue
        
    if response.status_code == 200:
        # Get new ETag
        etag = response.headers.get("ETag")
        
        # Get job status
        status = response.json()
        
        if status["status"] in ["completed", "failed"]:
            # Job is done
            break
            
        # Wait and try again
        time.sleep(1)
```

### WebSocket Connection

```javascript
// Connect to WebSocket server
const socket = new WebSocket(`ws://example.com/ws?token=${token}`);

// Handle messages
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === "job_update") {
    // Handle job update
    console.log(`Job ${message.job_id} status: ${message.status}`);
    
    if (message.status === "completed") {
      // Handle completed job
      console.log(`Result: ${message.result.path}`);
    } else if (message.status === "failed") {
      // Handle failed job
      console.log(`Error: ${message.result.error}`);
    }
  }
};

// Subscribe to job updates
socket.onopen = () => {
  socket.send(JSON.stringify({
    type: "subscribe",
    job_id: "123e4567-e89b-12d3-a456-426614174000"
  }));
};
```
