# Remote Code Execution Engine - Architecture Plan

## Mission

Build a secure, scalable, cloud-agnostic remote code execution platform that allows users to write Python code in a web interface, execute it safely, and receive results along with AI-powered complexity analysis.

## Quick Links

> **Detailed Documentation:**
> - [Architecture Overview](architecture/overview.md) - System design and components
> - [Security Model](architecture/security.md) - Sandbox, import restrictions, resource limits
> - [Data Model](architecture/data-model.md) - DynamoDB schemas, API contracts
> - [Infrastructure](architecture/infrastructure.md) - Pulumi components, AWS resources
> - [Phase Documentation](phases/README.md) - Implementation phases

---

## Architecture Decision: Hybrid (Option 3)

**Managed Services + Self-hosted Kubernetes Execution**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MANAGED SERVICES + SELF-HOSTED EXECUTION                  │
│                                                                              │
│  API Layer: API Gateway (HTTP + WebSocket) + Lambda                         │
│  Execution: Self-hosted Kubernetes cluster with gVisor (Phase 11)           │
│  Data: Aurora PostgreSQL (CRUD) + Neo4j AuraDB (search) - Phase 9           │
│  Queue: SQS FIFO (Phase 10) ✅                                               │
│  Real-time: WebSocket API Gateway (Phase 10) ✅                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Why Hybrid:**
- Managed services for API/auth/queue reduce ops burden
- Self-hosted K8s for execution gives full security control
- gVisor provides kernel-level isolation
- Network policies block all egress from execution pods

---

## Technology Stack

| Component | Technology | Phase |
|-----------|------------|-------|
| Frontend | React 18 + Monaco Editor + AWS Amplify | 4 |
| API Layer | AWS API Gateway (HTTP) + Lambda | 3, 7 |
| Backend | FastAPI + Mangum | 1-3 |
| Execution | Lambda (current), K8s + gVisor (Phase 11) | 2, 11 |
| Queue | AWS SQS FIFO | 10 |
| Database | Aurora PostgreSQL (CRUD), Neo4j AuraDB (search) | 9 |
| Auth | AWS Cognito | 6 |
| LLM | Google Gemini API | 5 |
| Real-time | API Gateway WebSocket | 10 |
| IaC | Pulumi (Python) | 7 |
| CI/CD | GitHub Actions | 8 |

---

## Phase Progress

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Backend Foundation | ✅ Complete | FastAPI project structure |
| 2 | Sandboxed Executor | ✅ Complete | Python runner with security |
| 3 | API Integration | ✅ Complete | Execution and analysis endpoints |
| 4 | Frontend | ✅ Complete | React + Monaco Editor |
| 5 | LLM Analysis | ✅ Complete | Gemini complexity analysis |
| 6 | Authentication | ✅ Complete | Cognito integration |
| 7 | Infrastructure | ✅ Complete | Pulumi AWS deployment |
| 8 | CI/CD | ✅ Complete | GitHub Actions pipeline |
| 9 | Persistence | � In Progress | PostgreSQL + Neo4j hybrid |
| 10 | Real-Time Async | ✅ Complete | WebSocket, SQS FIFO |
| 11 | Kubernetes | 📋 Planned | EKS + gVisor execution |

---

## Current Focus: Phase 9

**Persistence with Hybrid PostgreSQL + Neo4j**

Save and search code snippets with a hybrid relational + graph architecture.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Phase 9: Hybrid Persistence                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────┐                                       │
│  │        Lambda (FastAPI)         │                                       │
│  │  - CRUD → PostgreSQL            │                                       │
│  │  - Search → Neo4j               │                                       │
│  └───────────────┬─────────────────┘                                       │
│                  │                                                          │
│         ┌────────┴────────┐                                                │
│         ▼                 ▼                                                │
│  ┌──────────────┐   ┌──────────────┐                                      │
│  │   Aurora     │   │  Neo4j       │                                      │
│  │  PostgreSQL  │──▶│  AuraDB      │  (CDC via EventBridge)               │
│  │              │   │              │                                      │
│  │  • Users     │   │  • Embeddings│                                      │
│  │  • Snippets  │   │  • SIMILAR_TO│                                      │
│  └──────────────┘   │  • Patterns  │                                      │
│                     └──────────────┘                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Phase 9.1 (Current):** PostgreSQL foundation - Users + Snippets CRUD (backend only)
**Phase 9.2:** Neo4j + EventBridge CDC sync
**Phase 9.3:** Vector search with Gemini embeddings

**See:** [Phase Documentation](phases/README.md)

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Hybrid | Balance of managed services + execution control |
| Build Approach | Incremental | Build one component at a time, verify each |
| Frontend | React + Monaco | Industry standard, VS Code's editor |
| Authentication | AWS Cognito | Native AWS integration, managed |
| LLM Provider | Google Gemini | API key auth only, no GCP setup |
| Execution Timeout | 30 seconds | Complex computations while limiting abuse |
| Initial Cloud | AWS | Mature ecosystem, Cognito integration |
| Real-time | WebSocket | Native browser support, bidirectional |

---

## Security Summary

**Execution Sandbox (4 Layers):**
1. **Import Whitelist** - Only safe modules (math, json, collections, etc.)
2. **Restricted Builtins** - No eval, exec, open, __import__, compile
3. **AST Validation** - Block dangerous patterns at parse time
4. **Resource Limits** - 256MB memory, 30s timeout, no network

**See:** [Security Documentation](architecture/security.md)

---

## Project Structure

```
code-remote/
├── .github/
│   └── workflows/         # GitHub Actions CI/CD
├── frontend/              # React + Monaco Editor
├── backend/
│   ├── api/               # FastAPI routers, schemas, services
│   ├── executor/          # Sandboxed Python runner
│   ├── analyzer/          # Gemini LLM integration
│   └── common/            # Shared config, utilities
├── infra/pulumi/          # Infrastructure as Code
├── docs/                  # Architecture documentation
│   ├── architecture/      # System design docs
│   └── phases/            # Phase implementation docs
└── kubernetes/            # K8s manifests (Phase 11)
```

---

## Local Development

```bash
# Backend
cd backend && uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Full stack with Docker
docker-compose up -d
```

---

## Deployment

```bash
# Deploy infrastructure
cd infra/pulumi && pulumi up --stack dev

# Build and push API container
docker buildx build -t $ECR_URL:latest -f backend/Dockerfile.lambda backend/
docker push $ECR_URL:latest

# Update Lambda
aws lambda update-function-code --function-name $FUNC --image-uri $ECR_URL:latest
```

**See:** [Deployment Guide](DEPLOYMENT.md) | [Release Workflow](RELEASE_WORKFLOW.md)

---

## Status: APPROVED ✅

Ready for Phase 10 implementation.
