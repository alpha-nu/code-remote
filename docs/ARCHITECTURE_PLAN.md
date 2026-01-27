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
