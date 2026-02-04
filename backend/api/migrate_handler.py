"""Migration Lambda handler.

This Lambda runs Alembic migrations against the database.
Invoked during CI/CD deployment after the API Lambda is updated.
"""

import json
import logging
import subprocess
import sys

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    """Run Alembic migrations.

    Args:
        event: Lambda event (unused)
        context: Lambda context

    Returns:
        Migration result with status and output
    """
    logger.info("Starting database migration...")

    try:
        # Run alembic upgrade head
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode == 0:
            logger.info("Migration completed successfully")
            logger.info(f"Output: {result.stdout}")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "success",
                        "message": "Migrations completed successfully",
                        "output": result.stdout,
                    }
                ),
            }
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "status": "error",
                        "message": "Migration failed",
                        "error": result.stderr,
                        "output": result.stdout,
                    }
                ),
            }

    except subprocess.TimeoutExpired:
        logger.error("Migration timed out after 5 minutes")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": "Migration timed out after 5 minutes",
                }
            ),
        }
    except Exception as e:
        logger.exception("Unexpected error during migration")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": str(e),
                }
            ),
        }
