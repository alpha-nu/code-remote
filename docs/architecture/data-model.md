# Data Model

## Overview

Code Remote uses a dual-database architecture:

| Store | Purpose | Status |
|-------|---------|--------|
| **Aurora PostgreSQL** | User data, snippets, executions (source of truth) | ✅ Deployed |
| **Neo4j AuraDB** | Vector embeddings, semantic search | ✅ Deployed |

Data flows from PostgreSQL → Neo4j via SQS-based CDC (Change Data Capture).

> **Note:** DynamoDB is **not used**. All persistent data is in PostgreSQL.

---

## PostgreSQL Schema

### Users Table

Synced from Cognito on first API interaction.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255),
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_cognito_sub ON users(cognito_sub);
CREATE INDEX idx_users_email ON users(email);
```

### Snippets Table

Code snippets with analysis results.

```sql
CREATE TABLE snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    title VARCHAR(255),
    language VARCHAR(50) NOT NULL DEFAULT 'python',
    code TEXT NOT NULL,
    description TEXT,
    
    -- Execution tracking
    last_execution_at TIMESTAMPTZ,
    execution_count INTEGER NOT NULL DEFAULT 0,
    
    -- User organization
    is_starred BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- LLM complexity analysis results
    time_complexity VARCHAR(50),
    space_complexity VARCHAR(50),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_snippets_user_id ON snippets(user_id);
CREATE INDEX ix_snippets_user_starred_updated 
    ON snippets(user_id, is_starred DESC, updated_at DESC);
```

---

## SQLAlchemy Models

### User Model

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    snippets: Mapped[list["Snippet"]] = relationship(back_populates="user")
```

### Snippet Model

```python
class Snippet(Base, TimestampMixin):
    __tablename__ = "snippets"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(50), default="python")
    code: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    last_execution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_count: Mapped[int] = mapped_column(default=0)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    time_complexity: Mapped[str | None] = mapped_column(String(50))
    space_complexity: Mapped[str | None] = mapped_column(String(50))
    
    user: Mapped["User"] = relationship(back_populates="snippets")
```

---

## Neo4j Graph Schema

Vector search and semantic relationships stored in Neo4j AuraDB.

### Node Types

```cypher
// User node (synced from PostgreSQL)
(:User {
    id: String,           // UUID as string
    cognito_sub: String,
    email: String
})

// Snippet node with vector embedding
(:Snippet {
    id: String,           // UUID as string
    title: String,
    language: String,
    code: String,
    embedding: [Float]    // 768-dim Gemini text-embedding-004
})
```

### Relationships

```cypher
(:User)-[:OWNS]->(:Snippet)
(:Snippet)-[:SIMILAR_TO {score: Float}]->(:Snippet)
```

### Vector Index

```cypher
CREATE VECTOR INDEX snippet_embeddings FOR (s:Snippet) ON s.embedding
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 768,
        `vector.similarity_function`: 'cosine'
    }
}
```

---

## Data Sync (PostgreSQL → Neo4j)

When snippets are created/updated in PostgreSQL, a sync process updates Neo4j:

```
PostgreSQL ──► SQS FIFO Queue ──► Sync Worker Lambda ──► Neo4j
                                         │
                                         └──► Gemini API (embeddings)
```

### Sync Queue Messages

```json
{
    "action": "upsert" | "delete",
    "snippet_id": "uuid",
    "user_id": "uuid"
}
```

### Sync Worker Process

1. Receive message from `code-remote-{env}-snippet-sync.fifo`
2. Fetch snippet from PostgreSQL
3. Generate embedding via Gemini `text-embedding-004`
4. Upsert/delete node in Neo4j
5. Update similarity relationships

---

## Pydantic Schemas

### Snippet Schemas

```python
class SnippetCreate(BaseModel):
    title: str | None = None
    code: str
    language: str = "python"
    description: str | None = None

class SnippetResponse(BaseModel):
    id: UUID
    title: str | None
    code: str
    language: str
    description: str | None
    is_starred: bool
    execution_count: int
    time_complexity: str | None
    space_complexity: str | None
    created_at: datetime
    updated_at: datetime

class SnippetAnalysis(BaseModel):
    time_complexity: str
    space_complexity: str
    explanation: str
```

### Execution Schemas

```python
class ExecutionRequest(BaseModel):
    code: str
    timeout_seconds: int = 30

class ExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    error_type: str | None = None
    execution_time_ms: float | None = None
    timed_out: bool = False
```

---

## WebSocket Messages

### Client → Server

```typescript
{ "action": "subscribe", "job_id": "uuid" }
{ "action": "unsubscribe", "job_id": "uuid" }
{ "action": "ping" }
```

### Server → Client

```typescript
// Job completed
{
    "type": "job.result",
    "job_id": "uuid",
    "status": "completed" | "failed",
    "result": {
        "success": boolean,
        "stdout": string,
        "stderr": string,
        "error": string | null,
        "execution_time_ms": number,
        "timed_out": boolean
    }
}

// Heartbeat
{ "type": "pong" }
```

---

## SQS Message Formats

### Execution Queue

```json
{
    "job_id": "uuid",
    "user_id": "cognito-sub",
    "code": "print('hello')",
    "timeout_seconds": 30
}
```

- Queue: `code-remote-{env}-execution.fifo`
- MessageGroupId: `user_id`
- MessageDeduplicationId: `job_id`

### Snippet Sync Queue

```json
{
    "action": "upsert",
    "snippet_id": "uuid",
    "user_id": "uuid"
}
```

- Queue: `code-remote-{env}-snippet-sync.fifo`
- MessageGroupId: `user_id`
- MessageDeduplicationId: `{action}:{snippet_id}:{timestamp}`
