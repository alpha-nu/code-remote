"""Lambda handler for Neo4j migrations.

This handler runs pending Neo4j schema migrations.
Invoked during deployment via GitHub Actions.
"""

import json
import logging
from typing import Any

from api.services.neo4j_service import get_neo4j_credentials, neo4j_driver_context
from neo4j_migrations.runner import Neo4jMigrationRunner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for Neo4j migrations.

    Args:
        event: Lambda event (unused).
        context: Lambda context.

    Returns:
        Response with migration status.
    """
    logger.info("Starting Neo4j migrations...")

    try:
        # Get credentials (includes database name from secret)
        credentials = get_neo4j_credentials()
        database = credentials["database"]
        logger.info(f"Using database: {database}")

        # Use context manager for migrations - creates fresh driver, closes on exit
        with neo4j_driver_context() as driver:
            runner = Neo4jMigrationRunner(driver, database=database)

            # Get current status
            status_before = runner.get_status()
            logger.info(f"Status before: {status_before}")

            # Run pending migrations
            applied = runner.run_all_pending()

            # Get final status
            status_after = runner.get_status()

            result = {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Neo4j migrations complete",
                        "applied": applied,
                        "status": status_after,
                    }
                ),
            }

            logger.info(f"Migrations complete. Applied: {applied}")
            return result

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(e),
                    "message": "Neo4j migration failed",
                }
            ),
        }


# For local testing
if __name__ == "__main__":
    result = handler({}, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
