# Phase 9.2: Neo4j Semantic Search & Knowledge Graph

## Overview

Phase 9.2 introduces Neo4j as the semantic search and knowledge graph layer for Code Remote. This phase combines the originally planned 9.2 (Neo4j sync) and 9.3 (vector search) into a unified implementation.

**Key Goals:**
1. Enable semantic search across snippets ("find my quadratic functions")
2. Store code complexity analysis results in a queryable graph
3. Build relationships between snippets based on similarity
4. Implement queue-based CDC for PostgreSQL → Neo4j synchronization

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              User Creates/Updates Snippet                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API Lambda (FastAPI)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  POST /snippets or PUT /snippets/{id}                                   │    │
│  │    1. Save to PostgreSQL (source of truth) ✅                           │    │
│  │    2. Enqueue CDC event to SQS                                          │    │
│  │    3. Return response immediately                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SQS FIFO Queue (snippet-sync.fifo)                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Message: {                                                             │    │
│  │    "event_type": "snippet.created" | "snippet.updated" | "snippet.deleted",  │
│  │    "snippet_id": "uuid",                                                │    │
│  │    "user_id": "uuid",                                                   │    │
│  │    "timestamp": "ISO8601"                                               │    │
│  │  }                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Sync Worker Lambda                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  On snippet.created / snippet.updated:                                  │    │
│  │    1. Fetch snippet from PostgreSQL                                     │    │
│  │    2. Run complexity analysis (Gemini LLM) → time/space complexity      │    │
│  │    3. Generate embedding (Gemini) from: code + title + description      │    │
│  │    4. Upsert Snippet node in Neo4j with embedding + complexities        │    │
│  │    5. Create/update OWNED_BY relationship to User node                  │    │
│  │                                                                         │    │
│  │  On snippet.deleted:                                                    │    │
│  │    1. Delete Snippet node from Neo4j (cascades relationships)           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
┌────────────────────────┐  ┌────────────────────┐  ┌────────────────────────────┐
│   Gemini API           │  │   PostgreSQL       │  │   Neo4j AuraDB             │
│   (Embeddings +        │  │   (Source of Truth)│  │   (Semantic Search +       │
│    Analysis)           │  │                    │  │    Knowledge Graph)        │
└────────────────────────┘  └────────────────────┘  └────────────────────────────┘
```

---

## Data Flow: Snippet Creation

```
┌──────────┐    POST /snippets     ┌─────────────┐
│  User    │──────────────────────▶│  API Lambda │
│  (UI)    │                       │             │
└──────────┘                       └──────┬──────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
            │ 1. Validate  │      │ 2. Save to   │      │ 3. Enqueue   │
            │    request   │      │    PostgreSQL│      │    CDC event │
            └──────────────┘      └──────────────┘      └──────────────┘
                                          │                     │
                                          ▼                     │
                                  ┌──────────────┐              │
                                  │ 4. Return    │              │
                                  │    201 + ID  │              │
                                  └──────────────┘              │
                                                                │
            ┌───────────────────────────────────────────────────┘
            ▼
    ┌──────────────┐
    │  SQS Queue   │
    │  (FIFO)      │
    └──────┬───────┘
           │ (async, ~seconds later)
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    Sync Worker Lambda                         │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ 5. Fetch snippet from PostgreSQL                       │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                          │                                    │
    │                          ▼                                    │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ 6. Analyze complexity (Gemini LLM)                     │  │
    │  │    Input: code                                         │  │
    │  │    Output: { time_complexity: "O(n)", space: "O(1)" }  │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                          │                                    │
    │                          ▼                                    │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ 7. Generate embedding (Gemini text-embedding model)    │  │
    │  │    Input: f"{title}\n{description}\n{code}"            │  │
    │  │    Output: float[768] vector                           │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                          │                                    │
    │                          ▼                                    │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ 8. Upsert to Neo4j                                     │  │
    │  │    - Create/update Snippet node                        │  │
    │  │    - Set embedding vector property                     │  │
    │  │    - Set complexity properties                         │  │
    │  │    - Ensure OWNED_BY → User relationship               │  │
    │  └────────────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

---

## Neo4j Graph Schema

### Design Philosophy

The schema uses **nodes for categorical data** (language, complexity) rather than properties. This enables:
- Clean Cypher pattern matching instead of string comparisons
- Easy aggregation ("how many O(n²) snippets do I have?")
- Natural graph traversals for complex queries

### Node Types

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                NODE: User                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Properties:                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  id:           UUID (from PostgreSQL users.id)                          │    │
│  │  cognito_sub:  String (Cognito subject identifier)                      │    │
│  │  email:        String                                                   │    │
│  │  username:     String                                                   │    │
│  │  synced_at:    DateTime (last sync timestamp)                           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  Constraints: UNIQUE on id                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                               NODE: Snippet                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Properties:                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  id:               UUID (from PostgreSQL snippets.id)                   │    │
│  │  title:            String                                               │    │
│  │  description:      String (nullable)                                    │    │
│  │  code:             String (full code for search context)                │    │
│  │  complexity_explanation: String (LLM explanation)                       │    │
│  │                                                                         │    │
│  │  # Vector Embedding (for semantic search)                               │    │
│  │  embedding:        List<Float> [768 dimensions]                         │    │
│  │                                                                         │    │
│  │  # Metadata                                                             │    │
│  │  created_at:       DateTime                                             │    │
│  │  updated_at:       DateTime                                             │    │
│  │  synced_at:        DateTime (last sync from PostgreSQL)                 │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  Constraints: UNIQUE on id                                                       │
│  Indexes: VECTOR INDEX on embedding (cosine similarity)                          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                               NODE: Language                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Properties:                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  name:         String ("python", "javascript", "typescript", etc.)      │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  Constraints: UNIQUE on name                                                     │
│  Note: Pre-populated with supported languages, ~10-20 nodes total                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                               NODE: Complexity                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Properties:                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  notation:     String ("O(1)", "O(log n)", "O(n)", "O(n²)", etc.)      │    │
│  │  name:         String ("constant", "logarithmic", "linear", etc.)       │    │
│  │  rank:         Integer (for sorting: 1=O(1), 2=O(log n), 3=O(n), ...)  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  Constraints: UNIQUE on notation                                                 │
│  Note: Pre-populated with common complexities, ~10-15 nodes total                │
│                                                                                  │
│  Pre-populated values:                                                           │
│  ┌────────────┬───────────────┬──────┐                                          │
│  │ notation   │ name          │ rank │                                          │
│  ├────────────┼───────────────┼──────┤                                          │
│  │ O(1)       │ constant      │ 1    │                                          │
│  │ O(log n)   │ logarithmic   │ 2    │                                          │
│  │ O(n)       │ linear        │ 3    │                                          │
│  │ O(n log n) │ linearithmic  │ 4    │                                          │
│  │ O(n²)      │ quadratic     │ 5    │                                          │
│  │ O(n³)      │ cubic         │ 6    │                                          │
│  │ O(2^n)     │ exponential   │ 7    │                                          │
│  │ O(n!)      │ factorial     │ 8    │                                          │
│  └────────────┴───────────────┴──────┘                                          │
└─────────────────────────────────────────────────────────────────────────────────┘

```

### Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              RELATIONSHIPS                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  (Snippet)-[:OWNED_BY]->(User)                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Cardinality: Each Snippet has exactly one OWNED_BY                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  (Snippet)-[:WRITTEN_IN]->(Language)                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Cardinality: Each Snippet has exactly one WRITTEN_IN                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  (Snippet)-[:HAS_TIME_COMPLEXITY]->(Complexity)                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Cardinality: Each Snippet has exactly one HAS_TIME_COMPLEXITY          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  (Snippet)-[:HAS_SPACE_COMPLEXITY]->(Complexity)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Cardinality: Each Snippet has exactly one HAS_SPACE_COMPLEXITY         │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Visual Schema

```
                                 ┌──────────────┐
                                 │   Language   │
                                 │  ──────────  │
                                 │  name        │
                                 └──────┬───────┘
                                        │
                                        │ WRITTEN_IN
                                        │
┌──────────────┐                 ┌──────┴───────┐                 ┌──────────────┐
│    User      │                 │   Snippet    │                 │  Complexity  │
│  ──────────  │◀───OWNED_BY─────│  ──────────  │───HAS_TIME_────▶│  ──────────  │
│  id          │                 │  id          │   COMPLEXITY    │  notation    │
│  email       │                 │  title       │                 │  name        │
│  username    │                 │  code        │───HAS_SPACE────▶│  rank        │
└──────────────┘                 │  embedding[] │   COMPLEXITY    └──────────────┘
                                 │  description │
                                 └──────────────┘
```

---

## CDC Queue Message Schema

```python
# Message sent to SQS when snippet changes
class SnippetCDCEvent(BaseModel):
    event_type: Literal["snippet.created", "snippet.updated", "snippet.deleted"]
    snippet_id: UUID
    user_id: UUID
    timestamp: datetime
    
    # Optional: include data to avoid re-fetch for creates
    # (but re-fetch is safer for updates to ensure consistency)
    
# Example messages:

# Create
{
    "event_type": "snippet.created",
    "snippet_id": "123e4567-e89b-12d3-a456-426614174000",
    "user_id": "987fcdeb-51a2-3c4d-e567-890123456789",
    "timestamp": "2026-02-04T10:30:00Z"
}

# Update
{
    "event_type": "snippet.updated",
    "snippet_id": "123e4567-e89b-12d3-a456-426614174000",
    "user_id": "987fcdeb-51a2-3c4d-e567-890123456789",
    "timestamp": "2026-02-04T10:35:00Z"
}

# Delete
{
    "event_type": "snippet.deleted",
    "snippet_id": "123e4567-e89b-12d3-a456-426614174000",
    "user_id": "987fcdeb-51a2-3c4d-e567-890123456789",
    "timestamp": "2026-02-04T10:40:00Z"
}
```

---

## Search Strategy: Unified Text-to-Cypher

### Overview

All search queries go through a **unified LLM-powered Text-to-Cypher** pipeline. The LLM generates Cypher queries that can combine graph traversal AND vector search in a single query. If the LLM fails or returns no results, we fall back to pure semantic search.

```
┌────────────────────────────────────────────────────────────────────────────┐
│         User Query: "find my worst performing sorting algorithms"           │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│              1. ALWAYS Generate Query Embedding First                       │
│                 (cheap ~50ms, needed for fallback anyway)                   │
│                 $query_embedding = embed("find my worst...")                │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│              2. LLM Generates Cypher (with schema context)                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  CALL db.index.vector.queryNodes('snippet_embedding', 30,            │  │
│  │       $query_embedding) YIELD node AS s, score                       │  │
│  │  MATCH (s)-[:HAS_TIME_COMPLEXITY]->(c:Complexity)                    │  │
│  │  MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})                      │  │
│  │  RETURN s.id, s.title, c.notation, c.rank, score                     │  │
│  │  ORDER BY c.rank DESC                                                │  │
│  │  LIMIT 10                                                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         3. Validate & Execute                               │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐             ┌───────────────────┐
        │  Success +        │             │  LLM Error OR     │
        │  Has Results      │             │  Invalid Cypher   │
        └─────────┬─────────┘             │  OR No Results    │
                  │                       └─────────┬─────────┘
                  ▼                                 ▼
        ┌───────────────────┐             ┌───────────────────────────────┐
        │  Return Results   │             │  4. FALLBACK: Pure Semantic   │
        │  method: "cypher" │             │     (embedding already ready) │
        └───────────────────┘             └───────────────────────────────┘
                                                    │
                                                    ▼
                                          ┌───────────────────┐
                                          │  Return Results   │
                                          │  method: "semantic"│
                                          └───────────────────┘
```

### LLM Schema Context

The LLM receives the graph schema to generate valid Cypher:

```python
GRAPH_SCHEMA = """
## Neo4j Graph Schema

### Nodes
- User {id: UUID, email: String, username: String}
- Snippet {id: UUID, title: String, description: String, code: String, 
           complexity_explanation: String, embedding: List<Float>}
- Language {name: String}  -- e.g., "python", "javascript"
- Complexity {notation: String, name: String, rank: Integer}
  - rank: 1=O(1) best → 8=O(n!) worst
  - Values: O(1), O(log n), O(n), O(n log n), O(n²), O(n³), O(2^n), O(n!)

### Relationships
- (Snippet)-[:OWNED_BY]->(User)
- (Snippet)-[:WRITTEN_IN]->(Language)
- (Snippet)-[:HAS_TIME_COMPLEXITY]->(Complexity)
- (Snippet)-[:HAS_SPACE_COMPLEXITY]->(Complexity)

### Available Parameters (always provided)
- $user_id: Current user's UUID (ALWAYS filter by this)
- $query_embedding: 768-dim vector of user's query (use for semantic search)

### Vector Search Syntax
CALL db.index.vector.queryNodes('snippet_embedding', <limit>, $query_embedding)
YIELD node AS s, score
"""
```

### Text-to-Cypher Prompt

```python
TEXT_TO_CYPHER_PROMPT = '''
You are a Cypher query generator for a code snippet knowledge graph.

{schema}

## When to Use What

| Query Type | Approach |
|------------|----------|
| "my worst code" | Graph only: ORDER BY c.rank DESC |
| "sorting algorithms" | Vector only: use $query_embedding |
| "worst sorting algorithms" | BOTH: vector + ORDER BY rank |
| "count by complexity" | Graph only: aggregation |
| "efficient Python sorting" | BOTH: vector + language + rank filter |

## Rules
1. ONLY generate READ queries (MATCH, RETURN, ORDER BY, LIMIT)
2. NEVER generate write operations (CREATE, DELETE, SET, MERGE)
3. ALWAYS filter by user: (s)-[:OWNED_BY]->(u:User {{id: $user_id}})
4. Use vector search for conceptual/descriptive terms
5. Use graph traversal for structured filters (complexity, language)
6. Combine both when query has both concepts AND structure

## Examples

User: "show me my worst performing code"
```cypher
MATCH (s:Snippet)-[:HAS_TIME_COMPLEXITY]->(c:Complexity)
MATCH (s)-[:OWNED_BY]->(u:User {{id: $user_id}})
RETURN s.id, s.title, s.description, c.notation, c.rank
ORDER BY c.rank DESC
LIMIT 10
```

User: "find sorting algorithms"
```cypher
CALL db.index.vector.queryNodes('snippet_embedding', 10, $query_embedding)
YIELD node AS s, score
MATCH (s)-[:OWNED_BY]->(u:User {{id: $user_id}})
RETURN s.id, s.title, s.description, score
ORDER BY score DESC
```

User: "my worst performing sorting algorithms"
```cypher
CALL db.index.vector.queryNodes('snippet_embedding', 30, $query_embedding)
YIELD node AS s, score
MATCH (s)-[:HAS_TIME_COMPLEXITY]->(c:Complexity)
MATCH (s)-[:OWNED_BY]->(u:User {{id: $user_id}})
RETURN s.id, s.title, c.notation, c.rank, score
ORDER BY c.rank DESC, score DESC
LIMIT 10
```

User: "efficient Python code for searching"
```cypher
CALL db.index.vector.queryNodes('snippet_embedding', 30, $query_embedding)
YIELD node AS s, score
MATCH (s)-[:WRITTEN_IN]->(l:Language {{name: 'python'}})
MATCH (s)-[:HAS_TIME_COMPLEXITY]->(c:Complexity)
MATCH (s)-[:OWNED_BY]->(u:User {{id: $user_id}})
WHERE c.rank <= 3
RETURN s.id, s.title, c.notation, score
ORDER BY score DESC
LIMIT 10
```

Generate a Cypher query for:
User: "{user_query}"

Return ONLY the Cypher query, no explanation.
'''
```

### Search Service Implementation

```python
class SearchService:
    # Fallback query - pure semantic similarity
    FALLBACK_CYPHER = """
    CALL db.index.vector.queryNodes('snippet_embedding', $limit, $query_embedding)
    YIELD node AS s, score
    MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
    MATCH (s)-[:HAS_TIME_COMPLEXITY]->(tc:Complexity)
    MATCH (s)-[:HAS_SPACE_COMPLEXITY]->(sc:Complexity)
    OPTIONAL MATCH (s)-[:WRITTEN_IN]->(l:Language)
    RETURN s.id, s.title, s.description, 
           tc.notation AS time_complexity,
           sc.notation AS space_complexity,
           l.name AS language,
           score
    ORDER BY score DESC
    """

    async def search(self, query: str, user_id: UUID, limit: int = 10) -> SearchResult:
        # 1. ALWAYS generate embedding first (needed for fallback anyway)
        query_embedding = await self.embedding_service.generate(query)
        
        params = {
            "user_id": str(user_id),
            "query_embedding": query_embedding,
            "limit": limit,
        }
        
        # 2. Try LLM-generated Cypher
        try:
            cypher = await self.cypher_generator.generate(query)
            
            if cypher and self._is_valid_cypher(cypher):
                results = await self.neo4j.execute(cypher, params)
                
                if results:  # Has results
                    return SearchResult(
                        results=results,
                        query=query,
                        method="cypher",
                    )
        except Exception as e:
            logger.warning(f"Text-to-Cypher failed: {e}")
        
        # 3. FALLBACK: Pure semantic search
        results = await self.neo4j.execute(self.FALLBACK_CYPHER, params)
        
        return SearchResult(
            results=results,
            query=query,
            method="semantic",
        )

    def _is_valid_cypher(self, cypher: str) -> bool:
        """Validate generated Cypher is safe to execute."""
        cypher_upper = cypher.upper()
        
        # Block write operations
        forbidden = ['CREATE', 'DELETE', 'SET', 'MERGE', 'REMOVE', 'DROP']
        if any(word in cypher_upper for word in forbidden):
            return False
        
        # Must include user filter
        if '$user_id' not in cypher:
            return False
        
        return True
```

### What This Enables

| Natural Language Query | LLM Decision | Result |
|------------------------|--------------|--------|
| "sorting algorithms" | Vector search | Semantic matches |
| "my worst code" | Graph only | Sorted by rank DESC |
| "worst sorting algorithms" | Vector + Graph | Combined |
| "efficient Python searching" | Vector + Language + Rank | All three |
| "how many snippets per complexity?" | Graph aggregation | Count grouped |
| *(LLM fails)* | — | Fallback semantic |
| *(No results)* | — | Fallback semantic |

### Graph Queries for UI-Driven Filters

Graph traversal is still used for **UI-initiated** queries (clicking complexity badges):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Snippet Detail View                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Title: Binary Search Implementation                                      │  │
│  │                                                                           │  │
│  │  Analysis Results:                                                        │  │
│  │  ┌─────────────┐  ┌─────────────┐                                        │  │
│  │  │ O(log n)    │  │ O(1)        │                                        │  │
│  │  │ [clickable] │  │ [clickable] │                                        │  │
│  │  └─────────────┘  └─────────────┘                                        │  │
│  │   ↑ time          ↑ space                                                │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  User clicks "O(log n)" → GET /snippets/complexity?time=O(log n)                │
│                         → Direct graph query (no LLM needed)                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Embedding Strategy

### Primary Search Mechanism

Since **90% of queries are semantic**, embeddings are the core of our search functionality. The embedding must be rich enough to match:
- Technical terms: "quadratic", "logarithmic", "exponential"
- Concepts: "efficient sorting", "find duplicates", "tree traversal"
- Algorithmic descriptions: "divide and conquer", "nested loops"

### What to Embed (Combined Content)

The embedding input combines **all searchable information** about a snippet:

```python
def build_embedding_input(
    snippet: Snippet,
    analysis: ComplexityAnalysis
) -> str:
    """
    Combine snippet fields + analysis results into embedding input.
    
    CRITICAL: Analysis results MUST be included so semantic searches
    like "quadratic runtime" or "recursive" match appropriately.
    
    Structure:
    1. Title (primary identifier)
    2. Description (user-provided context)
    3. Analysis summary (complexity + patterns in natural language)
    4. Code (truncated if needed)
    """
    parts = []
    
    # 1. Title
    parts.append(f"Title: {snippet.title}")
    
    # 2. Description (if provided)
    if snippet.description:
        parts.append(f"Description: {snippet.description}")
    
    # 3. Analysis summary (CRITICAL for semantic search)
    analysis_text = build_analysis_summary(analysis)
    parts.append(analysis_text)
    
    # 4. Code (truncated to ~2000 tokens)
    code = snippet.code[:8000]
    parts.append(f"Code:\n{code}")
    
    return "\n\n".join(parts)


def build_analysis_summary(analysis: ComplexityAnalysis) -> str:
    """
    Convert analysis results to natural language for embedding.
    
    This enables semantic searches like:
    - "quadratic" → matches "O(n²) quadratic"
    - "logarithmic" → matches "O(log n) logarithmic"
    - "efficient algorithms" → matches explanation content
    """
    lines = ["Analysis:"]
    
    # Time complexity with name (e.g., "O(n²) quadratic")
    lines.append(
        f"- Time Complexity: {analysis.time_complexity} "
        f"({analysis.time_complexity_name})"
    )
    
    # Space complexity with name
    lines.append(
        f"- Space Complexity: {analysis.space_complexity} "
        f"({analysis.space_complexity_name})"
    )
    
    # LLM explanation (rich semantic content)
    if analysis.explanation:
        lines.append(f"- Explanation: {analysis.explanation}")
    
    return "\n".join(lines)


# Example output for embedding:
"""
Title: Binary Search Implementation

Description: Efficient search algorithm for sorted arrays. Returns index or -1.

Analysis:
- Time Complexity: O(log n) (logarithmic)
- Space Complexity: O(1) (constant)
- Explanation: The algorithm repeatedly divides the search interval in half, 
  resulting in logarithmic time complexity. No additional data structures 
  are used, so space complexity is constant.

Code:
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
"""
```

### Why This Structure Works

| User Query | Matches Because |
|------------|-----------------|
| "binary search" | Title + Code |
| "logarithmic" | Analysis "O(log n) (logarithmic)" |
| "efficient search" | Description + Analysis explanation |
| "constant space" | Analysis "O(1) (constant)" |
| "sorted array" | Description + Code |

### Gemini Embedding Model

```python
import google.generativeai as genai

async def generate_embedding(text: str) -> list[float]:
    """Generate 768-dimension embedding using Gemini."""
    result = await genai.embed_content_async(
        model="models/text-embedding-004",
        content=text,
        task_type="SEMANTIC_SIMILARITY"
    )
    return result['embedding']  # List of 768 floats
```

---

## Neo4j Queries

### Schema Setup (Run Once)

```cypher
// Constraints for all node types
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT snippet_id IF NOT EXISTS FOR (s:Snippet) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT language_name IF NOT EXISTS FOR (l:Language) REQUIRE l.name IS UNIQUE;
CREATE CONSTRAINT complexity_notation IF NOT EXISTS FOR (c:Complexity) REQUIRE c.notation IS UNIQUE;

// Vector Index for semantic search
CREATE VECTOR INDEX snippet_embedding IF NOT EXISTS
FOR (s:Snippet)
ON s.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }
};

// Pre-populate Language nodes
UNWIND ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c', 'cpp'] AS lang
MERGE (l:Language {name: lang});

// Pre-populate Complexity nodes
UNWIND [
  {notation: 'O(1)', name: 'constant', rank: 1},
  {notation: 'O(log n)', name: 'logarithmic', rank: 2},
  {notation: 'O(n)', name: 'linear', rank: 3},
  {notation: 'O(n log n)', name: 'linearithmic', rank: 4},
  {notation: 'O(n²)', name: 'quadratic', rank: 5},
  {notation: 'O(n³)', name: 'cubic', rank: 6},
  {notation: 'O(2^n)', name: 'exponential', rank: 7},
  {notation: 'O(n!)', name: 'factorial', rank: 8}
] AS c
MERGE (comp:Complexity {notation: c.notation})
SET comp.name = c.name, comp.rank = c.rank;
```

### Upsert Snippet

```cypher
// Upsert snippet with relationships to categorical nodes
MERGE (s:Snippet {id: $snippet_id})
SET s.title = $title,
    s.description = $description,
    s.code = $code,
    s.complexity_explanation = $complexity_explanation,
    s.embedding = $embedding,
    s.updated_at = datetime(),
    s.synced_at = datetime()
ON CREATE SET s.created_at = datetime()

// Link to User
WITH s
MATCH (u:User {id: $user_id})
MERGE (s)-[:OWNED_BY]->(u)

// Link to Language
WITH s
MATCH (l:Language {name: $language})
MERGE (s)-[:WRITTEN_IN]->(l)

// Link to Time Complexity (delete old, create new)
WITH s
OPTIONAL MATCH (s)-[r1:HAS_TIME_COMPLEXITY]->()
DELETE r1
WITH s
MATCH (tc:Complexity {notation: $time_complexity})
MERGE (s)-[:HAS_TIME_COMPLEXITY]->(tc)

// Link to Space Complexity (delete old, create new)
WITH s
OPTIONAL MATCH (s)-[r2:HAS_SPACE_COMPLEXITY]->()
DELETE r2
WITH s
MATCH (sc:Complexity {notation: $space_complexity})
MERGE (s)-[:HAS_SPACE_COMPLEXITY]->(sc)

RETURN s
```

### Query: By Complexity

```cypher
// "O(n²)" - exact notation match
MATCH (s:Snippet)-[:HAS_TIME_COMPLEXITY]->(c:Complexity {notation: $notation})
MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
RETURN s.id, s.title, s.description, c.notation AS time_complexity
ORDER BY s.updated_at DESC

// "quadratic" - name match
MATCH (s:Snippet)-[:HAS_TIME_COMPLEXITY]->(c:Complexity {name: $name})
MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
RETURN s.id, s.title, s.description, c.notation AS time_complexity
ORDER BY s.updated_at DESC

// "worse than linear" - rank comparison
MATCH (s:Snippet)-[:HAS_TIME_COMPLEXITY]->(c:Complexity)
WHERE c.rank > 3  // 3 = linear
MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
RETURN s.id, s.title, c.notation AS time_complexity
ORDER BY c.rank ASC
```

### Query: Semantic Search (Vector)

```cypher
// Free-form query: "algorithm to merge sorted arrays"
// Only used when no pattern/complexity keywords detected
CALL db.index.vector.queryNodes(
  'snippet_embedding',
  $limit,
  $query_embedding
)
YIELD node AS s, score
MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
RETURN s.id, s.title, s.description, score
ORDER BY score DESC
```

### Query: Similar Snippets (Runtime)

```cypher
// Find snippets similar to a given snippet (computed at runtime)
MATCH (source:Snippet {id: $snippet_id})
CALL db.index.vector.queryNodes(
  'snippet_embedding',
  $limit + 1,  // +1 to exclude self
  source.embedding
)
YIELD node AS s, score
WHERE s.id <> $snippet_id
MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
RETURN s.id, s.title, s.description, score
ORDER BY score DESC
LIMIT $limit
```

---

## API Endpoints (New)

### Unified Search (Text-to-Cypher with Fallback)

```
GET /snippets/search?q={query}&limit=10

All search queries go through the unified Text-to-Cypher pipeline:
1. Generate query embedding (always, for fallback)
2. LLM generates Cypher (may use embedding, graph, or both)
3. Execute Cypher
4. If fails or no results → fallback to pure semantic search

Examples:
- "sorting algorithms" → LLM uses vector search
- "my worst code" → LLM uses graph traversal (ORDER BY rank DESC)
- "worst sorting algorithms" → LLM combines both
- (LLM fails) → Fallback semantic search

Response:
{
  "results": [
    {
      "id": "uuid",
      "title": "Binary Search",
      "description": "...",
      "language": "python",
      "time_complexity": "O(log n)",
      "space_complexity": "O(1)",
      "score": 0.92  // similarity score if semantic search was used
    }
  ],
  "query": "efficient search algorithm",
  "method": "cypher" | "semantic",  // which path was used
  "total": 5
}
```

### Filter by Complexity (UI Click)

```
GET /snippets/complexity?time={notation}&space={notation}

Used when user clicks on a complexity badge in the UI.
Direct graph traversal - fast and exact (no LLM needed).

Example: User clicks "O(n²)" badge → GET /snippets/complexity?time=O(n²)

Response:
{
  "snippets": [...],
  "filters": {
    "time_complexity": "O(n²)",
    "space_complexity": null
  },
  "total": 12
}
```

---

## Implementation Steps

| Step | Task | Details |
|------|------|---------|
| 9.2.1 | Neo4j AuraDB setup | Create free tier instance, get credentials |
| 9.2.2 | Neo4j Python driver | Add `neo4j` to dependencies, create service |
| 9.2.3 | Graph schema setup | Run constraint/index creation, pre-populate nodes |
| 9.2.4 | Embedding service | Gemini `text-embedding-004` + analysis in input |
| 9.2.5 | CDC queue | Add `snippet-sync.fifo` SQS queue (Pulumi) |
| 9.2.6 | Sync worker Lambda | Process CDC: analyze → embed (with analysis) → Neo4j |
| 9.2.7 | Cypher generator service | LLM Text-to-Cypher with schema context |
| 9.2.8 | Search service | Unified search with fallback to semantic |
| 9.2.9 | Search endpoint | `GET /snippets/search` - Text-to-Cypher + fallback |
| 9.2.10 | Complexity filter | `GET /snippets/complexity` - graph traversal (UI click) |

---

## Infrastructure (Pulumi)

### New Resources

```python
# infra/pulumi/components/neo4j.py (configuration only - hosted on AuraDB)

# Store Neo4j credentials in Secrets Manager
neo4j_secret = aws.secretsmanager.Secret(
    "neo4j-credentials",
    name=f"{env}-neo4j-credentials",
)

aws.secretsmanager.SecretVersion(
    "neo4j-credentials-version",
    secret_id=neo4j_secret.id,
    secret_string=pulumi.Output.json_dumps({
        "uri": neo4j_uri,           # neo4j+s://xxxx.databases.neo4j.io
        "username": "neo4j",
        "password": neo4j_password,  # from Pulumi config (encrypted)
    }),
)

# SQS FIFO Queue for CDC events
snippet_sync_queue = aws.sqs.Queue(
    "snippet-sync-queue",
    name=f"{env}-snippet-sync.fifo",
    fifo_queue=True,
    content_based_deduplication=True,
    visibility_timeout_seconds=300,  # 5 min for LLM + Neo4j operations
)

snippet_sync_dlq = aws.sqs.Queue(
    "snippet-sync-dlq",
    name=f"{env}-snippet-sync-dlq.fifo",
    fifo_queue=True,
)
```

---

## Configuration

### Environment Variables

```bash
# .env additions

# Neo4j AuraDB
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Embedding model
GEMINI_EMBEDDING_MODEL=text-embedding-004

# CDC Queue
SNIPPET_SYNC_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/xxx/snippet-sync.fifo
```

---

## Error Handling & Resilience

| Scenario | Handling |
|----------|----------|
| Gemini API failure | Retry 3x with backoff, then DLQ |
| Neo4j connection failure | Retry 3x, then DLQ |
| Embedding dimension mismatch | Log error, skip (schema issue) |
| Snippet deleted before sync | Skip gracefully (idempotent) |
| Duplicate CDC events | SQS FIFO deduplication + Neo4j MERGE |
| Text-to-Cypher LLM fails | Fallback to pure semantic search |
| Generated Cypher invalid | Fallback to pure semantic search |
| Cypher returns no results | Fallback to pure semantic search |

---

## Future Enhancements (Phase 9.3+)

1. **Pattern Detection**: LLM extracts algorithmic patterns (recursion, memoization, etc.) as graph nodes
2. **Cross-user recommendations**: "Users with similar snippets also wrote..." (opt-in)
3. **Complexity trends**: Track how user's code complexity evolves over time
4. **Similar snippets**: `GET /snippets/{id}/similar` - find similar code

---

## Files to Create/Modify

### New Files
- `infra/pulumi/components/neo4j.py` - Neo4j config + SQS queue
- `backend/api/services/neo4j_service.py` - Neo4j driver + queries
- `backend/api/services/embedding_service.py` - Gemini embedding (includes analysis in input)
- `backend/api/services/cypher_generator.py` - LLM Text-to-Cypher with schema context
- `backend/api/services/search_service.py` - Unified search with fallback
- `backend/api/services/sync_worker.py` - CDC event processor
- `backend/api/routers/search.py` - Search endpoints
- `backend/api/schemas/search.py` - Search request/response schemas
- `backend/analyzer/prompts/text_to_cypher.txt` - Text-to-Cypher prompt

### Modified Files
- `infra/pulumi/__main__.py` - Add neo4j component
- `backend/common/config.py` - Add Neo4j + embedding settings
- `backend/api/routers/snippets.py` - Enqueue CDC events
- `backend/api/services/snippet_service.py` - Emit events on CRUD
- `backend/pyproject.toml` - Add `neo4j` dependency

---

## Testing Strategy

### Unit Tests
- Mock Neo4j driver, test query construction
- Mock Gemini API, test embedding input composition
- Test CDC event serialization/deserialization
- Test Cypher validation (block write operations, require user filter)
- Test fallback triggers (LLM error, invalid Cypher, no results)

### Integration Tests
- Local Neo4j container (docker-compose)
- End-to-end: create snippet → CDC → Neo4j upsert
- Text-to-Cypher with various query types
- Fallback behavior verification

### Load Tests
- Bulk snippet creation → CDC queue throughput
- Concurrent search queries
