"""Neo4j Component - Configuration and secrets for Neo4j AuraDB."""

import json

import pulumi
import pulumi_aws as aws


class Neo4jComponent(pulumi.ComponentResource):
    """Neo4j configuration for AuraDB integration.

    Manages secrets and configuration for Neo4j AuraDB connection.
    The Neo4j instance itself is hosted externally on AuraDB.
    """

    def __init__(
        self,
        name: str,
        environment: str,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """Initialize Neo4j component.

        Args:
            name: Resource name prefix.
            environment: Deployment environment (dev/staging/prod).
            tags: Common resource tags.
            opts: Pulumi resource options.
        """
        super().__init__("coderemote:neo4j:Config", name, None, opts)

        self.tags = tags or {}

        self.credentials_secret = aws.secretsmanager.Secret(
            f"{name}-credentials",
            name=f"code-remote-{environment}-neo4j-credentials",
            description=f"Neo4j AuraDB credentials for {environment}",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Snippet sync queue (FIFO) - for Neo4j synchronization
        self.sync_dlq = aws.sqs.Queue(
            f"{name}-sync-dlq",
            name=f"code-remote-{environment}-snippet-sync-dlq.fifo",
            fifo_queue=True,
            message_retention_seconds=1209600,  # 14 days
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.sync_queue = aws.sqs.Queue(
            f"{name}-sync-queue",
            name=f"code-remote-{environment}-snippet-sync.fifo",
            fifo_queue=True,
            content_based_deduplication=True,  # Dedup based on message body
            visibility_timeout_seconds=60,  # 60s for embedding + Neo4j write
            message_retention_seconds=86400,  # 24 hours
            receive_wait_time_seconds=20,  # Long polling
            redrive_policy=self.sync_dlq.arn.apply(
                lambda arn: json.dumps(
                    {
                        "deadLetterTargetArn": arn,
                        "maxReceiveCount": 3,
                    }
                )
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "credentials_secret_arn": self.credentials_secret.arn,
                "sync_queue_url": self.sync_queue.url,
                "sync_queue_arn": self.sync_queue.arn,
                "sync_dlq_url": self.sync_dlq.url,
                "sync_dlq_arn": self.sync_dlq.arn,
            }
        )
