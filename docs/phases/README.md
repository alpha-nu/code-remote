# Development Phases

This directory contains detailed documentation for each development phase.

## Phase Overview

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1-7 | Core Foundation | ✅ Complete | Authentication, execution, analysis |
| 8 | CI/CD | ✅ Complete | GitHub Actions, automated deployment |
| 9 | Persistence | � In Progress | PostgreSQL + Neo4j hybrid |
| 10 | Real-Time Async | ✅ Complete | WebSocket, SQS, async execution |
| 11 | Kubernetes | 🔲 Planned | Self-hosted execution cluster |

## Phase Documents

### Completed Phases
- See commit history and architecture docs for details on phases 1-8
- Phase 10 implementation details below

### In Progress
- **Phase 9: Persistence** - Hybrid architecture with PostgreSQL (CRUD) + Neo4j (Vector Search)
  - Phase 9.1: PostgreSQL Foundation (current)
  - Phase 9.2: Neo4j + CDC sync (upcoming)
  - Phase 9.3: Vector search (upcoming)

### Upcoming
- Phase 11: Kubernetes execution

## Technology Evolution

```
Phase 1-7: Lambda (sync) → API Gateway → React
     ↓
Phase 8:   + GitHub Actions CI/CD
     ↓
Phase 10:  + WebSocket API Gateway
           + SQS FIFO Queues  
           + Worker Lambda
           + Real-time result push
     ↓
Phase 9:   + Aurora PostgreSQL (CRUD, source of truth)
           + Neo4j AuraDB (Vector search, patterns)
           + EventBridge CDC (PG → Neo4j sync)
     ↓
Phase 11:  + EKS Cluster
           + gVisor (runsc)
           + Network isolation
```

---

## Phase 10: Real-Time Async Execution

### Implementation Summary

Phase 10 adds real-time async execution with WebSocket updates. The implementation uses a **stateless design** - no DynamoDB for job tracking. Instead, the `connection_id` is passed directly in the request, and results are pushed immediately to the client.

### Architecture

```
┌─────────────┐  POST /execute/async   ┌─────────────────────┐
│   Frontend  │─────────────────────▶  │    API Lambda       │
│   (React)   │  {code, connection_id} │  Returns {job_id}   │
└──────┬──────┘                        └──────────┬──────────┘
       │                                          │
       │ WebSocket                       SQS FIFO │
       │                                          ▼
┌──────┴──────────────┐               ┌─────────────────────┐
│  WebSocket API GW   │◀──────────────│   Worker Lambda     │
│  (returns conn_id)  │   Push via    │  - Executes code    │
└─────────────────────┘   Management  │  - Pushes result    │
                          API         └─────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State Storage | None (stateless) | Simpler, no DynamoDB cost, direct push |
| Connection ID | Passed in request | Client gets ID from WebSocket ping |
| Fallback | Auto sync execution | If WebSocket unavailable, use HTTP |
| Queue | SQS FIFO | Ordered, at-least-once delivery |

### Data Flow

1. **Frontend connects** to WebSocket, sends `ping`, receives `connection_id`
2. **User runs code** → `POST /execute/async {code, connection_id}`
3. **API queues job** to SQS FIFO, returns `{job_id, status: "queued"}`
4. **Worker receives** SQS message, executes code in sandbox
5. **Worker pushes** result via WebSocket Management API to `connection_id`
6. **Frontend receives** result instantly via WebSocket

### New Components

#### Infrastructure (Pulumi)
- `messaging.py` - SQS FIFO queue + DLQ
- `websocket.py` - WebSocket API Gateway with inline Lambda handlers
- `worker.py` - Worker Lambda with SQS event source

#### Backend
- `api/handlers/worker.py` - SQS consumer, executes code, pushes via WebSocket
- `api/routers/execution.py` - New `POST /execute/async` endpoint
- `api/schemas/execution.py` - `AsyncExecutionRequest`, `JobSubmittedResponse`

#### Frontend
- `hooks/useWebSocket.ts` - Connection management with auto-reconnect
- `hooks/useExecution.ts` - Async execution with sync fallback
- `Toolbar.tsx` - Updated with connection status indicator

### Configuration

```bash
# Backend environment variables
EXECUTION_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/xxx/queue.fifo
WEBSOCKET_ENDPOINT=wss://xxx.execute-api.us-east-1.amazonaws.com/prod

# Frontend environment variables  
VITE_WEBSOCKET_URL=wss://xxx.execute-api.us-east-1.amazonaws.com/prod
```

### Limitations & Future Work

1. **No job history** - Results only delivered via WebSocket (no persistence)
2. **Connection required** - Must have WebSocket connection before submitting
3. **No retry on disconnect** - If client disconnects, result is lost

These limitations are acceptable for the current use case. Phase 9 (Persistence) can add job history if needed.
