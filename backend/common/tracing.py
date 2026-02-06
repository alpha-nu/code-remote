"""
AWS X-Ray tracing for LLM calls.

Simple subsegment wrapper for Gemini API observability.
No-op when running outside Lambda (no active X-Ray segment).
"""

import os
from contextlib import contextmanager
from typing import Any

from aws_xray_sdk.core import patch_all, xray_recorder

# Auto-patch supported libraries (boto3, httpx, etc.)
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    patch_all()


@contextmanager
def llm_span(operation: str, model: str, **attributes: Any):
    """Create an X-Ray subsegment for LLM operations.

    Gracefully no-ops when no active segment exists (e.g., in tests or local dev).
    """
    with xray_recorder.in_subsegment(f"llm.{operation}") as subsegment:
        if subsegment is None:
            # No active segment - just yield None and continue
            yield None
        else:
            subsegment.put_metadata("model", model)
            subsegment.put_annotation("gen_ai_operation", operation)
            for key, value in attributes.items():
                if isinstance(value, str) and len(value) > 500:
                    value = value[:500] + "..."
                subsegment.put_metadata(key, value)
            yield subsegment


def add_llm_response_attributes(subsegment, **attributes: Any) -> None:
    """Add response metadata to subsegment. No-op if subsegment is None."""
    if subsegment is None:
        return
    for key, value in attributes.items():
        if isinstance(value, str) and len(value) > 500:
            value = value[:500] + "..."
        subsegment.put_metadata(key, value)
