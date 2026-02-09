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
# Edit .env and add your GEMINI_API_KEY for LLM features
```

### Running

```bash
# Start the API server
uvicorn api.main:app --reload --port 8000

# Health check
curl http://localhost:8000/health
```

#### macOS SSL Certificate Fix

On macOS, you may encounter SSL certificate errors when the backend tries to validate Cognito JWT tokens:

```
SSL: CERTIFICATE_VERIFY_FAILED - unable to get local issuer certificate
```

Fix by installing `certifi` and setting the `SSL_CERT_FILE` environment variable:

```bash
# Install certifi in your virtual environment
uv pip install certifi

# Start with SSL certificates configured
SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())") uvicorn api.main:app --reload --port 8000
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov --cov-report=html

# Run specific test file
pytest tests/unit/test_health.py -v

# Run only unit tests
pytest tests/unit/ -v
```

### Linting & Formatting

We use [Ruff](https://github.com/astral-sh/ruff) for Python linting and formatting.

```bash
# Check for linting issues
ruff check .

# Auto-fix issues
ruff check . --fix

# Auto-fix including unsafe fixes
ruff check . --fix --unsafe-fixes

# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```

#### Ruff Configuration

Ruff is configured in `pyproject.toml`:

- **Target:** Python 3.11
- **Line length:** 100 characters
- **Rules enabled:** E (errors), F (pyflakes), I (isort), N (naming), W (warnings), UP (upgrades)

### Pre-commit Hooks

Pre-commit hooks are configured at the repository root. Install with:

```bash
cd ..  # Go to repo root
pip install pre-commit
pre-commit install
```

Hooks run automatically on commit, or manually with:

```bash
pre-commit run --all-files
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with version info |
| `/execute` | POST | Execute Python code in sandbox |
| `/analyze` | POST | Analyze code complexity with Gemini LLM |
| `/analyze/status` | GET | Check if LLM analysis is available |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key for LLM analysis | (required for /analyze) |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000` |
| `DEFAULT_TIMEOUT` | Default code execution timeout (seconds) | `5` |
| `MAX_TIMEOUT` | Maximum allowed timeout (seconds) | `30` |

## Security

The executor enforces strict security:

- **AST validation** before execution
- **Import whitelist** - only safe modules allowed
- **Blocked builtins** - no `eval`, `exec`, `open`, etc.
- **Timeout enforcement** - prevents infinite loops
- **Output capture** - stdout/stderr captured safely
