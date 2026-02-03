# Phase 10: Real-Time Async Execution

## Overview

Transform code execution from synchronous to asynchronous with real-time WebSocket updates. This provides better UX for longer-running code and prepares the architecture for Kubernetes-based execution in Phase 11.

## Goals

1. **Non-blocking execution** - Submit code, get job ID immediately
2. **Real-time updates** - WebSocket pushes status changes as they happen
3. **Reliability** - SQS FIFO ensures ordered, at-least-once delivery
4. **Graceful fallback** - HTTP polling available if WebSocket fails

## Architecture

```
┌─────────────┐    POST /execute    ┌─────────────────────┐
│   Frontend  │──────────────────▶ │    API Lambda       │
│   (React)   │◀─────────────────── │  (Returns job_id)   │
└─────────────┘    {job_id}         └──────────┬──────────┘
       │                                       │
       │ WebSocket                    SQS FIFO │
       ▼                                       ▼
┌─────────────────────┐              ┌─────────────────────┐
│  WebSocket API GW   │◀─────────────│   Worker Lambda     │
│  ($connect, $default)              │  (Executes code)    │
└─────────────────────┘   Push via   └──────────┬──────────┘
                          API GW                │
                          Management            │ Read/Write
                          API                   ▼
                                      ┌─────────────────────┐
                                      │     DynamoDB        │
                                      │  Jobs | Connections │
                                      └─────────────────────┘
```

## Data Flow

### Submit Execution
1. User clicks "Run" → POST `/execute` with code
2. API Lambda creates job in DynamoDB (status: `pending`)
3. API Lambda sends message to SQS FIFO
4. API Lambda returns `{job_id, status: "pending"}`
5. Frontend subscribes to WebSocket for job updates

### Execute Code
1. Worker Lambda receives SQS message
2. Updates job status to `running`
3. Pushes status update via WebSocket
4. Executes code in sandbox
5. Updates job with result (status: `completed`/`failed`)
6. Pushes final result via WebSocket
7. Deletes SQS message

### Connection Management
1. Frontend connects to WebSocket with JWT in query string
2. `$connect` handler validates JWT, stores connection in DynamoDB
3. Frontend sends `{action: "subscribe", job_id: "..."}` 
4. `$default` handler adds job_id to connection's subscribed_jobs set
5. On disconnect, `$disconnect` handler removes connection record

## Implementation

### Backend Services

#### Job Service

```python
# api/services/job_service.py

import json
import uuid
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from backend.common.config import settings


class JobService:
    """Manages job lifecycle and DynamoDB persistence."""
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.sqs = boto3.client("sqs")
        self.jobs_table = self.dynamodb.Table(settings.JOBS_TABLE_NAME)
        self.queue_url = settings.EXECUTION_QUEUE_URL
    
    def create_job(self, user_id: str, code: str, timeout: int = 30) -> dict:
        """Create a new execution job."""
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ttl = int((now + timedelta(hours=24)).timestamp())
        
        item = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",
            "code": code,
            "timeout_seconds": timeout,
            "created_at": now.isoformat(),
            "ttl": ttl,
        }
        
        self.jobs_table.put_item(Item=item)
        
        # Send to SQS FIFO
        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({
                "job_id": job_id,
                "user_id": user_id,
                "code": code,
                "timeout_seconds": timeout,
            }),
            MessageGroupId=user_id,  # Preserves order per user
            MessageDeduplicationId=job_id,
        )
        
        return {"job_id": job_id, "status": "pending"}
    
    def get_job(self, job_id: str, user_id: str) -> dict | None:
        """Get job by ID, validates ownership."""
        response = self.jobs_table.get_item(Key={"job_id": job_id})
        job = response.get("Item")
        
        if not job or job["user_id"] != user_id:
            return None
        
        return job
    
    def update_status(self, job_id: str, status: str, **kwargs) -> None:
        """Update job status and optional fields."""
        update_expr = "SET #status = :status"
        names = {"#status": "status"}
        values = {":status": status}
        
        if status == "running":
            update_expr += ", started_at = :started_at"
            values[":started_at"] = datetime.utcnow().isoformat()
        
        if status in ("completed", "failed"):
            update_expr += ", completed_at = :completed_at"
            values[":completed_at"] = datetime.utcnow().isoformat()
        
        if "result" in kwargs:
            update_expr += ", #result = :result"
            names["#result"] = "result"
            values[":result"] = kwargs["result"]
        
        self.jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
```

#### Connection Service

```python
# api/services/connection_service.py

from datetime import datetime, timedelta

import boto3

from backend.common.config import settings


class ConnectionService:
    """Manages WebSocket connections in DynamoDB."""
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(settings.CONNECTIONS_TABLE_NAME)
    
    def add_connection(self, connection_id: str, user_id: str) -> None:
        """Store new WebSocket connection."""
        ttl = int((datetime.utcnow() + timedelta(hours=2)).timestamp())
        
        self.table.put_item(Item={
            "connection_id": connection_id,
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat(),
            "subscribed_jobs": set(),  # Empty string set
            "ttl": ttl,
        })
    
    def remove_connection(self, connection_id: str) -> None:
        """Remove connection on disconnect."""
        self.table.delete_item(Key={"connection_id": connection_id})
    
    def subscribe_to_job(self, connection_id: str, job_id: str) -> None:
        """Add job to connection's subscription list."""
        self.table.update_item(
            Key={"connection_id": connection_id},
            UpdateExpression="ADD subscribed_jobs :job_id",
            ExpressionAttributeValues={":job_id": {job_id}},
        )
    
    def get_connections_for_user(self, user_id: str) -> list[str]:
        """Get all connection IDs for a user."""
        response = self.table.query(
            IndexName="user_id-index",
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
        )
        return [item["connection_id"] for item in response.get("Items", [])]
```

#### WebSocket Notifier

```python
# api/services/websocket_notifier.py

import json

import boto3
from botocore.exceptions import ClientError

from backend.common.config import settings
from backend.api.services.connection_service import ConnectionService


class WebSocketNotifier:
    """Pushes messages to connected WebSocket clients."""
    
    def __init__(self):
        self.apigw = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=settings.WEBSOCKET_ENDPOINT,
        )
        self.connections = ConnectionService()
    
    def notify_user(self, user_id: str, message: dict) -> None:
        """Send message to all of user's connections."""
        connection_ids = self.connections.get_connections_for_user(user_id)
        data = json.dumps(message).encode()
        
        for conn_id in connection_ids:
            try:
                self.apigw.post_to_connection(
                    ConnectionId=conn_id,
                    Data=data,
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "GoneException":
                    # Connection stale, clean up
                    self.connections.remove_connection(conn_id)
                # Ignore other errors, best-effort delivery
    
    def notify_job_status(self, user_id: str, job_id: str, status: str) -> None:
        """Send job status update."""
        self.notify_user(user_id, {
            "type": "job.status",
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def notify_job_result(
        self, user_id: str, job_id: str, status: str, result: dict
    ) -> None:
        """Send job completion with result."""
        self.notify_user(user_id, {
            "type": "job.result",
            "job_id": job_id,
            "status": status,
            "result": result,
        })
```

### Lambda Handlers

#### WebSocket Connect

```python
# api/handlers/ws_connect.py

import logging
from backend.api.auth.cognito import validate_jwt
from backend.api.services.connection_service import ConnectionService

logger = logging.getLogger()
connections = ConnectionService()


def handler(event, context):
    """Handle WebSocket $connect route."""
    connection_id = event["requestContext"]["connectionId"]
    
    # JWT passed as query parameter (WebSocket limitation)
    token = event.get("queryStringParameters", {}).get("token")
    
    if not token:
        logger.warning("Connection attempt without token")
        return {"statusCode": 401}
    
    try:
        claims = validate_jwt(token)
        user_id = claims["sub"]
    except Exception as e:
        logger.warning(f"Invalid token: {e}")
        return {"statusCode": 401}
    
    connections.add_connection(connection_id, user_id)
    logger.info(f"Connected: {connection_id} for user {user_id}")
    
    return {"statusCode": 200}
```

#### WebSocket Disconnect

```python
# api/handlers/ws_disconnect.py

import logging
from backend.api.services.connection_service import ConnectionService

logger = logging.getLogger()
connections = ConnectionService()


def handler(event, context):
    """Handle WebSocket $disconnect route."""
    connection_id = event["requestContext"]["connectionId"]
    connections.remove_connection(connection_id)
    logger.info(f"Disconnected: {connection_id}")
    return {"statusCode": 200}
```

#### WebSocket Default (Message Handler)

```python
# api/handlers/ws_default.py

import json
import logging

from backend.api.services.connection_service import ConnectionService
from backend.api.services.job_service import JobService

logger = logging.getLogger()
connections = ConnectionService()
jobs = JobService()


def handler(event, context):
    """Handle WebSocket messages."""
    connection_id = event["requestContext"]["connectionId"]
    
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {"statusCode": 400}
    
    action = body.get("action")
    
    if action == "subscribe":
        job_id = body.get("job_id")
        if job_id:
            connections.subscribe_to_job(connection_id, job_id)
            logger.info(f"Subscribed {connection_id} to job {job_id}")
    
    elif action == "ping":
        # Heartbeat - could send pong back
        pass
    
    return {"statusCode": 200}
```

#### Worker Lambda

```python
# api/handlers/worker.py

import json
import logging

from backend.executor.runner import PythonRunner
from backend.api.services.job_service import JobService
from backend.api.services.websocket_notifier import WebSocketNotifier

logger = logging.getLogger()
jobs = JobService()
notifier = WebSocketNotifier()
runner = PythonRunner()


def handler(event, context):
    """Process SQS execution messages."""
    for record in event["Records"]:
        try:
            process_message(json.loads(record["body"]))
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            raise  # Let SQS retry
    
    return {"statusCode": 200}


def process_message(message: dict) -> None:
    """Execute code and push results."""
    job_id = message["job_id"]
    user_id = message["user_id"]
    code = message["code"]
    timeout = message.get("timeout_seconds", 30)
    
    # Update to running
    jobs.update_status(job_id, "running")
    notifier.notify_job_status(user_id, job_id, "running")
    
    # Execute
    result = runner.execute(code, timeout=timeout)
    
    # Determine final status
    status = "completed" if result["success"] else "failed"
    
    # Update job with result
    jobs.update_status(job_id, status, result=result)
    notifier.notify_job_result(user_id, job_id, status, result)
```

### API Router Updates

```python
# api/routers/execution.py

from fastapi import APIRouter, Depends, HTTPException

from backend.api.auth.dependencies import get_current_user
from backend.api.auth.models import User
from backend.api.schemas.jobs import (
    ExecutionRequest,
    JobSubmittedResponse,
    JobStatusResponse,
)
from backend.api.services.job_service import JobService

router = APIRouter(prefix="/execute", tags=["execution"])


def get_job_service() -> JobService:
    return JobService()


@router.post("", response_model=JobSubmittedResponse)
async def submit_execution(
    request: ExecutionRequest,
    user: User = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    """Submit code for async execution."""
    result = jobs.create_job(
        user_id=user.sub,
        code=request.code,
        timeout=request.timeout_seconds,
    )
    return JobSubmittedResponse(**result)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    jobs: JobService = Depends(get_job_service),
):
    """Get job status (polling fallback)."""
    job = jobs.get_job(job_id, user.sub)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)
```

### Frontend Hooks

#### useWebSocket

```typescript
// hooks/useWebSocket.ts

import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '../store/authStore';

interface WebSocketMessage {
  type: 'job.status' | 'job.result' | 'pong' | 'error';
  job_id?: string;
  status?: string;
  result?: ExecutionResult;
  message?: string;
}

export function useWebSocket(onMessage: (msg: WebSocketMessage) => void) {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const { accessToken } = useAuthStore();
  
  const connect = useCallback(() => {
    if (!accessToken) return;
    
    const wsUrl = `${import.meta.env.VITE_WS_ENDPOINT}?token=${accessToken}`;
    ws.current = new WebSocket(wsUrl);
    
    ws.current.onopen = () => {
      setIsConnected(true);
    };
    
    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      onMessage(message);
    };
    
    ws.current.onclose = () => {
      setIsConnected(false);
      // Reconnect after delay
      setTimeout(connect, 3000);
    };
    
    ws.current.onerror = () => {
      ws.current?.close();
    };
  }, [accessToken, onMessage]);
  
  const subscribe = useCallback((jobId: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: 'subscribe', job_id: jobId }));
    }
  }, []);
  
  useEffect(() => {
    connect();
    return () => ws.current?.close();
  }, [connect]);
  
  return { isConnected, subscribe };
}
```

#### useExecution

```typescript
// hooks/useExecution.ts

import { useState, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';
import { apiClient } from '../api/client';

interface Job {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: ExecutionResult;
}

export function useExecution() {
  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const handleMessage = useCallback((msg: WebSocketMessage) => {
    if (msg.type === 'job.status' && msg.job_id === currentJob?.id) {
      setCurrentJob(prev => prev ? { ...prev, status: msg.status! } : null);
    }
    
    if (msg.type === 'job.result' && msg.job_id === currentJob?.id) {
      setCurrentJob(prev => prev ? {
        ...prev,
        status: msg.status!,
        result: msg.result,
      } : null);
    }
  }, [currentJob?.id]);
  
  const { isConnected, subscribe } = useWebSocket(handleMessage);
  
  const execute = useCallback(async (code: string) => {
    setIsSubmitting(true);
    
    try {
      const response = await apiClient.post('/execute', { code });
      const { job_id, status } = response.data;
      
      setCurrentJob({ id: job_id, status });
      subscribe(job_id);
      
      // Fallback: poll if WebSocket not connected
      if (!isConnected) {
        pollForResult(job_id);
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [subscribe, isConnected]);
  
  const pollForResult = async (jobId: string) => {
    const poll = async () => {
      const response = await apiClient.get(`/execute/jobs/${jobId}`);
      const job = response.data;
      
      setCurrentJob({
        id: job.job_id,
        status: job.status,
        result: job.result,
      });
      
      if (job.status === 'pending' || job.status === 'running') {
        setTimeout(poll, 1000);
      }
    };
    poll();
  };
  
  return { currentJob, execute, isSubmitting };
}
```

## Testing

### Unit Tests

```python
# tests/unit/test_job_service.py

import pytest
from unittest.mock import MagicMock, patch

from backend.api.services.job_service import JobService


@pytest.fixture
def job_service():
    with patch("boto3.resource"), patch("boto3.client"):
        service = JobService()
        service.jobs_table = MagicMock()
        service.sqs = MagicMock()
        return service


def test_create_job_stores_in_dynamodb(job_service):
    result = job_service.create_job("user-123", "print('hi')", 30)
    
    assert "job_id" in result
    assert result["status"] == "pending"
    job_service.jobs_table.put_item.assert_called_once()


def test_create_job_sends_to_sqs(job_service):
    result = job_service.create_job("user-123", "print('hi')", 30)
    
    job_service.sqs.send_message.assert_called_once()
    call_kwargs = job_service.sqs.send_message.call_args.kwargs
    assert call_kwargs["MessageGroupId"] == "user-123"
```

### Integration Tests

```python
# tests/integration/test_async_execution.py

import pytest
import time

from backend.api.services.job_service import JobService


@pytest.mark.integration
def test_full_execution_flow(dynamodb_table, sqs_queue):
    """Test complete job lifecycle."""
    service = JobService()
    
    # Create job
    result = service.create_job("test-user", "print('hello')", 5)
    job_id = result["job_id"]
    
    # Verify pending
    job = service.get_job(job_id, "test-user")
    assert job["status"] == "pending"
    
    # Simulate worker processing
    service.update_status(job_id, "running")
    service.update_status(job_id, "completed", result={
        "success": True,
        "stdout": "hello\n",
        "stderr": "",
        "execution_time_ms": 50,
    })
    
    # Verify completed
    job = service.get_job(job_id, "test-user")
    assert job["status"] == "completed"
    assert job["result"]["stdout"] == "hello\n"
```

## Known Issues & Mitigations

### 1. Lambda Async Pattern
**Issue:** WebSocket handlers use `async def` but Lambda needs sync functions.
**Fix:** Use synchronous boto3 calls (not aioboto3). Lambda handlers are already sync.

### 2. FIFO Queue Throughput
**Issue:** FIFO queues limited to 300 msg/sec per MessageGroupId.
**Mitigation:** Using user_id as MessageGroupId distributes load. Monitor and consider partitioning if needed.

### 3. WebSocket Connection Limits
**Issue:** API Gateway WebSocket has 500 connections per account by default.
**Mitigation:** Request limit increase for production. Implement connection pooling if needed.

### 4. Stale Jobs
**Issue:** Jobs can get stuck in "running" if worker crashes.
**Mitigation:** DynamoDB TTL cleans up after 24h. Future: Add a cleanup Lambda on schedule.

## Configuration

### Environment Variables

```bash
# Backend
JOBS_TABLE_NAME=code-remote-dev-jobs
CONNECTIONS_TABLE_NAME=code-remote-dev-connections
EXECUTION_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/xxx/code-remote-dev-execution.fifo
WEBSOCKET_ENDPOINT=https://xxx.execute-api.us-east-1.amazonaws.com/dev

# Frontend
VITE_API_ENDPOINT=https://xxx.execute-api.us-east-1.amazonaws.com
VITE_WS_ENDPOINT=wss://xxx.execute-api.us-east-1.amazonaws.com/dev
```

## Rollout Plan

1. **Infrastructure First**
   - Deploy DynamoDB tables
   - Deploy SQS queue
   - Deploy WebSocket API Gateway

2. **Backend Services**
   - Add job_service.py, connection_service.py
   - Add WebSocket handlers
   - Add worker Lambda
   - Update /execute endpoint

3. **Frontend**
   - Add useWebSocket hook
   - Update useExecution to async pattern
   - Add job status UI

4. **Testing**
   - Unit tests for all services
   - Integration test with localstack
   - Manual E2E testing

5. **Deployment**
   - Deploy to dev, verify
   - Monitor CloudWatch logs
   - Deploy to prod
