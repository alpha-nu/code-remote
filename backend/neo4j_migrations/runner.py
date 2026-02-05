"""Neo4j migration runner.

Discovers and applies pending migrations to Neo4j.
"""

import importlib
import logging
import pkgutil
from types import ModuleType

from neo4j import Driver

logger = logging.getLogger(__name__)


def discover_migrations() -> list[ModuleType]:
    """Discover all migration modules in the versions directory.

    Returns:
        List of migration modules sorted by MIGRATION_ID.
    """
    import neo4j_migrations.versions as versions_pkg

    migrations = []

    for importer, modname, ispkg in pkgutil.iter_modules(versions_pkg.__path__):
        if not ispkg and modname.startswith("0"):  # Migration files start with numbers
            module = importlib.import_module(f"neo4j_migrations.versions.{modname}")
            if hasattr(module, "MIGRATION_ID") and hasattr(module, "QUERIES"):
                migrations.append(module)

    # Sort by migration ID
    migrations.sort(key=lambda m: m.MIGRATION_ID)
    return migrations


class Neo4jMigrationRunner:
    """Runs Neo4j schema migrations."""

    def __init__(self, driver: Driver, database: str = "neo4j"):
        """Initialize migration runner.

        Args:
            driver: Neo4j driver instance.
            database: Database name.
        """
        self.driver = driver
        self.database = database

    def get_applied_migrations(self) -> set[str]:
        """Get list of already-applied migration IDs.

        Returns:
            Set of applied migration IDs.
        """
        with self.driver.session(database=self.database) as session:
            result = session.run("MATCH (m:Migration) RETURN m.id AS id")
            return {record["id"] for record in result}

    def run_migration(
        self,
        migration_id: str,
        description: str,
        queries: list[str],
    ) -> None:
        """Run a single migration and record it.

        Args:
            migration_id: Unique migration identifier.
            description: Human-readable description.
            queries: List of Cypher queries to execute.
        """
        with self.driver.session(database=self.database) as session:
            # Execute all migration queries
            for query in queries:
                query = query.strip()
                if query:
                    logger.debug(f"Executing: {query[:100]}...")
                    session.run(query)

            # Record migration as applied
            session.run(
                """
                MERGE (m:Migration {id: $id})
                SET m.description = $description,
                    m.applied_at = datetime()
                """,
                id=migration_id,
                description=description,
            )

        logger.info(f"Applied migration {migration_id}: {description}")

    def run_all_pending(self) -> list[str]:
        """Discover and run all pending migrations.

        Returns:
            List of applied migration IDs.
        """
        applied = self.get_applied_migrations()
        newly_applied = []

        for migration in discover_migrations():
            if migration.MIGRATION_ID not in applied:
                logger.info(f"Applying Neo4j migration: {migration.MIGRATION_ID}")
                self.run_migration(
                    migration.MIGRATION_ID,
                    getattr(migration, "DESCRIPTION", ""),
                    migration.QUERIES,
                )
                newly_applied.append(migration.MIGRATION_ID)

        if not newly_applied:
            logger.info("No pending Neo4j migrations")

        return newly_applied

    def get_status(self) -> dict:
        """Get migration status.

        Returns:
            Dictionary with migration status information.
        """
        applied = self.get_applied_migrations()
        all_migrations = discover_migrations()

        pending = [m.MIGRATION_ID for m in all_migrations if m.MIGRATION_ID not in applied]

        return {
            "applied": sorted(applied),
            "pending": pending,
            "total": len(all_migrations),
        }
