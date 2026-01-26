# Code Remote

Remote Code Execution Engine: Users write Python code in a web interface, we execute it securely and return results with AI-powered complexity analysis.

## Architecture

- **Frontend:** React + TypeScript + Monaco Editor
- **Backend:** FastAPI (Python 3.11+)
- **Execution:** Sandboxed Python runner with security restrictions
- **Analysis:** Google Gemini LLM for complexity analysis
- **Infrastructure:** AWS (Pulumi IaC) + Kubernetes

## Project Structure

```
code-remote/
├── frontend/          # React + Monaco Editor web app
├── backend/
│   ├── api/           # FastAPI services
│   ├── executor/      # Sandboxed Python runner
│   ├── analyzer/      # Gemini LLM complexity analysis
│   └── common/        # Shared utilities
├── infra/pulumi/      # Infrastructure as Code (planned)
└── kubernetes/        # K8s manifests (planned)
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) for Python package management
- [pre-commit](https://pre-commit.com/) for git hooks

### Setup

```bash
# Clone and setup backend
cd backend
uv venv ../.venv
source ../.venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env  # Add your GEMINI_API_KEY

# Setup frontend
cd ../frontend
npm install

# Install pre-commit hooks (from repo root)
cd ..
pip install pre-commit
pre-commit install
```

### Running

```bash
# Terminal 1: Backend API
cd backend
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend dev server
cd frontend
npm run dev
```

## Development

### Linting & Formatting

We use automated linting via pre-commit hooks. Hooks run automatically on `git commit`.

```bash
# Run all linters manually
pre-commit run --all-files

# Python linting (backend)
cd backend
ruff check .              # Check for issues
ruff check . --fix        # Auto-fix issues
ruff format .             # Format code
ruff format --check .     # Check formatting

# TypeScript/React linting (frontend)
cd frontend
npm run lint              # ESLint check
npm run type-check        # TypeScript type checking
```

### Pre-commit Hooks

The following hooks run automatically on commit:

| Hook | Description |
|------|-------------|
| ruff lint | Python linting and auto-fix |
| ruff format | Python code formatting |
| eslint | TypeScript/React linting |
| typescript check | Type checking |
| trailing-whitespace | Remove trailing whitespace |
| end-of-file-fixer | Ensure files end with newline |
| check-yaml | Validate YAML syntax |
| check-json | Validate JSON syntax |
| detect-private-key | Prevent accidental key commits |

### Testing

```bash
# Backend tests
cd backend
pytest                           # Run all tests
pytest tests/unit/ -v            # Unit tests with verbose
pytest --cov --cov-report=html   # With coverage report

# Frontend (tests coming soon)
cd frontend
npm run type-check
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/execute` | POST | Execute Python code securely |
| `/analyze` | POST | Analyze code complexity with AI |
| `/analyze/status` | GET | Check if LLM is configured |

## Security

The executor sandbox enforces:
- **Allowed imports:** `math`, `json`, `collections`, `itertools`, `functools`, `typing`, `dataclasses`, `datetime`, `re`, `random`, `string`, `decimal`, `fractions`, `statistics`, `heapq`, `bisect`, `copy`, `enum`, `operator`
- **Blocked:** `os`, `subprocess`, `socket`, `sys`, network access, file I/O
- **Timeout:** 30 seconds max execution time

## License

MIT
