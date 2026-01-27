"""Pytest configuration for smoke tests."""

import os

import pytest


def pytest_addoption(parser):
    """Add command line options for smoke tests."""
    parser.addoption(
        "--api-url",
        action="store",
        default=os.getenv("API_ENDPOINT", "http://localhost:8000"),
        help="API endpoint URL for smoke tests",
    )


@pytest.fixture
def api_url(request):
    """Get the API URL from command line or environment."""
    return request.config.getoption("--api-url")
