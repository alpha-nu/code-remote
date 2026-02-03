# Data Model

## Overview

Code Remote uses DynamoDB for job tracking and WebSocket connection management. Future phases will add Aurora PostgreSQL for persistent code snippets with vector search.

## DynamoDB Tables

### Jobs Table

Stores execution job state and results.

```
Table: code-remote-{env}-jobs
────────────────────────────────────────────────────────────

Primary Key:
  - Partition Key: job_id (String, UUID)

GSI: user_id-created_at-index
  - Partition Key: user_id (String)
  - Sort Key: created_at (String, ISO timestamp)
  - Projection: ALL

TTL: ttl (Number, Unix timestamp)
  - Auto-delete after 24 hours

Attributes:
┌─────────────────────┬───────────┬──────────────────────────────┐
│ Attribute           │ Type      │ Description                  │
├─────────────────────┼───────────┼──────────────────────────────┤
│ job_id              │ String    │ UUID, primary key            │
│ user_id             │ String    │ Cognito sub                  │
│ status              │ String    │ pending|running|completed|failed │
│ code                │ String    │ Submitted code               │
│ timeout_seconds     │ Number    │ Max execution time           │
│ created_at          │ String    │ ISO timestamp                │
│ started_at          │ String    │ When execution started       │
│ completed_at        │ String    │ When execution finished      │
│ result              │ Map       │ Execution result (see below) │
│ ttl                 │ Number    │ Unix timestamp for deletion  │
└─────────────────────┴───────────┴──────────────────────────────┘

Result Map Structure:
{
  "success": Boolean,
  "stdout": String,
  "stderr": String,
  "error": String | null,
  "error_type": String | null,
  "execution_time_ms": Number,
  "timed_out": Boolean
}
```

### Connections Table

Tracks active WebSocket connections for push notifications.

```
Table: code-remote-{env}-connections
────────────────────────────────────────────────────────────

Primary Key:
  - Partition Key: connection_id (String, API Gateway ID)

GSI: user_id-index
  - Partition Key: user_id (String)
  - Projection: ALL

TTL: ttl (Number, Unix timestamp)
  - Auto-delete after 2 hours

Attributes:
┌─────────────────────┬───────────┬──────────────────────────────┐
│ Attribute           │ Type      │ Description                  │
├─────────────────────┼───────────┼──────────────────────────────┤
│ connection_id       │ String    │ API Gateway connection ID    │
│ user_id             │ String    │ Cognito sub                  │
│ connected_at        │ String    │ ISO timestamp                │
│ subscribed_jobs     │ StringSet │ Job IDs being watched        │
│ ttl                 │ Number    │ Unix timestamp for cleanup   │
└─────────────────────┴───────────┴──────────────────────────────┘
```

## Access Patterns

### Jobs Table

| Pattern | Query | Index |
|---------|-------|-------|
| Get job by ID | `job_id = X` | Primary key |
| List user's recent jobs | `user_id = X, created_at DESC` | GSI |
| Update job status | `job_id = X` (update) | Primary key |

### Connections Table

| Pattern | Query | Index |
|---------|-------|-------|
| Get connection | `connection_id = X` | Primary key |
| Find user's connections | `user_id = X` | GSI |
| Add job subscription | `connection_id = X` (update SET) | Primary key |
| Remove connection | `connection_id = X` (delete) | Primary key |

## Pydantic Schemas

```python
# api/schemas/jobs.py

from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class ExecutionRequest(BaseModel):
    """Request to execute code."""
    code: str
    timeout_seconds: int = 30


class JobResult(BaseModel):
    """Execution result."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    error_type: str | None = None
    execution_time_ms: float | None = None
    timed_out: bool = False


class JobSubmittedResponse(BaseModel):
    """Response when job is submitted."""
    job_id: str
    status: Literal["pending"] = "pending"


class JobStatusResponse(BaseModel):
    """Full job status."""
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    result: JobResult | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobSummary(BaseModel):
    """Abbreviated job info for lists."""
    job_id: str
    status: str
    created_at: datetime
    execution_time_ms: float | None = None
```

## WebSocket Message Types

### Client → Server

```typescript
// Subscribe to job updates
{ "action": "subscribe", "job_id": "uuid" }

// Unsubscribe
{ "action": "unsubscribe", "job_id": "uuid" }

// Heartbeat
{ "action": "ping" }
```

### Server → Client

```typescript
// Job status changed
{
  "type": "job.status",
  "job_id": "uuid",
  "status": "running" | "completed" | "failed",
  "timestamp": "ISO-8601"
}

// Job completed with result
{
  "type": "job.result",
  "job_id": "uuid",
  "status": "completed" | "failed",
  "result": {
    "success": boolean,
    "stdout": string,
    "stderr": string,
    "error": string | null,
    "execution_time_ms": number,
    "timed_out": boolean
  }
}

// Heartbeat response
{ "type": "pong" }

// Error
{
  "type": "error",
  "message": string,
  "code": "JOB_NOT_FOUND" | "INVALID_REQUEST" | "UNAUTHORIZED"
}
```

## SQS Message Format

```json
{
  "job_id": "uuid",
  "user_id": "cognito-sub",
  "code": "print('hello')",
  "timeout_seconds": 30
}
```

FIFO Queue attributes:
- `MessageGroupId`: user_id (preserves order per user)
- `MessageDeduplicationId`: job_id (prevents duplicates)

## Future: Aurora PostgreSQL Schema (Phase 9)

For code snippets with semantic search:

```sql
-- Users (synced from Cognito)
CREATE TABLE users (
    id UUID PRIMARY KEY,
    cognito_sub VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Snippets
CREATE TABLE snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    language VARCHAR(50) DEFAULT 'python',
    
    -- Analysis results
    time_complexity VARCHAR(50),
    space_complexity VARCHAR(50),
    explanation TEXT,
    analyzed_at TIMESTAMPTZ,
    
    -- Metadata
    is_starred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Vector for semantic search (Gemini: 768 dims)
    embedding vector(768)
);

-- Indexes
CREATE INDEX idx_snippets_user_id ON snippets(user_id);
CREATE INDEX idx_snippets_starred ON snippets(user_id, is_starred) 
    WHERE is_starred = TRUE;
CREATE INDEX idx_snippets_embedding ON snippets 
    USING ivfflat (embedding vector_cosine_ops);
```
