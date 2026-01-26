# Code Remote Backend

Backend services for the Remote Code Execution Engine.

## Components

- **api/** - FastAPI web service
- **executor/** - Sandboxed Python code executor
- **analyzer/** - LLM-powered code complexity analysis
- **common/** - Shared utilities and configuration

## Development

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for package management

### Setup

```bash
# Create virtual environment and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
```

### Running

```bash
# Start the API server
uvicorn api.main:app --reload --port 8000

# Health check
curl http://localhost:8000/health
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/unit/test_health.py -v
```

### Linting

```bash
# Check code style
ruff check .

# Fix auto-fixable issues
ruff check . --fix
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/execute` | POST | Execute Python code (coming in Phase 2) |
| `/analyze` | POST | Analyze code complexity (coming in Phase 5) |
