"""Clean up pre-populated Complexity nodes.

Removes orphaned Complexity nodes that were pre-populated but have no
relationships. Complexity nodes are now created dynamically via MERGE
to handle varied LLM output formats (e.g., O(n^2) vs O(n²)).
"""

MIGRATION_ID = "0002"
DESCRIPTION = "Remove orphaned pre-populated Complexity nodes"

QUERIES = [
    # Delete Complexity nodes that have no incoming relationships
    # This safely removes pre-populated nodes while preserving any
    # that are actually linked to snippets
    """
    MATCH (c:Complexity)
    WHERE NOT (c)<-[:HAS_TIME_COMPLEXITY]-() AND NOT (c)<-[:HAS_SPACE_COMPLEXITY]-()
    DELETE c
    """,
]
