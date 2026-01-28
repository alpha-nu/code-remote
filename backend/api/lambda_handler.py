"""AWS Lambda handler for FastAPI using Mangum adapter.

This module provides the entry point for AWS Lambda to invoke the FastAPI application.
Mangum handles the translation between API Gateway events and ASGI.
"""

from mangum import Mangum

from api.main import app

# Create the Lambda handler
# Mangum wraps FastAPI's ASGI interface for AWS Lambda + API Gateway
handler = Mangum(app, lifespan="off")
