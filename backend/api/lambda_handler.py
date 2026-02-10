"""AWS Lambda handler for FastAPI using Mangum adapter.

This module provides the entry point for AWS Lambda to invoke the FastAPI application.
Mangum handles the translation between API Gateway events and ASGI.
"""

import logging

from mangum import Mangum

from api.main import app

# Configure root logger so application-level INFO/WARNING/ERROR messages
# propagate to CloudWatch.  The Lambda runtime adds a StreamHandler on the
# root logger, but leaves the level at WARNING by default — which silently
# swallows every INFO message from FastAPI routes, background tasks, and
# shared modules like ``common.websocket``.
logging.getLogger().setLevel(logging.INFO)

# Create the Lambda handler
# Mangum wraps FastAPI's ASGI interface for AWS Lambda + API Gateway
handler = Mangum(app, lifespan="off")
