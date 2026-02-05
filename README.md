<div align="center">
<img src="frontend/public/logo-180.png" width="180" alt="Code Remote Logo">

<h1>Code Remote</h1>

**Secure, Cloud-Native Remote Code Execution Platform**
</div>

---

A secure, cloud-native remote code execution platform that enables users to write Python code in a browser-based editor, execute it in an isolated sandbox, and receive AI-powered complexity analysis.

## What is Code Remote?

Code Remote provides a safe environment for running untrusted Python code. Whether you're building an educational platform, a coding interview tool, or an online IDE, Code Remote handles the hard parts: security isolation, resource limits, and intelligent code analysis.

**Key Use Cases:**
- Online coding education and tutorials
- Technical interview platforms
- Algorithm visualization and testing
- Safe code playground for experimentation

## Features

| Feature | Description |
|---------|-------------|
| **Monaco Editor** | VS Code's editor with Python syntax highlighting and autocomplete |
| **Secure Execution** | Sandboxed Python runner with import restrictions and resource limits |
| **AI Analysis** | Google Gemini-powered time/space complexity analysis |
| **Real-Time Results** | WebSocket-based live execution updates |
| **Authentication** | AWS Cognito user management |
| **Cloud Native** | Pulumi IaC, GitHub Actions CI/CD, AWS infrastructure |

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     Frontend     │────▶│   API Gateway    │────▶│  Lambda/FastAPI  │
│  React + Monaco  │     │   (HTTP + WS)    │     │                  │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                              ┌─────────────────┬──────────┴──────────┐
                              ▼                 ▼                      ▼
                    ┌──────────────┐   ┌──────────────┐      ┌──────────────┐
                    │   Executor   │   │   Analyzer   │      │   Cognito    │
                    │  (Sandbox)   │   │   (Gemini)   │      │    (Auth)    │
                    └──────────────┘   └──────────────┘      └──────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- Docker (optional, for containerized development)

### Local Setup

**1. Backend**

```bash
cd backend
uv venv ../.venv
source ../.venv/bin/activate
uv pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

**2. Frontend**

```bash
cd frontend
npm install
```

**3. Run the Application**

```bash
# Terminal 1: Backend API (port 8000)
cd backend
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend dev server (port 5173)
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

---

## Running Scripts

### Testing

```bash
# Run all backend tests
cd backend
pytest

# Run with coverage report
pytest --cov --cov-report=html

# Run specific test categories
pytest tests/unit/ -v           # Unit tests
pytest tests/integration/ -v    # Integration tests
pytest tests/smoke/ -v          # Smoke tests

# Frontend type checking
cd frontend
npm run type-check
```

### Linting & Formatting

```bash
# Run all linters via pre-commit
pre-commit run --all-files

# Python (backend)
cd backend
ruff check . --fix    # Lint and auto-fix
ruff format .         # Format code

# TypeScript (frontend)
cd frontend
npm run lint
```

### Docker

```bash
# Run full stack with Docker Compose
docker-compose up -d

# Build backend container only
docker build -t code-remote-api -f backend/Dockerfile backend/

# Build Lambda-compatible container
docker build -t code-remote-lambda -f backend/Dockerfile.lambda backend/

# Stop all containers
docker-compose down
```

### Infrastructure (Pulumi)

```bash
cd infra/pulumi

# Preview changes
pulumi preview --stack dev

# Deploy to AWS
pulumi up --stack dev --yes

# Get stack outputs (API URL, etc.)
pulumi stack output

# Destroy infrastructure
pulumi destroy --stack dev
```

---

## Project Structure

```
code-remote/
├── frontend/              # React + Monaco Editor
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── hooks/         # React hooks
│   │   ├── store/         # Zustand state management
│   │   └── api/           # API client
│   └── package.json
│
├── backend/
│   ├── api/               # FastAPI application
│   │   ├── routers/       # HTTP endpoints
│   │   ├── schemas/       # Pydantic models
│   │   ├── services/      # Business logic
│   │   └── auth/          # Cognito integration
│   ├── executor/          # Sandboxed Python runner
│   ├── analyzer/          # Gemini LLM integration
│   └── tests/             # Unit, integration, smoke tests
│
├── infra/pulumi/          # Infrastructure as Code
│   ├── components/        # Reusable Pulumi components
│   └── Pulumi.*.yaml      # Environment configs
│
└── docs/                  # Architecture documentation
    ├── architecture/      # System design docs
    └── phases/            # Implementation phases
```

---

## Security

The execution sandbox enforces multiple security layers:

| Layer | Protection |
|-------|------------|
| **Import Whitelist** | Only safe modules: `math`, `json`, `collections`, `itertools`, `functools`, `typing`, `dataclasses`, `datetime`, `re`, `random`, `string`, `decimal`, `fractions`, `statistics`, `heapq`, `bisect`, `copy`, `enum`, `operator` |
| **Restricted Builtins** | Blocked: `eval`, `exec`, `open`, `__import__`, `compile`, `globals`, `locals` |
| **AST Validation** | Dangerous patterns detected at parse time |
| **Resource Limits** | 256MB memory, 30s timeout, no network access |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/execute` | POST | Execute Python code (returns job_id) |
| `/execute/jobs/{id}` | GET | Get job status and result |
| `/analyze` | POST | AI complexity analysis |
| `/analyze/status` | GET | Check LLM configuration |

---

## Documentation

For detailed architecture and design decisions:

| Document | Description |
|----------|-------------|
| [Architecture Plan](docs/architecture-plan.md) | High-level system overview |
| [System Overview](docs/architecture/overview.md) | Detailed component design |
| [Security Model](docs/architecture/security.md) | Sandbox security layers |
| [Data Model](docs/architecture/data-model.md) | Database schemas and API contracts |
| [Infrastructure](docs/architecture/infrastructure.md) | AWS/Pulumi resource details |
| [Phase 10: Real-Time](docs/phases/phase-10-realtime.md) | WebSocket async execution |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `AWS_REGION` | No | AWS region (default: us-east-1) |
| `COGNITO_USER_POOL_ID` | Prod | Cognito user pool ID |
| `COGNITO_CLIENT_ID` | Prod | Cognito app client ID |
| `ENVIRONMENT` | No | dev / staging / prod |

---

## Contributing

1. Install pre-commit hooks: `pre-commit install`
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and ensure tests pass: `pytest`
4. Commit (hooks run automatically)
5. Push and create a PR

## License

MIT
