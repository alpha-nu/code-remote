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


# Remote Code Execution Engine - Architecture Plan

## Mission
Build a secure, scalable, cloud-agnostic remote code execution platform that allows users to write Python code in a web interface, execute it safely, and receive results along with AI-powered complexity analysis.

---

## Architecture Options

### Option 1: Kubernetes-Native Architecture (Recommended)

**Best for:** Production-grade, cloud-agnostic, full control over execution environment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   FRONTEND                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  React/Vue + Monaco Editor (VS Code's editor)                       │    │
│  │  - Code editing with Python syntax highlighting                      │    │
│  │  - Basic intellisense via Pyright WASM                              │    │
│  │  - WebSocket for real-time execution output                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY LAYER                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Kong / Traefik / AWS API Gateway (abstracted via Pulumi)           │    │
│  │  - Rate limiting, Authentication (JWT/OAuth2)                        │    │
│  │  - Request validation, CORS                                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────────┐
│   EXECUTION SERVICE   │ │  ANALYSIS SERVICE │ │     SESSION SERVICE       │
│   (FastAPI)           │ │  (FastAPI)        │ │     (FastAPI)             │
│                       │ │                   │ │                           │
│ - Receives code       │ │ - LLM integration │ │ - User session mgmt       │
│ - Validates input     │ │ - Complexity calc │ │ - Execution history       │
│ - Queues execution    │ │ - Code review     │ │ - Rate limit tracking     │
└───────────────────────┘ └───────────────────┘ └───────────────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MESSAGE QUEUE                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Redis Streams / RabbitMQ / AWS SQS (abstracted)                    │    │
│  │  - Execution job queue                                               │    │
│  │  - Result notification                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION ORCHESTRATOR                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Kubernetes Job Controller (Custom Operator)                         │    │
│  │  - Spawns ephemeral pods for each execution                         │    │
│  │  - Resource limits (CPU, Memory, Time)                              │    │
│  │  - Network isolation (no egress by default)                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SANDBOXED EXECUTION POD                                            │    │
│  │  ┌───────────────────────────────────────────────────────────────┐  │    │
│  │  │  gVisor / Firecracker MicroVM                                 │  │    │
│  │  │  - Hardened Python runtime                                    │  │    │
│  │  │  - seccomp profiles                                           │  │    │
│  │  │  - Read-only filesystem                                       │  │    │
│  │  │  - No network access                                          │  │    │
│  │  │  - Resource cgroups                                           │  │    │
│  │  └───────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  PostgreSQL      │  │  Redis           │  │  S3 / MinIO              │   │
│  │  - Execution logs│  │  - Session cache │  │  - Code snapshots        │   │
│  │  - User data     │  │  - Rate limits   │  │  - Large outputs         │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Why Kubernetes-Native:**
- **Cloud Agnostic:** Runs on EKS, GKE, AKS, or self-hosted
- **Isolation:** Each execution in its own pod with resource limits
- **Scalability:** HPA for services, cluster autoscaler for nodes
- **Security:** Network policies, pod security policies, gVisor runtime
- **Testability:** Kind/k3s for local development, same manifests everywhere

---

### Option 2: Serverless-First Architecture

**Best for:** Cost optimization, auto-scaling, minimal ops overhead

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND                                     │
│         Static site on CDN (CloudFront/CloudFlare)                          │
│         React + Monaco Editor                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SERVERLESS API LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  AWS Lambda / Google Cloud Run / Azure Functions                    │    │
│  │  (Abstracted via Pulumi's cloud-agnostic components)                │    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │    │
│  │  │ /submit      │  │ /analyze     │  │ /status                  │   │    │
│  │  │ Lambda       │  │ Lambda       │  │ Lambda                   │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXECUTION via AWS Fargate / Cloud Run                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Ephemeral container per execution                                   │    │
│  │  - Timeout: 30 seconds max                                          │    │
│  │  - Memory: 512MB max                                                │    │
│  │  - VPC isolated, no internet                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Tradeoffs:**
- ✅ Zero infrastructure to manage
- ✅ Pay-per-execution pricing
- ❌ Cold start latency (1-3 seconds)
- ❌ Execution time limits (15 min Lambda, 60 min Cloud Run)
- ❌ Less control over sandbox security

---

### Option 3: Hybrid Architecture

**Best for:** Balance of control and simplicity

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MANAGED SERVICES + SELF-HOSTED EXECUTION                  │
│                                                                              │
│  API Layer: Managed (API Gateway + Lambda for routing)                      │
│  Execution: Self-hosted Kubernetes cluster with gVisor                      │
│  Data: Managed databases (RDS, ElastiCache)                                 │
│  Queue: Managed (SQS/SNS)                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Backend Component Design

### 1. API Service (FastAPI)

```python
# Structure
backend/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── routers/
│   │   ├── execution.py     # POST /execute
│   │   ├── analysis.py      # POST /analyze
│   │   └── health.py        # GET /health
│   ├── schemas/
│   │   ├── execution.py     # Pydantic models
│   │   └── analysis.py
│   ├── services/
│   │   ├── executor.py      # Business logic
│   │   ├── analyzer.py      # LLM integration
│   │   └── queue.py         # Message queue client
│   └── middleware/
│       ├── auth.py          # JWT validation
│       └── rate_limit.py    # Rate limiting
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── Dockerfile
```

**Why FastAPI:**
- Async-first for high concurrency
- Built-in OpenAPI documentation
- Pydantic for validation
- Easy to test with TestClient

### 2. Execution Sandbox

```python
# sandbox/
├── executor/
│   ├── __init__.py
│   ├── runner.py            # Main execution logic
│   ├── security.py          # Import restrictions
│   ├── resource_monitor.py  # CPU/Memory tracking
│   └── output_capture.py    # stdout/stderr capture
├── Dockerfile               # Hardened Python image
└── seccomp-profile.json     # System call restrictions
```

**Security Layers:**
1. **Container Level:** gVisor or Firecracker for kernel isolation
2. **Python Level:** RestrictedPython or custom AST validation
3. **Import Restrictions:** Whitelist-only imports (no `os`, `subprocess`, `socket`)
4. **Resource Limits:** cgroups for CPU (100ms max), Memory (128MB max)
5. **Timeout:** Hard kill after 10 seconds
6. **Network:** No egress allowed

### 3. LLM Analysis Service

```python
# analyzer/
├── __init__.py
├── complexity.py            # Complexity analysis prompts
├── llm_client.py            # Abstract LLM interface
├── providers/
│   ├── openai.py
│   ├── anthropic.py
│   └── local.py             # Ollama for testing
└── prompts/
    ├── time_complexity.txt
    └── space_complexity.txt
```

**LLM Integration Pattern:**
```python
class ComplexityAnalyzer:
    async def analyze(self, code: str) -> ComplexityResult:
        prompt = self._build_prompt(code)
        response = await self.llm_client.complete(prompt)
        return self._parse_response(response)
```

### 4. Infrastructure (Pulumi - Python)

```python
# infra/
├── __main__.py              # Entry point
├── config.py                # Environment config
├── components/
│   ├── __init__.py
│   ├── networking.py        # VPC, subnets, security groups
│   ├── kubernetes.py        # EKS/GKE cluster
│   ├── database.py          # RDS/Cloud SQL
│   ├── queue.py             # SQS/Pub-Sub
│   └── storage.py           # S3/GCS
├── stacks/
│   ├── dev.py
│   ├── staging.py
│   └── prod.py
└── Pulumi.yaml
```

**Cloud Agnostic Abstraction:**
```python
# components/database.py
from abc import ABC, abstractmethod

class DatabaseProvider(ABC):
    @abstractmethod
    def create_postgres(self, name: str, config: DBConfig) -> Database:
        pass

class AWSDatabase(DatabaseProvider):
    def create_postgres(self, name: str, config: DBConfig) -> Database:
        return aws.rds.Instance(name, ...)

class GCPDatabase(DatabaseProvider):
    def create_postgres(self, name: str, config: DBConfig) -> Database:
        return gcp.sql.DatabaseInstance(name, ...)
```

---

## Testing Strategy

### Unit Tests
```
pytest backend/tests/unit/ -v --cov=backend
```
- Mock external services (LLM, Queue, Database)
- Test business logic in isolation
- Target: 80%+ coverage

### Integration Tests
```
docker-compose -f docker-compose.test.yml up
pytest backend/tests/integration/ -v
```
- Real containers for dependencies (Postgres, Redis)
- Test API endpoints
- Test queue consumers

### E2E Tests
```
pytest backend/tests/e2e/ -v --env=staging
```
- Deploy to staging environment
- Full flow: Submit → Execute → Return result
- Security penetration tests

### Local Development
```
# Start all services locally
docker-compose up -d

# Run specific service
cd backend && uvicorn api.main:app --reload

# Run sandbox locally (with relaxed security)
docker run -it --rm executor:dev python runner.py
```

---

## Security Checklist

| Layer | Control | Implementation |
|-------|---------|----------------|
| Network | No egress | K8s NetworkPolicy deny-all egress |
| Container | Kernel isolation | gVisor runsc runtime |
| Container | Resource limits | CPU: 0.1, Memory: 128Mi, Timeout: 10s |
| Python | Import restrictions | AST analysis, whitelist only |
| Python | Dangerous functions | Block `eval`, `exec`, `compile` with literals only |
| API | Authentication | JWT with short expiry (15 min) |
| API | Rate limiting | 10 requests/minute per user |
| API | Input validation | Pydantic schemas, max code size 10KB |
| Data | Encryption | TLS in transit, AES-256 at rest |

---

## Recommended Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Frontend | React + Monaco Editor | Industry standard, VS Code's editor |
| API Framework | FastAPI | Async, fast, great DX |
| Execution | Docker + gVisor | Security + portability |
| Orchestration | Kubernetes | Cloud agnostic |
| Queue | Redis Streams | Simple, fast, good for small messages |
| Database | PostgreSQL | Reliable, feature-rich |
| Cache | Redis | Session storage, rate limiting |
| IaC | Pulumi (Python) | Same language as backend |
| CI/CD | GitHub Actions | Integration with repo |
| Monitoring | Prometheus + Grafana | K8s native |
| LLM | OpenAI API (primary), Ollama (dev) | Quality + local testing |

---

## Project Structure (Complete)

```
code-remote/
├── .github/
│   ├── copilot-instructions.md
│   └── workflows/
│       ├── ci.yml
│       ├── cd.yml
│       └── security.yml
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── backend/
│   ├── api/
│   ├── executor/
│   ├── analyzer/
│   ├── common/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── infra/
│   ├── pulumi/
│   ├── kubernetes/
│   └── docker/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── security.md
├── docker-compose.yml
├── docker-compose.test.yml
├── Makefile
└── README.md
```

---

## Implementation Approach: Incremental Build (Option B) ✅

We will build one component at a time, verifying each piece works before moving on. This approach ensures deep understanding of each part and catches integration issues early.

**Build Order:** Backend API → Executor → Frontend → Infrastructure → Integration

---

## Implementation Phases

### Phase 1: Backend Foundation ✅ COMPLETE
**Goal:** Working FastAPI service with local Docker development

| Step | Task | Status |
|------|------|--------|
| 1.1 | Create project structure and `pyproject.toml` | ✅ |
| 1.2 | FastAPI skeleton with `/health` endpoint | ✅ |
| 1.3 | Pydantic settings with `.env` support | ✅ |
| 1.4 | Docker Compose for local development | ✅ |
| 1.5 | Unit test setup with pytest | ✅ |
| 1.6 | CI pipeline (GitHub Actions) | ✅ |

---

### Phase 2: Sandboxed Executor ✅ COMPLETE
**Goal:** Secure Python code execution with resource limits

| Step | Task | Status |
|------|------|--------|
| 2.1 | Basic executor that runs Python code | ✅ |
| 2.2 | Stdout/stderr capture | ✅ |
| 2.3 | Timeout enforcement (30s max) | ✅ |
| 2.4 | Import restrictions (whitelist) | ✅ |
| 2.5 | Resource limits (memory) | ✅ (via container) |
| 2.6 | Executor Docker image | ✅ |
| 2.7 | Unit tests (60 tests, 80% coverage) | ✅ |

**Key Files:**
- `backend/executor/security.py` - Import whitelist, AST validation
- `backend/executor/runner.py` - Sandboxed execution with multiprocessing
| 2.6 | Executor Docker image | Run executor in container |
| 2.7 | Integration tests | Full execution flow tested |

**Deliverables:**
- `backend/executor/` with sandboxed runner
- `backend/executor/Dockerfile`
- Security whitelist configuration

---

### Phase 3: API Integration
**Goal:** Connect API to executor via queue

| Step | Task | Verification |
|------|------|--------------|
| 3.1 | Execution request/response schemas | Pydantic models validate |
| 3.2 | `/execute` endpoint (sync for now) | Submit code, get result |
| 3.3 | Redis Streams queue setup | Queue accepts messages |
| 3.4 | Async execution via queue | Submit → poll → get result |
| 3.5 | `/status/{id}` endpoint | Check execution status |
| 3.6 | Error handling and validation | Bad input returns proper errors |

**Deliverables:**
- `backend/api/routers/execution.py`
- `backend/api/services/executor_service.py`
- Queue integration with Redis

---

### Phase 4: Frontend
**Goal:** Working code editor that submits and displays results

| Step | Task | Verification |
|------|------|--------------|
| 4.1 | React + Vite project setup | `npm run dev` starts app |
| 4.2 | Monaco Editor integration | Editor renders with Python syntax |
| 4.3 | API client for execution | Submit button calls `/execute` |
| 4.4 | Result display panel | See stdout/stderr/errors |
| 4.5 | Loading states and error handling | UX for pending/error states |
| 4.6 | Basic styling | Clean, usable interface |

**Deliverables:**
- `frontend/` with React + Monaco
- Working end-to-end execution flow

---

### Phase 5: LLM Complexity Analysis
**Goal:** Gemini-powered code analysis

| Step | Task | Verification |
|------|------|--------------|
| 5.1 | Gemini provider with API key auth | Connection test passes |
| 5.2 | Complexity analysis prompt | Returns time/space complexity |
| 5.3 | `/analyze` endpoint | Submit code, get analysis |
| 5.4 | Frontend integration | Show complexity after execution |
| 5.5 | Prompt refinement | Accurate results on test cases |

**Deliverables:**
- `backend/analyzer/` with Gemini provider
- Complexity prompts in `backend/analyzer/prompts/`

---

### Phase 6: Authentication
**Goal:** Cognito-based user authentication

| Step | Task | Verification |
|------|------|--------------|
| 6.1 | Cognito user pool setup (Pulumi) | Pool created in AWS |
| 6.2 | JWT validation middleware | Protected endpoints require token |
| 6.3 | AWS Amplify frontend integration | Login/logout flow works |
| 6.4 | User context in execution | Executions tied to user |

**Deliverables:**
- `infra/pulumi/components/auth.py`
- `backend/api/middleware/auth.py`
- Frontend auth flow

---

### Phase 7: Infrastructure & Deployment
**Goal:** Production-ready AWS deployment

| Step | Task | Verification |
|------|------|--------------|
| 7.1 | Pulumi project structure | `pulumi preview` works |
| 7.2 | VPC and networking | Resources created |
| 7.3 | RDS PostgreSQL | Database accessible |
| 7.4 | SQS queues | Messages flow through |
| 7.5 | EKS cluster for executor | Pods run successfully |
| 7.6 | ECR for container images | Images push/pull |
| 7.7 | GitHub Actions deploy workflow | Push to release branch deploys |

**Deliverables:**
- `infra/pulumi/` complete
- `kubernetes/` manifests
- `.github/workflows/deploy.yml`

---

### Phase 8: Security Hardening
**Goal:** Production security posture

| Step | Task | Verification |
|------|------|--------------|
| 8.1 | gVisor runtime on executor pods | Pods use runsc |
| 8.2 | Network policies (no egress) | Executor can't reach internet |
| 8.3 | Secrets Manager integration | No secrets in code/config |
| 8.4 | Security scanning in CI | Vulnerabilities flagged |
| 8.5 | Rate limiting | Abuse prevented |

**Deliverables:**
- Hardened Kubernetes manifests
- Security scanning workflow

---

## Decisions Made ✅

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | **Option 3: Hybrid** | Balance of managed services + execution control |
| **Build Approach** | **Option B: Incremental** | Build one component at a time, verify each works |
| Frontend | **React + Monaco Editor** | Industry standard, VS Code's editor |
| Authentication | **AWS Cognito** | Native AWS integration, managed service |
| LLM Provider | **Google Gemini** | API key auth only, no GCP setup required |
| Execution Timeout | **30 seconds** | Allows complex computations while limiting abuse |
| Initial Cloud | **AWS** | Mature ecosystem, Cognito integration |

---

## Final Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Monaco Editor + AWS Amplify |
| API Layer | AWS API Gateway + Lambda (routing) |
| Backend Services | FastAPI (containerized on ECS Fargate) |
| Execution | Self-hosted K8s cluster with gVisor |
| Queue | AWS SQS |
| Database | AWS RDS PostgreSQL |
| Cache | AWS ElastiCache Redis |
| Auth | AWS Cognito |
| LLM | Google Gemini API |
| IaC | Pulumi (Python) |
| CI/CD | GitHub Actions |

---

## Status: APPROVED ✅

- `.github/copilot-instructions.md` has been generated
- `documentation/RELEASE_WORKFLOW.md` documents deployment workflow
- **Current Phase: 1 - Backend Foundation** (Ready to start)

---

## Phase 9: Persistence & Code Snippets (IN PROGRESS)

**Goal:** Allow users to save, organize, and search code snippets with AI-powered semantic search

**Decision:** Hybrid Architecture - PostgreSQL (CRUD) + Neo4j (Vector Search)

### Feature Overview

Users can:
- Save code snippets with name, description, and analysis results
- Star favorite snippets
- Semantic search: "find my recursive snippets"

### Database Options Analysis

#### Option 1: PostgreSQL + pgvector (Recommended)
**Aurora Serverless v2 or RDS**

```
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector                                      │
├─────────────────────────────────────────────────────────────┤
│  ✓ Single DB for structured data AND vector embeddings      │
│  ✓ Relational model fits users → snippets naturally         │
│  ✓ pgvector: mature, supports cosine/L2/inner product       │
│  ✓ Hybrid search: combine WHERE clauses with vector search  │
│  ✓ Aurora Serverless v2 scales to near-zero                 │
│  ✗ Not truly serverless (min capacity units)                │
│  ✗ Cold starts possible                                     │
└─────────────────────────────────────────────────────────────┘
```

**Schema:**
```sql
-- Users (from Cognito, cached locally)
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
    
    -- Analysis results (nullable until analyzed)
    time_complexity VARCHAR(50),
    space_complexity VARCHAR(50),
    explanation TEXT,
    suggestions TEXT,
    analyzed_at TIMESTAMPTZ,
    model_used VARCHAR(100),
    
    -- Metadata
    is_starred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Vector embedding for semantic search (768 dims for Gemini)
    embedding vector(768)
);

-- Indexes
CREATE INDEX idx_snippets_user_id ON snippets(user_id);
CREATE INDEX idx_snippets_starred ON snippets(user_id, is_starred) WHERE is_starred = TRUE;
CREATE INDEX idx_snippets_embedding ON snippets USING ivfflat (embedding vector_cosine_ops);
```

---

#### Option 2: DynamoDB + OpenSearch Serverless
**Fully Serverless, AWS-Native**

```
┌─────────────────────────────────────────────────────────────┐
│  DynamoDB + OpenSearch Serverless                           │
├─────────────────────────────────────────────────────────────┤
│  ✓ Truly serverless, scales to zero                         │
│  ✓ Native AWS integration                                   │
│  ✓ OpenSearch has k-NN vector search                        │
│  ✗ Two services to manage and sync                          │
│  ✗ OpenSearch Serverless has minimum cost (~$700/mo)        │
│  ✗ Complex for relational queries (denormalization needed)  │
└─────────────────────────────────────────────────────────────┘
```

**Schema (Single-Table Design):**
```
PK                      SK                      Attributes
─────────────────────────────────────────────────────────────
USER#<userId>           PROFILE                 email, createdAt
USER#<userId>           SNIPPET#<snippetId>     name, code, description, ...
USER#<userId>           STARRED#<snippetId>     (GSI for starred queries)
```

---

#### Option 3: MongoDB Atlas
**Flexible Schema + Built-in Vector Search**

```
┌─────────────────────────────────────────────────────────────┐
│  MongoDB Atlas                                              │
├─────────────────────────────────────────────────────────────┤
│  ✓ Atlas Vector Search built-in (no separate service)       │
│  ✓ Flexible schema for evolving analysis results            │
│  ✓ Good aggregation pipeline for complex queries            │
│  ✓ Serverless tier available                                │
│  ✗ Outside AWS ecosystem (adds latency)                     │
│  ✗ Another platform/credentials to manage                   │
└─────────────────────────────────────────────────────────────┘
```

---

#### Option 4: Supabase (PostgreSQL + pgvector)
**Managed PostgreSQL with Extras**

```
┌─────────────────────────────────────────────────────────────┐
│  Supabase                                                   │
├─────────────────────────────────────────────────────────────┤
│  ✓ Managed Postgres + pgvector                              │
│  ✓ Real-time subscriptions (future collab features)         │
│  ✓ Built-in auth (could replace Cognito eventually)         │
│  ✓ Edge functions                                           │
│  ✗ Outside AWS (latency, another platform)                  │
│  ✗ Vendor lock-in to Supabase specifics                     │
└─────────────────────────────────────────────────────────────┘
```

---

#### Option 5: Neo4j AuraDB (Graph Database)
**Native Graph with Vector Search**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Neo4j AuraDB + Vector Index                                            │
├─────────────────────────────────────────────────────────────────────────┤
│  ✓ Native graph traversals for relationship queries                     │
│  ✓ Neo4j 5.x has native vector search (vector indexes)                  │
│  ✓ Cypher query language is expressive and readable                     │
│  ✓ AuraDB Free tier available (good for dev)                            │
│  ✓ Excellent for "similar to", "related to", recommendations            │
│  ✓ Can model code patterns as a knowledge graph                         │
│  ✗ Outside AWS ecosystem (adds latency, another platform)               │
│  ✗ Overkill if relationships stay simple                                │
│  ✗ Learning curve for Cypher if team is SQL-focused                     │
│  ✗ AuraDB Pro pricing can get expensive                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Why Graph Databases Could Be Valuable:**

For semantic search and future features, graphs excel at modeling relationships:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Potential Relationships in Code Snippets                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────┐         ┌─────────┐         ┌─────────┐                     │
│   │ User │──owns──▶│ Snippet │──uses──▶│ Pattern │                     │
│   └──────┘         └─────────┘         └─────────┘                     │
│      │                  │                   │                           │
│      │ starred          │ similar_to        │ related_to               │
│      ▼                  ▼                   ▼                           │
│   ┌─────────┐      ┌─────────┐         ┌─────────┐                     │
│   │ Snippet │      │ Snippet │         │ Pattern │                     │
│   └─────────┘      └─────────┘         └─────────┘                     │
│                         │                                               │
│                         │ has_complexity                                │
│                         ▼                                               │
│                    ┌───────────┐                                        │
│                    │ O(n log n)│                                        │
│                    └───────────┘                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

**Graph Schema:**

```cypher
// Node types
(:User {id, cognito_sub, email, created_at})
(:Snippet {id, name, description, code, language, time_complexity, 
           space_complexity, embedding, created_at, updated_at})
(:Pattern {name, description})  -- e.g., "recursion", "memoization", "two-pointer"
(:Complexity {notation, category})  -- e.g., "O(n)", "linear"
(:Tag {name})

// Relationship types
(:User)-[:OWNS]->(:Snippet)
(:User)-[:STARRED {starred_at}]->(:Snippet)
(:Snippet)-[:SIMILAR_TO {score}]->(:Snippet)  -- computed from embeddings
(:Snippet)-[:USES]->(:Pattern)  -- extracted by LLM during analysis
(:Snippet)-[:HAS_TIME_COMPLEXITY]->(:Complexity)
(:Snippet)-[:HAS_SPACE_COMPLEXITY]->(:Complexity)
(:Snippet)-[:TAGGED_WITH]->(:Tag)
(:Pattern)-[:RELATED_TO]->(:Pattern)  -- e.g., recursion → memoization
```

**Powerful Graph Queries:**

```cypher
-- "Find snippets similar to my starred snippets"
MATCH (me:User {id: $userId})-[:STARRED]->(s:Snippet)-[:SIMILAR_TO*1..2]->(related:Snippet)
WHERE NOT (me)-[:OWNS]->(related)
RETURN related

-- "Find all recursive patterns I've used"
MATCH (me:User)-[:OWNS]->(s:Snippet)-[:USES]->(p:Pattern {name: 'recursion'})
RETURN s, p

-- "Recommend snippets based on users with similar patterns"
MATCH (me:User)-[:OWNS]->(:Snippet)-[:USES]->(p:Pattern)<-[:USES]-(:Snippet)<-[:OWNS]-(other:User)
MATCH (other)-[:STARRED]->(recommended:Snippet)
WHERE NOT (me)-[:OWNS]->(recommended)
RETURN recommended, count(*) AS score ORDER BY score DESC
```

**Hybrid Search (Vector + Graph):**

```cypher
// Semantic search with graph context
CALL db.index.vector.queryNodes('snippet-embeddings', 10, $query_embedding)
YIELD node AS snippet, score
MATCH (user:User {id: $userId})-[:OWNS]->(snippet)
OPTIONAL MATCH (snippet)-[:USES]->(pattern:Pattern)
RETURN snippet, collect(pattern.name) AS patterns, score
ORDER BY score DESC
```

---

#### Option 6: Amazon Neptune (AWS-Native Graph)
**AWS-Managed Graph Database**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Amazon Neptune                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  ✓ AWS-native, VPC integration, IAM auth                                │
│  ✓ Supports both Gremlin and SPARQL                                     │
│  ✓ Neptune Analytics has vector similarity (preview)                    │
│  ✓ Serverless option available                                          │
│  ✗ More expensive than Neo4j AuraDB Free                                │
│  ✗ Gremlin syntax is verbose compared to Cypher                         │
│  ✗ Vector search less mature than pgvector or Neo4j                     │
│  ✗ Minimum ~$0.10/hour even for serverless                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Graph vs. Relational Comparison

| Feature | Relational (pgvector) | Graph (Neo4j) |
|---------|----------------------|---------------|
| **User → Snippet CRUD** | ✅ Simple, fast | ⚠️ Works but overkill |
| **Semantic search** | ✅ pgvector excellent | ✅ Neo4j vector indexes |
| **"Similar snippets"** | ⚠️ Requires joins | ✅ Native traversal |
| **Pattern knowledge graph** | ❌ Complex JOINs | ✅ Natural fit |
| **Recommendations** | ⚠️ Complex queries | ✅ Graph algorithms built-in |
| **Multi-hop queries** | ❌ Recursive CTEs | ✅ Simple traversals |
| **AWS integration** | ✅ Aurora native | ⚠️ Neptune or external |
| **Operational simplicity** | ✅ Familiar SQL | ⚠️ New paradigm |

---

### Option 7: Hybrid Approach (PostgreSQL + Neo4j)
**Best of Both Worlds**

For projects that need strong CRUD with eventual graph capabilities:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Hybrid Architecture                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Lambda (FastAPI)                            │   │
│  │  - CRUD operations → PostgreSQL                                  │   │
│  │  - Recommendations → Neo4j                                       │   │
│  │  - Semantic search → PostgreSQL (pgvector)                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                    │                           │                        │
│                    ▼                           ▼                        │
│  ┌──────────────────────────┐    ┌──────────────────────────────────┐  │
│  │   Aurora PostgreSQL      │    │   Neo4j AuraDB                   │  │
│  │   + pgvector             │───▶│   (sync via CDC/events)          │  │
│  │                          │    │                                  │  │
│  │   • Users table          │    │   • Pattern knowledge graph      │  │
│  │   • Snippets table       │    │   • Similarity relationships     │  │
│  │   • Vector embeddings    │    │   • Recommendations engine       │  │
│  └──────────────────────────┘    └──────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Phased Implementation:**
1. **Phase 1:** PostgreSQL handles CRUD + semantic search (simpler, cheaper)
2. **Phase 2:** If pattern detection is added (LLM extracts "uses recursion"), add Neo4j for the knowledge graph
3. **Phase 3:** Use Neo4j for recommendations ("users who wrote similar code also liked...")

---

#### CDC/Events Synchronization Deep Dive

**What is CDC (Change Data Capture)?**

CDC captures row-level changes (INSERT, UPDATE, DELETE) from PostgreSQL and streams them to other systems. For the hybrid approach, we sync snippet data from PostgreSQL (source of truth) to Neo4j (graph layer).

**Synchronization Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     PostgreSQL → Neo4j Sync Options                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Option A: AWS DMS (Database Migration Service)                                 │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                 │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    │
│  │   Aurora     │───▶│   AWS DMS   │───▶│   Kinesis    │───▶│   Lambda    │    │
│  │  PostgreSQL  │    │  (CDC task) │    │   Stream     │    │  (writer)   │    │
│  └──────────────┘    └─────────────┘    └──────────────┘    └──────┬──────┘    │
│         │                                                          │           │
│         │ logical replication                                      │ Cypher    │
│         │ (wal2json)                                               ▼           │
│         │                                                   ┌─────────────┐    │
│         │                                                   │   Neo4j     │    │
│         └─ Snapshots table ─────────────────────────────────│   AuraDB    │    │
│                                                             └─────────────┘    │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Option B: Application-Level Events (Simpler for MVP)                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                 │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    │
│  │   Lambda     │───▶│  EventBridge│───▶│   Lambda     │───▶│   Neo4j     │    │
│  │  (API CRUD)  │    │  (event bus)│    │  (sync fn)   │    │   AuraDB    │    │
│  └──────┬───────┘    └─────────────┘    └──────────────┘    └─────────────┘    │
│         │                                                                       │
│         │ writes                                                                │
│         ▼                                                                       │
│  ┌──────────────┐                                                               │
│  │   Aurora     │                                                               │
│  │  PostgreSQL  │                                                               │
│  └──────────────┘                                                               │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Option C: Debezium (Open Source CDC)                                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                 │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    │
│  │   Aurora     │───▶│  Debezium   │───▶│    Kafka     │───▶│   Kafka     │    │
│  │  PostgreSQL  │    │  Connector  │    │   (MSK)      │    │  Consumer   │────│
│  └──────────────┘    └─────────────┘    └──────────────┘    └─────────────┘    │
│                                                                          │      │
│                                                                          ▼      │
│                                                                   ┌─────────┐   │
│                                                                   │  Neo4j  │   │
│                                                                   └─────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Recommended: Option B (Application-Level Events)**

For our scale and simplicity goals, application-level events via EventBridge is the best fit:

```python
# backend/api/services/snippet_service.py

from backend.common.events import event_bus

class SnippetService:
    async def create_snippet(self, user_id: str, data: SnippetCreate) -> Snippet:
        # 1. Write to PostgreSQL (source of truth)
        snippet = await self.repo.create(user_id, data)
        
        # 2. Emit event for graph sync (async, non-blocking)
        await event_bus.publish(
            event_type="snippet.created",
            payload={
                "snippet_id": str(snippet.id),
                "user_id": user_id,
                "patterns": snippet.detected_patterns,  # LLM-extracted
                "complexity": snippet.time_complexity,
                "embedding": snippet.embedding.tolist(),
            }
        )
        
        return snippet
    
    async def update_snippet(self, snippet_id: str, data: SnippetUpdate) -> Snippet:
        snippet = await self.repo.update(snippet_id, data)
        await event_bus.publish("snippet.updated", {...})
        return snippet
    
    async def delete_snippet(self, snippet_id: str) -> None:
        await self.repo.delete(snippet_id)
        await event_bus.publish("snippet.deleted", {"snippet_id": snippet_id})
```

**EventBridge Configuration (Pulumi):**

```python
# infra/pulumi/components/events.py

import pulumi_aws as aws

def create_snippet_event_bus(env: str):
    # Custom event bus for snippet events
    event_bus = aws.cloudwatch.EventBus(
        f"{env}-snippet-events",
        name=f"code-remote-{env}-snippets"
    )
    
    # Rule to route snippet events to Neo4j sync Lambda
    neo4j_sync_rule = aws.cloudwatch.EventRule(
        f"{env}-neo4j-sync-rule",
        event_bus_name=event_bus.name,
        event_pattern=json.dumps({
            "source": ["code-remote.snippets"],
            "detail-type": ["snippet.created", "snippet.updated", "snippet.deleted"]
        })
    )
    
    # Target: Lambda function for Neo4j sync
    aws.cloudwatch.EventTarget(
        f"{env}-neo4j-sync-target",
        rule=neo4j_sync_rule.name,
        event_bus_name=event_bus.name,
        arn=neo4j_sync_lambda.arn
    )
    
    return event_bus
```

**Neo4j Sync Lambda:**

```python
# backend/api/handlers/neo4j_sync.py

from neo4j import AsyncGraphDatabase

async def handler(event, context):
    """Process EventBridge events and sync to Neo4j."""
    
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    
    async with driver.session() as session:
        detail_type = event["detail-type"]
        payload = event["detail"]
        
        if detail_type == "snippet.created":
            await session.run("""
                MERGE (u:User {id: $user_id})
                CREATE (s:Snippet {
                    id: $snippet_id,
                    embedding: $embedding
                })
                CREATE (u)-[:OWNS]->(s)
                
                // Create pattern relationships
                WITH s
                UNWIND $patterns AS pattern_name
                MERGE (p:Pattern {name: pattern_name})
                CREATE (s)-[:USES]->(p)
                
                // Create complexity node
                WITH s
                MERGE (c:Complexity {notation: $complexity})
                CREATE (s)-[:HAS_COMPLEXITY]->(c)
            """, {
                "user_id": payload["user_id"],
                "snippet_id": payload["snippet_id"],
                "embedding": payload["embedding"],
                "patterns": payload.get("patterns", []),
                "complexity": payload.get("complexity", "unknown")
            })
            
        elif detail_type == "snippet.deleted":
            await session.run("""
                MATCH (s:Snippet {id: $snippet_id})
                DETACH DELETE s
            """, {"snippet_id": payload["snippet_id"]})
            
        elif detail_type == "snippet.updated":
            # Update snippet properties and relationships
            await session.run("""
                MATCH (s:Snippet {id: $snippet_id})
                SET s.embedding = $embedding
                
                // Update patterns (delete old, create new)
                WITH s
                OPTIONAL MATCH (s)-[r:USES]->(:Pattern)
                DELETE r
                
                WITH s
                UNWIND $patterns AS pattern_name
                MERGE (p:Pattern {name: pattern_name})
                CREATE (s)-[:USES]->(p)
            """, payload)
    
    await driver.close()
```

**Similarity Computation (Async Job):**

The `SIMILAR_TO` relationships between snippets can be computed periodically or on-demand:

```python
# backend/jobs/compute_similarity.py

async def compute_snippet_similarities(user_id: str):
    """Compute and store similarity relationships in Neo4j."""
    
    async with neo4j_driver.session() as session:
        # Find similar snippets using vector index
        await session.run("""
            // For each snippet owned by user
            MATCH (u:User {id: $user_id})-[:OWNS]->(s:Snippet)
            WHERE s.embedding IS NOT NULL
            
            // Find similar snippets (vector search)
            CALL db.index.vector.queryNodes(
                'snippet-embeddings', 
                5,  // top 5 similar
                s.embedding
            ) YIELD node AS similar, score
            
            // Don't link to self
            WHERE similar.id <> s.id AND score > 0.8
            
            // Create or update similarity relationship
            MERGE (s)-[r:SIMILAR_TO]->(similar)
            SET r.score = score, r.computed_at = datetime()
        """, {"user_id": user_id})
```

**Event Flow Diagram:**

```
User saves snippet
        │
        ▼
┌───────────────────┐
│  POST /snippets   │
│  (Lambda/FastAPI) │
└─────────┬─────────┘
          │
          ├──────────────────────────────┐
          │                              │
          ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐
│  PostgreSQL         │      │  EventBridge        │
│  (INSERT snippet)   │      │  (emit event)       │
└─────────────────────┘      └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │  Neo4j Sync Lambda  │
                             │  (process event)    │
                             └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │  Neo4j AuraDB       │
                             │  (CREATE nodes,     │
                             │   relationships)    │
                             └─────────────────────┘
```

**Consistency Considerations:**

| Concern | Solution |
|---------|----------|
| **Event ordering** | EventBridge preserves order per partition |
| **Duplicate events** | Make Neo4j operations idempotent (MERGE) |
| **Failed sync** | DLQ + retry with exponential backoff |
| **Initial sync** | One-time bulk sync job on Neo4j addition |
| **Data drift** | Periodic reconciliation job |

**Reconciliation Job (Weekly):**

```python
# backend/jobs/reconcile_graph.py

async def reconcile_postgres_neo4j():
    """Ensure Neo4j graph matches PostgreSQL source of truth."""
    
    # Get all snippet IDs from PostgreSQL
    pg_snippets = await pg_repo.get_all_snippet_ids()
    
    # Get all snippet IDs from Neo4j
    async with neo4j_driver.session() as session:
        result = await session.run("MATCH (s:Snippet) RETURN s.id AS id")
        neo4j_snippets = {r["id"] async for r in result}
    
    # Find orphaned nodes in Neo4j (deleted in PG)
    orphaned = neo4j_snippets - set(pg_snippets)
    if orphaned:
        await session.run(
            "UNWIND $ids AS id MATCH (s:Snippet {id: id}) DETACH DELETE s",
            {"ids": list(orphaned)}
        )
    
    # Find missing nodes in Neo4j (need sync)
    missing = set(pg_snippets) - neo4j_snippets
    if missing:
        for snippet_id in missing:
            snippet = await pg_repo.get(snippet_id)
            await sync_snippet_to_neo4j(snippet)
```

**Cost Estimate (with Neo4j sync):**

| Component | Monthly Cost |
|-----------|-------------|
| Aurora PostgreSQL (0.5 ACU avg) | ~$45 |
| EventBridge (1M events) | ~$1 |
| Lambda (sync function) | ~$5 |
| Neo4j AuraDB Free | $0 |
| **Total** | **~$51/mo** |

*Note: Neo4j AuraDB Free tier includes 200K nodes, 400K relationships - plenty for MVP*

---

### Recommendation: **PostgreSQL + pgvector on Aurora Serverless v2**

**Why:**

| Factor | PostgreSQL + pgvector |
|--------|----------------------|
| **Data Model** | Relational fits perfectly (users → snippets) |
| **Vector Search** | pgvector in same DB, hybrid queries |
| **AWS Integration** | Aurora Serverless v2, IAM auth, VPC |
| **Cost** | ~$0.12/ACU-hour, scales down when idle |
| **Complexity** | Single database, familiar SQL |
| **Future-proof** | Can add full-text search, JSON columns |

**Hybrid Search Query Example:**
```sql
-- "Find my starred recursive snippets"
SELECT id, name, description, code,
       1 - (embedding <=> $query_embedding) AS similarity
FROM snippets
WHERE user_id = $user_id
  AND is_starred = TRUE
ORDER BY embedding <=> $query_embedding
LIMIT 10;
```

**Why Not Start with Graph?**
- MVP (save/search snippets) doesn't need graph traversals
- PostgreSQL is operationally simpler
- Can add Neo4j later without migrating (it's additive)

**Why Keep Graph in Mind?**
- The "semantic search" vision ("find my recursive snippets") is exactly what graphs excel at when combined with a pattern knowledge graph
- Future features like "suggest similar code" or "learn from others' patterns" would benefit enormously

---

### Embedding Strategy

For semantic search, embeddings are generated when snippets are saved:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Code Snippet   │────▶│  Embedding API   │────▶│  PostgreSQL │
│  + Description  │     │  (Gemini/OpenAI) │     │  pgvector   │
└─────────────────┘     └──────────────────┘     └─────────────┘
                              │
                              ▼
                        768/1536 dims
```

**Options:**
1. **Gemini Embedding** - `text-embedding-004` (768 dims) - already have API key
2. **OpenAI** - `text-embedding-3-small` (1536 dims)
3. **Self-hosted** - Sentence Transformers (free, but need compute)

---

### Proposed Architecture with Persistence

```
┌────────────────────────────────────────────────────────────────────┐
│                         Code Remote                                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────────┐  │
│  │ Frontend │───▶│ API Gateway  │───▶│ Lambda (FastAPI)        │  │
│  └──────────┘    └──────────────┘    │  - /snippets CRUD       │  │
│                                      │  - /snippets/search     │  │
│                                      └───────────┬─────────────┘  │
│                                                  │                │
│                         ┌────────────────────────┼────────────┐   │
│                         │                        │            │   │
│                         ▼                        ▼            │   │
│              ┌─────────────────┐    ┌─────────────────────┐   │   │
│              │ Aurora Postgres │    │ Gemini Embedding    │   │   │
│              │ + pgvector      │◀───│ API                 │   │   │
│              └─────────────────┘    └─────────────────────┘   │   │
│                                                               │   │
└───────────────────────────────────────────────────────────────────┘
```

---

### Implementation Steps (Phase 9)

#### Phase 9.1: PostgreSQL Foundation (Backend Only)
| Step | Task | Details |
|------|------|---------|
| 9.1.1 | Pulumi: Aurora Serverless v2 | VPC, subnet groups, security groups |
| 9.1.2 | Database migrations | Alembic setup, initial schema |
| 9.1.3 | SQLAlchemy models | User, Snippet (no vector column yet) |
| 9.1.4 | User sync service | Sync Cognito users to PostgreSQL |
| 9.1.5 | Snippet CRUD endpoints | POST/GET/PUT/DELETE /snippets |

#### Phase 9.2: Neo4j Graph Layer + CDC Sync
| Step | Task | Details |
|------|------|---------|
| 9.2.1 | Neo4j AuraDB setup | Free tier, get connection credentials |
| 9.2.2 | EventBridge event bus | Route snippet events to sync Lambda |
| 9.2.3 | Sync Lambda | PG → Neo4j on create/update/delete |
| 9.2.4 | Graph schema | User, Snippet, Pattern nodes |
| 9.2.5 | Reconciliation job | Weekly sync validation |

#### Phase 9.3: Vector Search
| Step | Task | Details |
|------|------|---------|
| 9.3.1 | Gemini embedding service | Generate embeddings on snippet save |
| 9.3.2 | Store embeddings in Neo4j | Vector index on Snippet nodes |
| 9.3.3 | Semantic search endpoint | GET /snippets/search?q= |
| 9.3.4 | SIMILAR_TO computation | Async job for similarity relationships |

#### Phase 9.4: Pattern Knowledge Graph (Future)
| Step | Task | Details |
|------|------|---------|
| 9.4.1 | LLM pattern extraction | Detect patterns during analysis |
| 9.4.2 | Pattern nodes | "recursion", "memoization", etc. |
| 9.4.3 | Advanced queries | "Find my recursive snippets" |

**Status:** ✅ APPROVED - Phase 9.1 starting (Backend Only)

**Decisions Made:**
- PostgreSQL: Aurora Serverless v2 (source of truth for CRUD)
- Graph DB: Neo4j AuraDB (free tier, Cypher queries)
- CDC: EventBridge (app-level events, simpler than DMS)
- Phasing: PostgreSQL first, Neo4j added in 9.2

---

## Phase 10: Async Execution & Event-Driven Architecture (✅ COMPLETE)

**Goal:** Replace synchronous execution with robust async job processing using SQS, enabling retries, better UX, and laying groundwork for future eventing needs.

**Implementation:** Stateless WebSocket design - no DynamoDB for job tracking. Connection ID passed in request, results pushed immediately via WebSocket Management API.

### Current Problem

The current execution flow is **synchronous request-response**:

```
┌──────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────────────┐
│ Frontend │────▶│ API Gateway │────▶│   Lambda    │────▶│ Execute (in-proc) │
│          │◀────│             │◀────│  (Mangum)   │◀────│ or Fargate task   │
└──────────┘     └─────────────┘     └─────────────┘     └───────────────────┘
                        ▲                                         │
                        │                                         │
                        └─────── waits synchronously ─────────────┘
```

**Problems:**

| Issue | Impact |
|-------|--------|
| **API Gateway timeout (29s)** | If execution + Fargate cold start > 29s → client gets 504 |
| **Lambda timeout billing** | Lambda sits idle while polling Fargate |
| **No retry on failures** | Transient errors fail the entire request |
| **No backpressure** | Traffic spike = uncontrolled Fargate task explosion |
| **Poor UX** | User stares at spinner with no progress feedback |
| **No execution history** | Results lost after response sent |

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Async Execution with SQS                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ Frontend │───▶│ POST /exec  │───▶│ SQS Queue   │───▶│  Worker Lambda      │ │
│  │          │    │ (returns    │    │ (jobs)      │    │  (or Fargate)       │ │
│  │          │    │  job_id)    │    │             │    │                     │ │
│  └────┬─────┘    └─────────────┘    └─────────────┘    └──────────┬──────────┘ │
│       │                                                           │            │
│       │ poll or WebSocket                                         │ writes     │
│       │                                                           ▼            │
│       │         ┌─────────────┐    ┌───────────────────────────────────────┐   │
│       └────────▶│ GET /status │◀───│  DynamoDB (jobs table)                │   │
│                 │ or WS push  │    │  - job_id, status, created_at         │   │
│                 └─────────────┘    │  - result (stdout, stderr, error)     │   │
│                                    │  - TTL for auto-cleanup               │   │
│                                    └───────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Dead Letter Queue (DLQ)                                                │   │
│  │  - Failed jobs after 3 retries                                          │   │
│  │  - Alarm triggers on DLQ depth                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Benefits

| Benefit | Description |
|---------|-------------|
| **Decoupled** | API responds immediately with `job_id` (< 100ms), no timeout risk |
| **Retries** | SQS handles retries with exponential backoff (3 attempts default) |
| **DLQ** | Failed executions go to dead-letter queue for debugging/alerting |
| **Throttling** | Control concurrency via Lambda reserved concurrency |
| **Progress** | Can update status: `pending` → `running` → `completed` / `failed` |
| **History** | Results stored in DynamoDB, queryable later |
| **WebSockets** | Push results to frontend when ready (optional enhancement) |
| **Reusable** | Same pattern for snippet sync, LLM analysis, etc. |

### Data Model (DynamoDB)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Jobs Table                                                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Partition Key: job_id (UUID)                                                   │
│  Sort Key: (none - single item per job)                                         │
│                                                                                 │
│  Attributes:                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  job_id:        UUID (PK)                                               │   │
│  │  user_id:       string (Cognito sub, GSI for user's jobs)               │   │
│  │  status:        enum (pending | running | completed | failed)           │   │
│  │  code:          string (the submitted code)                             │   │
│  │  timeout_seconds: number                                                │   │
│  │                                                                         │   │
│  │  # Set when running                                                     │   │
│  │  started_at:    ISO timestamp                                           │   │
│  │                                                                         │   │
│  │  # Set when completed/failed                                            │   │
│  │  completed_at:  ISO timestamp                                           │   │
│  │  result: {                                                              │   │
│  │    success:     boolean                                                 │   │
│  │    stdout:      string                                                  │   │
│  │    stderr:      string                                                  │   │
│  │    error:       string | null                                           │   │
│  │    error_type:  string | null                                           │   │
│  │    execution_time_ms: number                                            │   │
│  │    timed_out:   boolean                                                 │   │
│  │  }                                                                      │   │
│  │                                                                         │   │
│  │  # Metadata                                                             │   │
│  │  created_at:    ISO timestamp                                           │   │
│  │  ttl:           Unix timestamp (auto-delete after 24h)                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  GSI: user_id-created_at-index (for listing user's recent jobs)                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### API Changes

**New Endpoints:**

```python
# POST /execute → Returns job_id immediately
@router.post("/execute", response_model=JobSubmittedResponse)
async def submit_execution(
    request: ExecutionRequest,
    user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
) -> JobSubmittedResponse:
    """Submit code for async execution. Returns job_id to poll for results."""
    job = await job_service.submit(
        user_id=user.sub,
        code=request.code,
        timeout_seconds=request.timeout_seconds,
    )
    return JobSubmittedResponse(
        job_id=job.job_id,
        status="pending",
        poll_url=f"/jobs/{job.job_id}",
    )


# GET /jobs/{job_id} → Poll for status/results
@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    """Get the status and results of an execution job."""
    job = await job_service.get(job_id, user_id=user.sub)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        result=job.result if job.status in ("completed", "failed") else None,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# GET /jobs → List user's recent jobs
@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
    limit: int = Query(default=10, le=50),
) -> list[JobSummary]:
    """List the user's recent execution jobs."""
    return await job_service.list_for_user(user_id=user.sub, limit=limit)
```

**Response Models:**

```python
# api/schemas/jobs.py

class JobSubmittedResponse(BaseModel):
    job_id: str
    status: Literal["pending"]
    poll_url: str


class JobResult(BaseModel):
    success: bool
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None
    error_type: str | None = None
    execution_time_ms: float | None = None
    timed_out: bool = False


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    result: JobResult | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobSummary(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    execution_time_ms: float | None = None
```

### Job Service Implementation

```python
# backend/api/services/job_service.py

import json
import uuid
from datetime import datetime, timedelta

import boto3

from api.schemas.jobs import JobResult, JobStatusResponse
from common.config import settings


class JobService:
    """Service for managing async execution jobs."""

    def __init__(self):
        self.sqs = boto3.client("sqs", region_name=settings.aws_region)
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.jobs_table = self.dynamodb.Table(settings.jobs_table_name)
        self.queue_url = settings.execution_queue_url

    async def submit(
        self,
        user_id: str,
        code: str,
        timeout_seconds: float | None = None,
    ) -> JobStatusResponse:
        """Submit a new execution job."""
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ttl = int((now + timedelta(hours=24)).timestamp())

        # 1. Create job record in DynamoDB (pending)
        item = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "pending",
            "code": code,
            "timeout_seconds": timeout_seconds or settings.execution_timeout_seconds,
            "created_at": now.isoformat(),
            "ttl": ttl,
        }
        self.jobs_table.put_item(Item=item)

        # 2. Send message to SQS queue
        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({
                "job_id": job_id,
                "user_id": user_id,
                "code": code,
                "timeout_seconds": item["timeout_seconds"],
            }),
            MessageGroupId=user_id,  # FIFO: preserve order per user
            MessageDeduplicationId=job_id,
        )

        return JobStatusResponse(
            job_id=job_id,
            status="pending",
            created_at=now,
        )

    async def get(self, job_id: str, user_id: str) -> JobStatusResponse | None:
        """Get a job by ID, validating ownership."""
        response = self.jobs_table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        
        if not item or item.get("user_id") != user_id:
            return None

        return self._item_to_response(item)

    async def update_status(
        self,
        job_id: str,
        status: str,
        result: JobResult | None = None,
    ) -> None:
        """Update job status (called by worker)."""
        now = datetime.utcnow().isoformat()
        
        update_expr = "SET #status = :status"
        expr_values = {":status": status}
        expr_names = {"#status": "status"}

        if status == "running":
            update_expr += ", started_at = :started_at"
            expr_values[":started_at"] = now
        elif status in ("completed", "failed"):
            update_expr += ", completed_at = :completed_at"
            expr_values[":completed_at"] = now
            if result:
                update_expr += ", #result = :result"
                expr_names["#result"] = "result"
                expr_values[":result"] = result.model_dump()

        self.jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )

    def _item_to_response(self, item: dict) -> JobStatusResponse:
        """Convert DynamoDB item to response model."""
        result = None
        if "result" in item:
            result = JobResult(**item["result"])
        
        return JobStatusResponse(
            job_id=item["job_id"],
            status=item["status"],
            result=result,
            created_at=datetime.fromisoformat(item["created_at"]),
            started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
            completed_at=datetime.fromisoformat(item["completed_at"]) if item.get("completed_at") else None,
        )
```

### Worker Lambda (SQS Consumer)

```python
# backend/api/handlers/execution_worker.py

"""
SQS-triggered Lambda that processes execution jobs.

This worker:
1. Receives job from SQS queue
2. Updates status to "running" in DynamoDB
3. Executes the code (in-process or via Fargate)
4. Updates status to "completed" or "failed" with results
"""

import json
import logging

from api.schemas.jobs import JobResult
from api.services.job_service import JobService
from api.services.lambda_executor import LambdaExecutor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

job_service = JobService()
executor = LambdaExecutor()


def handler(event, context):
    """Process SQS messages containing execution jobs."""
    
    for record in event.get("Records", []):
        process_job(record)
    
    # Return success - failed messages will be retried by SQS
    return {"statusCode": 200}


def process_job(record: dict) -> None:
    """Process a single execution job from SQS."""
    try:
        body = json.loads(record["body"])
        job_id = body["job_id"]
        code = body["code"]
        timeout_seconds = body.get("timeout_seconds", 30)
        
        logger.info(f"Processing job {job_id}")
        
        # 1. Mark job as running
        job_service.update_status(job_id, "running")
        
        # 2. Execute the code
        result = executor.execute(code, timeout_seconds=timeout_seconds)
        
        # 3. Convert to JobResult
        job_result = JobResult(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            error=result.error,
            error_type=result.error_type,
            execution_time_ms=result.execution_time_ms,
            timed_out=result.timed_out,
        )
        
        # 4. Update job as completed/failed
        status = "completed" if result.success else "failed"
        job_service.update_status(job_id, status, result=job_result)
        
        logger.info(f"Job {job_id} {status}")
        
    except Exception as e:
        logger.error(f"Error processing job: {e}")
        # Don't catch - let SQS retry
        raise
```

### Infrastructure (Pulumi)

```python
# infra/pulumi/components/execution_queue.py

import json
import pulumi
import pulumi_aws as aws


def create_execution_queue(env: str, worker_lambda: aws.lambda_.Function):
    """Create SQS queue for async execution jobs."""
    
    # Dead Letter Queue for failed jobs
    dlq = aws.sqs.Queue(
        f"{env}-execution-dlq",
        name=f"code-remote-{env}-execution-dlq.fifo",
        fifo_queue=True,
        message_retention_seconds=1209600,  # 14 days
    )
    
    # Main execution queue
    queue = aws.sqs.Queue(
        f"{env}-execution-queue",
        name=f"code-remote-{env}-execution.fifo",
        fifo_queue=True,
        content_based_deduplication=False,
        visibility_timeout_seconds=60,  # Must be > Lambda timeout
        receive_wait_time_seconds=20,  # Long polling
        redrive_policy=dlq.arn.apply(lambda arn: json.dumps({
            "deadLetterTargetArn": arn,
            "maxReceiveCount": 3,  # 3 retries before DLQ
        })),
    )
    
    # Lambda trigger from SQS
    aws.lambda_.EventSourceMapping(
        f"{env}-execution-trigger",
        event_source_arn=queue.arn,
        function_name=worker_lambda.name,
        batch_size=1,  # Process one job at a time
        enabled=True,
    )
    
    # CloudWatch alarm for DLQ depth
    aws.cloudwatch.MetricAlarm(
        f"{env}-dlq-alarm",
        alarm_name=f"code-remote-{env}-execution-dlq-depth",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=1,
        metric_name="ApproximateNumberOfMessagesVisible",
        namespace="AWS/SQS",
        period=300,
        statistic="Sum",
        threshold=0,
        alarm_description="Execution jobs failing and going to DLQ",
        dimensions={"QueueName": dlq.name},
        # alarm_actions=[sns_topic.arn],  # Add SNS for notifications
    )
    
    return queue, dlq


def create_jobs_table(env: str):
    """Create DynamoDB table for job status tracking."""
    
    table = aws.dynamodb.Table(
        f"{env}-jobs-table",
        name=f"code-remote-{env}-jobs",
        billing_mode="PAY_PER_REQUEST",  # Serverless pricing
        hash_key="job_id",
        attributes=[
            {"name": "job_id", "type": "S"},
            {"name": "user_id", "type": "S"},
            {"name": "created_at", "type": "S"},
        ],
        global_secondary_indexes=[
            {
                "name": "user_id-created_at-index",
                "hash_key": "user_id",
                "range_key": "created_at",
                "projection_type": "ALL",
            },
        ],
        ttl={
            "attribute_name": "ttl",
            "enabled": True,
        },
    )
    
    return table
```

### Frontend Changes

```typescript
// frontend/src/hooks/useExecution.ts

interface Job {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: {
    success: boolean;
    stdout?: string;
    stderr?: string;
    error?: string;
    execution_time_ms?: number;
    timed_out: boolean;
  };
}

export function useExecution() {
  const [job, setJob] = useState<Job | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const execute = async (code: string, timeout?: number) => {
    // 1. Submit job
    const response = await api.post('/execute', { code, timeout_seconds: timeout });
    const { job_id } = response.data;
    
    setJob({ job_id, status: 'pending' });
    setIsPolling(true);
    
    // 2. Poll for results
    const pollInterval = setInterval(async () => {
      const statusResponse = await api.get(`/jobs/${job_id}`);
      const updatedJob = statusResponse.data;
      
      setJob(updatedJob);
      
      if (updatedJob.status === 'completed' || updatedJob.status === 'failed') {
        clearInterval(pollInterval);
        setIsPolling(false);
      }
    }, 1000); // Poll every second
    
    // Cleanup on unmount
    return () => clearInterval(pollInterval);
  };

  return { job, isPolling, execute };
}
```

### Event Flow Summary

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                        Async Execution Flow                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  1. User clicks "Run"                                                         │
│     │                                                                         │
│     ▼                                                                         │
│  2. POST /execute                                                             │
│     │  ├─▶ Create job in DynamoDB (status: pending)                          │
│     │  └─▶ Send message to SQS queue                                         │
│     │                                                                         │
│     ▼                                                                         │
│  3. Return { job_id, status: "pending" } immediately (< 100ms)               │
│     │                                                                         │
│     ▼                                                                         │
│  4. Frontend starts polling GET /jobs/{job_id}                               │
│     │                                                                         │
│     │  ┌─────────────────────────────────────────────────────────────────┐   │
│     │  │  Meanwhile, in the background...                                │   │
│     │  │                                                                 │   │
│     │  │  5. SQS triggers Worker Lambda                                  │   │
│     │  │     │                                                           │   │
│     │  │     ▼                                                           │   │
│     │  │  6. Worker updates job status to "running"                      │   │
│     │  │     │                                                           │   │
│     │  │     ▼                                                           │   │
│     │  │  7. Worker executes code (sandbox)                              │   │
│     │  │     │                                                           │   │
│     │  │     ▼                                                           │   │
│     │  │  8. Worker updates job status to "completed" with result        │   │
│     │  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                         │
│     ▼                                                                         │
│  9. Frontend poll receives { status: "completed", result: {...} }            │
│     │                                                                         │
│     ▼                                                                         │
│  10. Display results to user                                                  │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Migration Strategy

Since execution is currently synchronous, we need a migration path:

| Phase | Action |
|-------|--------|
| **10.1** | Deploy DynamoDB table + SQS queue (Pulumi) |
| **10.2** | Deploy worker Lambda with SQS trigger |
| **10.3** | Add new `/execute` (async) + `/jobs/{id}` endpoints |
| **10.4** | Update frontend to use async flow |
| **10.5** | Keep old sync endpoint as `/execute/sync` (deprecated) |
| **10.6** | Remove sync endpoint after verification |

### Cost Estimate

| Component | Monthly Cost (10K executions) |
|-----------|-------------------------------|
| SQS FIFO | ~$0.50 (10K messages) |
| DynamoDB | ~$1.00 (on-demand, with TTL) |
| Worker Lambda | ~$2.00 (10K invocations × 30s avg) |
| CloudWatch | ~$0.30 (alarms) |
| **Total** | **~$4/mo** |

### Future Enhancements

| Enhancement | Description |
|-------------|-------------|
| **WebSockets** | Push results instead of polling (API Gateway WebSocket) |
| **Progress streaming** | Stream stdout in real-time via WebSocket |
| **Priority queues** | Separate queues for free/paid users |
| **Batch execution** | Run multiple code blocks in sequence |
| **Scheduled execution** | Cron-like scheduled jobs |

### Implementation Steps (Phase 10)

| Step | Task | Details |
|------|------|---------|
| 10.1 | Pulumi: SQS FIFO queue + DLQ | With CloudWatch alarm |
| 10.2 | Pulumi: DynamoDB jobs table | With TTL and GSI |
| 10.3 | Worker Lambda | SQS consumer with executor |
| 10.4 | JobService | Submit, get, update_status |
| 10.5 | New API endpoints | POST /execute, GET /jobs/{id}, GET /jobs |
| 10.6 | Frontend: useExecution hook | Submit + poll pattern |
| 10.7 | Frontend: Job status UI | Pending/running/completed states |
| 10.8 | Remove sync execution | Deprecate old endpoint |

**Status:** ✅ COMPLETE (Commit: ec58019)

**Implementation Notes:**
- Stateless design (no DynamoDB jobs table)
- SQS FIFO + Worker Lambda + WebSocket push
- Local dev fallback with FastAPI WebSocket
- Connection status indicator in editor status bar
