# Phase 9: Data Persistence Layer

## Overview

Phase 9 introduces a PostgreSQL-based persistence layer for Code Remote, enabling users to save, retrieve, and manage their code snippets across sessions. This phase is split into two sub-phases:

- **Phase 9.1**: PostgreSQL Foundation (this document)
- **Phase 9.2**: Vector Search with pgvector (planned)

---

## Phase 9.1: PostgreSQL Foundation

### Goals

1. Deploy Aurora PostgreSQL Serverless v2 for cost-effective, scalable storage
2. Implement SQLAlchemy async models for User and Snippet entities
3. Create CRUD API endpoints for snippet management
4. Sync Cognito users to PostgreSQL on first API interaction

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│                    (React + Monaco Editor)                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP + JWT
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway                                 │
│                    (HTTP API v2)                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Lambda Function                             │
│                      (FastAPI + Mangum)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  /snippets router                                        │    │
│  │    ├── POST   /snippets      → SnippetService.create()  │    │
│  │    ├── GET    /snippets      → SnippetService.list()    │    │
│  │    ├── GET    /snippets/{id} → SnippetService.get()     │    │
│  │    ├── PUT    /snippets/{id} → SnippetService.update()  │    │
│  │    └── DELETE /snippets/{id} → SnippetService.delete()  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  get_db_user dependency (on every authenticated request) │    │
│  │    └── UserService.get_or_create_from_cognito()         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────┘
                          │ asyncpg (PostgreSQL async driver)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              Aurora PostgreSQL Serverless v2                     │
│                  (Private Subnet, VPC)                           │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │   users table    │    │        snippets table            │   │
│  │  ───────────────  │    │  ─────────────────────────────── │   │
│  │  id (UUID, PK)   │◄───│  user_id (UUID, FK)              │   │
│  │  cognito_sub     │    │  id (UUID, PK)                   │   │
│  │  email           │    │  title, language, code           │   │
│  │  username        │    │  description                     │   │
│  │  last_login      │    │  execution_count                 │   │
│  │  created_at      │    │  last_execution_at               │   │
│  │  updated_at      │    │  created_at, updated_at          │   │
│  └──────────────────┘    └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## User Sync Service - Deep Dive

### The Problem

Code Remote uses AWS Cognito for authentication, but Cognito only provides identity—it doesn't store application-specific data. We need:

1. A database user record with a UUID primary key for foreign key relationships
2. The ability to track user-specific data (snippets, execution history)
3. Automatic user provisioning without manual registration

### The Solution: Lazy User Sync

The `UserService` implements a "sync on first access" pattern:

```python
# backend/api/services/user_service.py

class UserService:
    async def get_or_create_from_cognito(
        self,
        cognito_sub: str,    # From JWT 'sub' claim
        email: str,          # From JWT 'email' claim
        username: str | None # From JWT 'cognito:username' claim
    ) -> User:
        # 1. Try to find existing user by Cognito sub
        user = await self.get_by_cognito_sub(cognito_sub)
        
        if user is None:
            # 2. First API call - create database record
            user = User(
                cognito_sub=cognito_sub,
                email=email,
                username=username or email.split("@")[0],
            )
            self.db.add(user)
        else:
            # 3. Update email if changed in Cognito
            if user.email != email:
                user.email = email
        
        # 4. Always update last_login timestamp
        user.last_login = datetime.now(UTC)
        
        await self.db.flush()
        await self.db.refresh(user)
        return user
```

### How It's Triggered

The sync happens via a FastAPI dependency injected into every snippets endpoint:

```python
# backend/api/routers/snippets.py

async def get_db_user(
    cognito_user: CognitoUser = Depends(get_current_user),  # JWT validated
    db: AsyncSession = Depends(get_db),                      # DB session
) -> User:
    """Get or create database user from Cognito claims."""
    user_service = UserService(db)
    return await user_service.get_or_create_from_cognito(
        cognito_sub=cognito_user.id,     # Cognito 'sub' is in .id
        email=cognito_user.email or "",
        username=cognito_user.username,
    )

@router.post("", response_model=SnippetResponse)
async def create_snippet(
    request: SnippetCreate,
    user: User = Depends(get_db_user),  # ← Triggers user sync
    db: AsyncSession = Depends(get_db),
):
    ...
```

### Request Flow Diagram

```
User makes authenticated request to POST /snippets
                    │
                    ▼
        ┌───────────────────────┐
        │ get_current_user()    │  Validates JWT, extracts claims
        │ (auth dependency)     │  Returns CognitoUser model
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ get_db_user()         │  Converts Cognito → Database user
        │ (snippets dependency) │
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐      ┌───────────────┐
│ User exists   │      │ User doesn't  │
│ in database   │      │ exist yet     │
└───────┬───────┘      └───────┬───────┘
        │                       │
        ▼                       ▼
┌───────────────┐      ┌───────────────┐
│ Update        │      │ INSERT new    │
│ last_login    │      │ user record   │
└───────┬───────┘      └───────┬───────┘
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Return User model     │  Has UUID for FK relationships
        │ with database ID      │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ create_snippet()      │  Uses user.id for snippet.user_id
        │ endpoint handler      │
        └───────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| UUID primary key | Avoids exposing Cognito sub externally, provides standard FK type |
| Sync on every request | Catches email changes, maintains accurate last_login |
| cognito_sub as unique key | Immutable identifier that survives email changes |
| Username from email | Sensible default when Cognito username not available |

### Edge Cases Handled

1. **Email change in Cognito**: Detected and updated on next API call
2. **No username in token**: Falls back to email prefix
3. **Concurrent first requests**: Database unique constraint on cognito_sub prevents duplicates
4. **User deletion in Cognito**: Orphan DB records remain (manual cleanup needed)

---

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(255),
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_cognito_sub ON users(cognito_sub);
CREATE INDEX ix_users_email ON users(email);
```

### Snippets Table

```sql
CREATE TABLE snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    language VARCHAR(50) NOT NULL DEFAULT 'python',
    code TEXT NOT NULL,
    description TEXT,
    execution_count INTEGER NOT NULL DEFAULT 0,
    last_execution_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_snippets_user_id ON snippets(user_id);
```

---

## Infrastructure

### Aurora Serverless v2 Configuration

```python
# infra/pulumi/components/database.py

serverlessv2_scaling_configuration=ClusterServerlessv2ScalingConfigurationArgs(
    min_capacity=0.5,   # 0.5 ACU (~$43/month at full usage)
    max_capacity=4.0,   # Dev: 4 ACU, Prod: 16 ACU
)
```

**Why Serverless v2?**
- Scales to near-zero when idle (cost optimization)
- No cold starts like Serverless v1
- Automatic scaling for traffic spikes
- Pay-per-second billing

### Security Configuration

1. **Network isolation**: Aurora in private subnets only
2. **Security groups**: Only Lambda can connect (port 5432)
3. **Encryption**: Storage encrypted at rest
4. **Secrets**: Credentials in AWS Secrets Manager

### Lambda Connection Pooling

```python
# backend/api/services/database.py

_engine = create_async_engine(
    url,
    pool_size=1,        # Lambda = 1 concurrent request
    max_overflow=0,     # No extra connections
    pool_pre_ping=True, # Verify connection before use
)
```

---

## Migrations

Managed via Alembic with async support:

```bash
# Create new migration
cd backend
alembic revision --autogenerate -m "Add new_field to snippets"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

Initial migration: `backend/alembic/versions/0001_initial_schema.py`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/snippets` | Create snippet |
| GET | `/snippets` | List user's snippets (paginated) |
| GET | `/snippets/{id}` | Get single snippet |
| PUT | `/snippets/{id}` | Update snippet |
| DELETE | `/snippets/{id}` | Delete snippet |

All endpoints require authentication and only operate on the authenticated user's snippets.

---

## Testing

35 new unit tests added:

- `test_snippet_service.py` - 13 tests for SnippetService CRUD
- `test_user_service.py` - 10 tests for UserService sync logic
- `test_snippets.py` - 12 tests for API endpoints

Run tests:
```bash
cd backend
pytest tests/unit/ -v
```

---

## Phase 9.2 Preview: Vector Search

Planned additions:
- pgvector extension for embedding storage
- Code embeddings via Gemini API
- Semantic search across snippets
- Similar code suggestions

---

## Files Added/Modified

### New Files
- `infra/pulumi/components/database.py` - Aurora Pulumi component
- `backend/alembic.ini` - Alembic configuration
- `backend/alembic/env.py` - Async migration environment
- `backend/alembic/versions/0001_initial_schema.py` - Initial migration
- `backend/api/models/base.py` - SQLAlchemy base and mixins
- `backend/api/models/user.py` - User model
- `backend/api/models/snippet.py` - Snippet model
- `backend/api/services/database.py` - Connection management
- `backend/api/services/user_service.py` - Cognito sync service
- `backend/api/services/snippet_service.py` - Snippet CRUD service
- `backend/api/routers/snippets.py` - CRUD endpoints
- `backend/api/schemas/snippet.py` - Pydantic schemas

---

## Backend Enhancement Requests (from UI Team)

### 1. Add `is_starred` Field to Snippets

**Requirement:** Users should be able to star/favorite snippets for quick access.

**Schema Changes:**
```sql
ALTER TABLE snippets ADD COLUMN is_starred BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX ix_snippets_user_id_starred ON snippets(user_id, is_starred) WHERE is_starred = true;
```

**API Updates:**
- Add `is_starred: bool` field to `SnippetResponse`, `SnippetCreate`, `SnippetUpdate` schemas
- Support filtering starred snippets: `GET /snippets?starred=true`
- Add dedicated toggle endpoint (optional): `POST /snippets/{id}/star`

**UI Use Case:** Display starred snippets at top of list, show star icon in upper-right wedge.

---

### 2. Include Complexity Analysis in Snippet Response

**Requirement:** Display time/space complexity badges on each snippet without separate API calls.

**Schema Changes:**
```sql
ALTER TABLE snippets ADD COLUMN time_complexity VARCHAR(100);
ALTER TABLE snippets ADD COLUMN space_complexity VARCHAR(100);
ALTER TABLE snippets ADD COLUMN complexity_analyzed_at TIMESTAMP WITH TIME ZONE;
```

**API Updates:**
- Add optional fields to `SnippetResponse`:
  ```python
  time_complexity: str | None = None
  space_complexity: str | None = None
  complexity_analyzed_at: datetime | None = None
  ```
- Auto-analyze complexity on snippet creation (async background task)
- Re-analyze when code is updated
- Expose manual re-analysis: `POST /snippets/{id}/analyze`

**Implementation Notes:**
- Cache analysis results in database to avoid repeated LLM calls
- Update `complexity_analyzed_at` timestamp on each analysis
- Return `null` values if not yet analyzed

**UI Use Case:** Show complexity badges directly in snippet list without fetching from `/analyze` endpoint.

### Modified Files
- `infra/pulumi/__main__.py` - Added database component
- `infra/pulumi/components/serverless_api.py` - Lambda→DB connectivity
- `backend/pyproject.toml` - Added SQLAlchemy, asyncpg, alembic
- `backend/api/main.py` - Registered snippets router
- `backend/common/config.py` - Added database_secret_arn setting
