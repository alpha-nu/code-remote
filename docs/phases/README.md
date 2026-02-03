# Development Phases

This directory contains detailed documentation for each development phase.

## Phase Overview

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1-7 | Core Foundation | ✅ Complete | Authentication, execution, analysis |
| 8 | CI/CD | ✅ Complete | GitHub Actions, automated deployment |
| 9 | Persistence | 🔲 Planned | Code snippets, Aurora PostgreSQL |
| **10** | **Real-Time Async** | **🔄 In Progress** | **WebSocket, SQS, async execution** |
| 11 | Kubernetes | 🔲 Planned | Self-hosted execution cluster |

## Phase Documents

### Completed Phases
- See commit history and [ARCHITECTURE_PLAN.md](../ARCHITECTURE_PLAN.md) for details on phases 1-8

### Active & Upcoming
- [Phase 10: Real-Time Async Execution](phase-10-realtime.md) - Current focus
- Phase 9: Persistence (TBD) - Code snippets with semantic search

## Technology Evolution

```
Phase 1-7: Lambda (sync) → API Gateway → React
     ↓
Phase 8:   + GitHub Actions CI/CD
     ↓
Phase 10:  + WebSocket API Gateway
           + SQS FIFO Queues  
           + DynamoDB (Jobs, Connections)
           + Worker Lambda
     ↓
Phase 9:   + Aurora PostgreSQL (snippets)
           + pgvector (semantic search)
     ↓
Phase 11:  + EKS Cluster
           + gVisor (runsc)
           + Network isolation
```

## Migration Notes

### Phase 10 Changes Existing Code

1. **API Layer**
   - `/execute` becomes async (returns job_id immediately)
   - New `/jobs/{id}` endpoint for polling fallback
   - New WebSocket API for real-time updates

2. **Frontend**
   - ExecutionService becomes async
   - New WebSocket hook for live updates
   - Job history UI component

3. **Infrastructure**
   - New DynamoDB tables (Jobs, Connections)
   - New SQS FIFO queue
   - New Worker Lambda
   - New WebSocket API Gateway

### Breaking Changes
- `/execute` response format changes (returns `{job_id, status}` not `{result}`)
- Frontend must handle async flow
- Polling or WebSocket required for results
