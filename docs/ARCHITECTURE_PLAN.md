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

## Phase 9: Persistence & Code Snippets (PLANNING)

**Goal:** Allow users to save, organize, and search code snippets with AI-powered semantic search

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

| Step | Task | Details |
|------|------|---------|
| 9.1 | Pulumi: Aurora Serverless v2 | VPC, subnet groups, security groups |
| 9.2 | Database migrations | Alembic setup, initial schema |
| 9.3 | SQLAlchemy models | User, Snippet with pgvector |
| 9.4 | Snippet CRUD endpoints | POST/GET/PUT/DELETE /snippets |
| 9.5 | Embedding service | Generate embeddings on save |
| 9.6 | Search endpoint | /snippets/search with vector + filters |
| 9.7 | Frontend: Snippets UI | Save dialog, library view, search |

**Status:** PLANNING - Awaiting approval
