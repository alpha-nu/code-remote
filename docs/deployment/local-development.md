# Local Development

This guide covers setting up Code Remote for local development.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| uv | Latest | Python package manager |
| Docker | Latest | Database, full-stack |

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
docker compose up -d

# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# PostgreSQL: localhost:5432
```

### Option 2: Manual Setup

**Terminal 1: Backend**
```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your GEMINI_API_KEY

uvicorn api.main:app --reload --port 8000
```

**Terminal 2: Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Terminal 3: Database**
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_USER=coderemote \
  -e POSTGRES_PASSWORD=coderemote \
  -e POSTGRES_DB=coderemote \
  -p 5432:5432 \
  postgres:16-alpine
```

---

## Docker Compose Services

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    
  frontend:
    build: ./frontend
    ports: ["3000:80"]
    
  api:
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./backend:/app  # Hot reload
```

---

## Environment Variables

### Backend (.env)
```bash
# Required
GEMINI_API_KEY=your-api-key

# Database (for local dev)
DATABASE_URL=postgresql+asyncpg://coderemote:coderemote@localhost:5432/coderemote

# Optional
DEBUG=true
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### Frontend (.env.development)
```bash
VITE_API_URL=http://localhost:8000
```

---

## Database Migrations

```bash
cd backend

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback
alembic downgrade -1
```

---

## Testing

### Backend
```bash
cd backend

# All tests
pytest

# With coverage
pytest --cov --cov-report=html

# Unit tests only
pytest tests/unit/ -v
```

### Frontend
```bash
cd frontend

# Run tests
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage
```

---

## Linting

### Backend
```bash
cd backend

# Check
ruff check .

# Fix
ruff check . --fix

# Format
ruff format .
```

### Frontend
```bash
cd frontend

# Lint
npm run lint

# Type check
npm run type-check
```

---

## Common Tasks

### Reset Database
```bash
docker compose down -v
docker compose up -d postgres
cd backend && alembic upgrade head
```

### Rebuild Containers
```bash
docker compose build --no-cache
docker compose up -d
```

### View Logs
```bash
docker compose logs -f api
docker compose logs -f frontend
```

---

## IDE Setup

### VS Code Extensions
- Python
- Pylance
- ESLint
- Prettier
- Docker

### Settings
```json
{
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process
lsof -i :8000
# Kill it
kill -9 <PID>
```

### Database Connection Failed
```bash
# Check postgres is running
docker ps | grep postgres
# Restart if needed
docker compose restart postgres
```

### Module Not Found
```bash
# Reinstall dependencies
cd backend
uv pip install -e ".[dev]"
```

---

## Architecture for Local Dev

```mermaid
flowchart LR
    Browser --> Frontend[Frontend :3000]
    Frontend --> API[API :8000]
    API --> DB[(PostgreSQL :5432)]
    API --> Gemini[Gemini API]
```

---

## Related Documents

- [Backend Architecture](../architecture/backend.md)
- [Frontend Architecture](../architecture/frontend.md)
- [CI/CD Pipeline](ci-cd.md)
