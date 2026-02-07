"""Initial Neo4j schema migration.

Creates constraints, indexes, and pre-populates reference nodes.
"""

MIGRATION_ID = "0001"
DESCRIPTION = "Initial schema: constraints, indexes, and reference nodes"

QUERIES = [
    # === Constraints ===
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT snippet_id IF NOT EXISTS FOR (s:Snippet) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT language_name IF NOT EXISTS FOR (l:Language) REQUIRE l.name IS UNIQUE",
    "CREATE CONSTRAINT complexity_notation IF NOT EXISTS FOR (c:Complexity) REQUIRE c.notation IS UNIQUE",
    "CREATE CONSTRAINT migration_id IF NOT EXISTS FOR (m:Migration) REQUIRE m.id IS UNIQUE",
    # === Vector Index ===
    """
    CREATE VECTOR INDEX snippet_embedding IF NOT EXISTS
    FOR (s:Snippet) ON s.embedding
    OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}
    """,
    # === Pre-populate Languages ===
    "MERGE (l:Language {name: 'python'})",
    "MERGE (l:Language {name: 'javascript'})",
    "MERGE (l:Language {name: 'typescript'})",
    "MERGE (l:Language {name: 'java'})",
    "MERGE (l:Language {name: 'go'})",
    "MERGE (l:Language {name: 'rust'})",
    "MERGE (l:Language {name: 'c'})",
    "MERGE (l:Language {name: 'cpp'})",
    "MERGE (l:Language {name: 'csharp'})",
    "MERGE (l:Language {name: 'ruby'})",
    "MERGE (l:Language {name: 'php'})",
    "MERGE (l:Language {name: 'swift'})",
    "MERGE (l:Language {name: 'kotlin'})",
    "MERGE (l:Language {name: 'scala'})",
    # NOTE: Complexity nodes are created dynamically via MERGE in upsert_snippet
    # to handle varied LLM output formats (e.g., O(n^2) vs O(n²))
]
