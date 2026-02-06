# Architecture Overview

## Mission

Build a secure, scalable, cloud-agnostic remote code execution platform that allows users to write Python code in a web interface, execute it safely, and receive results along with AI-powered complexity analysis.

## Architecture Choice: Hybrid

We use a **hybrid architecture** combining managed AWS services with controlled execution:

- **API Layer**: Managed (API Gateway + Lambda)
- **Execution**: Lambda-based sandboxed execution (with future K8s option)
- **Data**: Managed databases (DynamoDB, future Aurora)
- **Queue**: Managed SQS FIFO
- **Real-time**: API Gateway WebSocket

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Code Remote                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────┐   │
│  │  Frontend   │    │   API Gateway    │    │   Lambda (FastAPI)      │   │
│  │  React +    │───▶│   HTTP + WS      │───▶│   - /execute            │   │
│  │  Monaco     │    │                  │    │   - /analyze            │   │
│  └─────────────┘    └──────────────────┘    │   - /jobs               │   │
│        │                    │               └───────────┬─────────────┘   │
│        │                    │                           │                 │
│        │ WebSocket          │                           ▼                 │
│        │                    │               ┌─────────────────────────┐   │
│        │                    │               │      SQS FIFO Queue     │   │
│        │                    │               └───────────┬─────────────┘   │
│        │                    │                           │                 │
│        │                    │                           ▼                 │
│        │                    │               ┌─────────────────────────┐   │
│        │◀───────────────────┼───────────────│    Worker Lambda        │   │
│        │   Push results     │               │    - Execute code       │   │
│        │                    │               │    - Push via WebSocket │   │
│                             │               └───────────┬─────────────┘   │
│                             │                           │                 │
│                             │                           ▼                 │
│  ┌──────────────────────────┴───────────────────────────────────────────┐ │
│  │                         Data Layer                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │  Cognito    │  │  DynamoDB   │  │   Gemini    │  │  CloudWatch │  │ │
│  │  │  Auth       │  │  Jobs       │  │   LLM API   │  │  Logs       │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Hybrid | Balance of managed services + execution control |
| Frontend | React + Monaco Editor | Industry standard, VS Code's editor |
| Authentication | AWS Cognito | Native AWS integration, managed service |
| LLM Provider | Google Gemini | API key auth only, no GCP setup required |
| Execution Timeout | 30 seconds | Allows complex computations while limiting abuse |
| Initial Cloud | AWS | Mature ecosystem, Cognito integration |
| Real-time | WebSocket | Instant feedback, better than polling |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Monaco Editor + AWS Amplify |
| API Layer | AWS API Gateway (HTTP + WebSocket) |
| Backend | FastAPI + Mangum (Lambda adapter) |
| Execution | Lambda-based sandbox with restricted imports |
| Queue | AWS SQS FIFO |
| Database | DynamoDB (jobs), Aurora PostgreSQL (future) |
| Auth | AWS Cognito |
| LLM | Google Gemini API |
| IaC | Pulumi (Python) |
| CI/CD | GitHub Actions |

## Project Structure

```
code-remote/
├── frontend/           # React + Monaco Editor
│   ├── src/
│   │   ├── components/ # UI components
│   │   ├── hooks/      # Custom React hooks
│   │   ├── store/      # Zustand state management
│   │   └── api/        # API client
│   └── package.json
│
├── backend/
│   ├── api/            # FastAPI application
│   │   ├── routers/    # Route handlers
│   │   ├── schemas/    # Pydantic models
│   │   ├── services/   # Business logic
│   │   ├── auth/       # Cognito integration
│   │   └── handlers/   # Lambda handlers (WebSocket)
│   ├── executor/       # Sandboxed Python runner
│   ├── analyzer/       # Gemini LLM integration
│   ├── common/         # Shared utilities
│   └── tests/
│
├── infra/pulumi/       # Infrastructure as Code
│   ├── components/     # Reusable Pulumi components
│   └── __main__.py     # Entry point
│
└── docs/               # Documentation
```

## Component Responsibilities

### Frontend
- Monaco Editor with Python syntax highlighting
- WebSocket connection for real-time updates
- Auth flow via Cognito/Amplify
- State management with Zustand + React Query

### API Lambda (FastAPI)
- Request validation and auth
- Job submission to SQS
- Job status queries from DynamoDB
- Complexity analysis via Gemini

### Worker Lambda
- Consumes jobs from SQS
- Executes code in sandbox
- Updates job status in DynamoDB
- Pushes results via WebSocket

### WebSocket Handlers
- Manage persistent connections
- Route job updates to clients
- Handle subscribe/unsubscribe

## Data Flow

### Code Execution Flow
```
1. User writes code in Monaco Editor
2. Frontend POSTs to /execute with JWT
3. API Lambda validates, creates job in DynamoDB, sends to SQS
4. API returns job_id immediately (~100ms)
5. Frontend subscribes to WebSocket for job_id
6. Worker Lambda picks up job from SQS
7. Worker updates status to "running", pushes via WebSocket
8. Worker executes code in sandbox
9. Worker updates result, pushes final status via WebSocket
10. Frontend displays result in real-time
```

### Analysis Flow
```
1. User clicks "Analyze"
2. Frontend POSTs to /analyze with code
3. API Lambda calls Gemini API with complexity prompt
4. Gemini returns time/space complexity analysis
5. API returns analysis result
6. Frontend displays complexity info
```
