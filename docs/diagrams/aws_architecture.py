#!/usr/bin/env python3
"""Generate AWS architecture diagrams for Code Remote.

This script uses the `diagrams` library to generate professional architecture
diagrams with official AWS icons. Run this script to regenerate diagrams after
architecture changes.

Requirements:
    pip install diagrams

Usage:
    python aws_architecture.py

Output:
    - aws_architecture.png: Full system architecture
    - data_flow.png: Request/response data flow
    - security_layers.png: Security model visualization
"""

import argparse

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Aurora
from diagrams.aws.integration import SQS
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import Cognito, SecretsManager
from diagrams.aws.storage import S3
from diagrams.onprem.database import Neo4J
from diagrams.programming.framework import React
from diagrams.saas.chat import Slack  # Using as placeholder for Gemini

# ============================================================================
# SIZE PRESETS
# ============================================================================
# Adjust these values to control icon and text sizes across all diagrams.
# The diagrams library uses Graphviz under the hood - all sizes are in inches.

SIZE_PRESETS = {
    "small": {
        "node_width": "1.0",
        "node_height": "1.0",
        "fontsize": "10",
        "title_fontsize": "16",
    },
    "medium": {
        "node_width": "1.5",
        "node_height": "1.5",
        "fontsize": "12",
        "title_fontsize": "20",
    },
    "large": {
        "node_width": "2.0",
        "node_height": "2.0",
        "fontsize": "14",
        "title_fontsize": "24",
    },
    "xlarge": {
        "node_width": "2.5",
        "node_height": "2.5",
        "fontsize": "16",
        "title_fontsize": "28",
    },
}

# Default size preset (change this to adjust all diagrams at once)
DEFAULT_SIZE = "medium"


def get_diagram_attrs(size: str = DEFAULT_SIZE) -> tuple[dict, dict]:
    """Get graph and node attributes for the given size preset.

    Args:
        size: One of 'small', 'medium', 'large', 'xlarge'

    Returns:
        Tuple of (graph_attr, node_attr) dictionaries
    """
    preset = SIZE_PRESETS.get(size, SIZE_PRESETS["medium"])

    graph_attr = {
        "fontsize": preset["title_fontsize"],
        "bgcolor": "white",
        "pad": "0.5",
        "splines": "ortho",
    }

    node_attr = {
        "width": preset["node_width"],
        "height": preset["node_height"],
        "fontsize": preset["fontsize"],
    }

    return graph_attr, node_attr


def create_full_architecture(size: str = DEFAULT_SIZE):
    """Create the main AWS architecture diagram."""
    graph_attr, node_attr = get_diagram_attrs(size)
    with Diagram(
        "Code Remote - AWS Architecture",
        filename="aws_architecture",
        show=False,
        direction="TB",
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        # External
        user = React("Frontend\n(React + Monaco)")

        with Cluster("AWS Cloud"):
            # CDN Layer
            cdn = CloudFront("CloudFront CDN")
            s3 = S3("Frontend Bucket")

            # API Layer
            with Cluster("API Layer"):
                apigw = APIGateway("API Gateway\n(HTTP + WebSocket)")
                cognito = Cognito("Cognito\nUser Pool")

            # Compute Layer
            with Cluster("Compute Layer"):
                api_lambda = Lambda("API Lambda\n(FastAPI)")
                worker_lambda = Lambda("Worker Lambda\n(Executor)")
                sync_lambda = Lambda("Sync Worker\n(Neo4j CDC)")
                migration_lambda = Lambda("Migration\nLambda")

            # Messaging
            with Cluster("Messaging"):
                exec_queue = SQS("Execution Queue\n(FIFO)")
                sync_queue = SQS("Snippet Sync\nQueue (FIFO)")

            # Data Layer
            with Cluster("Data Layer", direction="LR"):
                with Cluster("VPC - Private Subnets"):
                    aurora = Aurora("Aurora\nPostgreSQL")
                secrets = SecretsManager("Secrets\nManager")
                neo4j = Neo4J("Neo4j AuraDB\n(Vector Search)")

            # External Services
            gemini = Slack("Google Gemini\n(LLM API)")

        # Connections
        user >> cdn >> s3
        user >> apigw
        apigw >> cognito
        apigw >> api_lambda
        apigw >> worker_lambda

        api_lambda >> aurora
        api_lambda >> secrets
        api_lambda >> exec_queue
        api_lambda >> sync_queue

        exec_queue >> worker_lambda
        worker_lambda >> aurora
        worker_lambda >> apigw  # WebSocket push

        sync_queue >> sync_lambda
        sync_lambda >> aurora
        sync_lambda >> neo4j
        sync_lambda >> gemini

        migration_lambda >> aurora

        api_lambda >> gemini  # Analysis requests


def create_data_flow(size: str = DEFAULT_SIZE):
    """Create data flow diagram for code execution."""
    graph_attr, node_attr = get_diagram_attrs(size)
    with Diagram(
        "Code Execution Flow",
        filename="data_flow",
        show=False,
        direction="LR",
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        with Cluster("Client"):
            browser = React("Browser")

        with Cluster("API Gateway"):
            http_api = APIGateway("HTTP API")
            ws_api = APIGateway("WebSocket")

        with Cluster("Processing"):
            api = Lambda("API Lambda")
            queue = SQS("FIFO Queue")
            worker = Lambda("Worker")

        with Cluster("Storage"):
            db = Aurora("PostgreSQL")

        # Flow
        browser >> Edge(label="1. POST /execute") >> http_api
        http_api >> Edge(label="2. Validate JWT") >> api
        api >> Edge(label="3. Queue job") >> queue
        api >> Edge(label="4. Return job_id", style="dashed") >> http_api
        http_api >> Edge(style="dashed") >> browser

        queue >> Edge(label="5. Consume") >> worker
        worker >> Edge(label="6. Execute code") >> worker
        worker >> Edge(label="7. Push result") >> ws_api
        ws_api >> Edge(label="8. Real-time update") >> browser
        worker >> Edge(label="9. Store result") >> db


def create_security_layers(size: str = DEFAULT_SIZE):
    """Create security model diagram."""
    graph_attr, node_attr = get_diagram_attrs(size)
    with Diagram(
        "Security Layers",
        filename="security_layers",
        show=False,
        direction="TB",
        graph_attr={**graph_attr, "rankdir": "TB"},
        node_attr=node_attr,
    ):
        with Cluster("Layer 1: Edge Security"):
            cdn = CloudFront("CloudFront\nWAF + TLS")
            apigw = APIGateway("API Gateway\nRate Limiting")

        with Cluster("Layer 2: Authentication"):
            cognito = Cognito("Cognito JWT\nValidation")

        with Cluster("Layer 3: Application"):
            with Cluster("Input Validation"):
                validation = Lambda("Pydantic\n10KB limit\nUTF-8 only")

            with Cluster("AST Analysis"):
                ast = Lambda("Import Whitelist\nDangerous Patterns")

        with Cluster("Layer 4: Execution Sandbox"):
            with Cluster("Lambda Isolation"):
                sandbox = Lambda("Restricted Builtins\nNo Network\nTimeout: 30s")

        with Cluster("Layer 5: Data Security"):
            SecretsManager("Secrets Manager\nEncrypted at rest")
            with Cluster("VPC Isolation"):
                Aurora("Private Subnets\nNo public access")

        # Flow
        cdn >> apigw >> cognito >> validation >> ast >> sandbox


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AWS architecture diagrams")
    parser.add_argument(
        "--size",
        choices=["small", "medium", "large", "xlarge"],
        default=DEFAULT_SIZE,
        help=f"Icon size preset (default: {DEFAULT_SIZE})",
    )
    args = parser.parse_args()

    print(f"Generating architecture diagrams (size: {args.size})...")
    create_full_architecture(args.size)
    print("✓ aws_architecture.png")
    create_data_flow(args.size)
    print("✓ data_flow.png")
    create_security_layers(args.size)
    print("✓ security_layers.png")
    print("\nDone! Diagrams saved to current directory.")
