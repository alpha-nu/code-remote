"""CLI entrypoint for Neo4j migrations.

Usage:
    python -m neo4j_migrations              # run all pending
    python -m neo4j_migrations status       # show migration status

Requires NEO4J_URI, NEO4J_PASSWORD, and NEO4J_DATABASE env vars
(or NEO4J_SECRET_ARN for AWS Secrets Manager).
"""

import argparse
import logging
import sys

from api.services.neo4j_service import get_neo4j_credentials, neo4j_driver_context
from neo4j_migrations.runner import Neo4jMigrationRunner

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
# Suppress noisy Neo4j driver notifications (e.g., "constraint already exists")
logging.getLogger("neo4j").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


def run_migrations() -> int:
    """Run all pending migrations. Returns exit code."""
    credentials = get_neo4j_credentials()
    database = credentials["database"]

    with neo4j_driver_context() as driver:
        runner = Neo4jMigrationRunner(driver, database=database)
        status = runner.get_status()

        if not status["pending"]:
            logger.info("No pending migrations.")
            return 0

        logger.info(f"Pending migrations: {status['pending']}")
        applied = runner.run_all_pending()
        logger.info(f"Applied {len(applied)} migration(s): {applied}")
    return 0


def show_status() -> int:
    """Show migration status. Returns exit code."""
    credentials = get_neo4j_credentials()
    database = credentials["database"]

    with neo4j_driver_context() as driver:
        runner = Neo4jMigrationRunner(driver, database=database)
        status = runner.get_status()

    print(f"Total:   {status['total']}")
    print(f"Applied: {status['applied']}")
    print(f"Pending: {status['pending']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Neo4j migration runner")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "status"],
        help="Command to execute (default: run)",
    )
    args = parser.parse_args()

    try:
        if args.command == "status":
            return show_status()
        return run_migrations()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
