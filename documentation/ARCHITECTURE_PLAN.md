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

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Project scaffolding
- [ ] Basic FastAPI service with health endpoint
- [ ] Docker setup for local development
- [ ] Pulumi project initialization (AWS)
- [ ] CI pipeline setup

### Phase 2: Core Execution (Week 3-4)
- [ ] Sandboxed Python executor
- [ ] Queue integration (Redis Streams)
- [ ] Basic API endpoints (submit, status, result)
- [ ] Unit and integration tests

### Phase 3: Frontend (Week 5)
- [ ] Monaco Editor integration
- [ ] WebSocket for real-time output
- [ ] Basic UI (submit, view results)

### Phase 4: LLM Integration (Week 6)
- [ ] Complexity analysis service
- [ ] LLM provider abstraction
- [ ] Prompt engineering for accurate analysis

### Phase 5: Security Hardening (Week 7)
- [ ] gVisor integration
- [ ] Network policies
- [ ] Security scanning in CI
- [ ] Penetration testing

### Phase 6: Production Readiness (Week 8)
- [ ] Kubernetes deployment manifests
- [ ] Monitoring and alerting
- [ ] Documentation
- [ ] Load testing

---

## Decisions Made ✅

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | **Option 3: Hybrid** | Balance of managed services + execution control |
| Frontend | **React + Monaco Editor** | Industry standard, VS Code's editor |
| Authentication | **AWS Cognito** | Native AWS integration, managed service |
| LLM Provider | **Google Gemini** | Strong code understanding, competitive pricing |
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

`.github/copilot-instructions.md` has been generated.
