"""Messaging Component - SQS Queues for async job processing."""

import json

import pulumi
import pulumi_aws as aws


class MessagingComponent(pulumi.ComponentResource):
    """SQS FIFO queue for code execution jobs."""

    def __init__(
        self,
        name: str,
        environment: str,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:messaging:Queues", name, None, opts)

        self.tags = tags or {}

        # Dead Letter Queue for failed jobs
        self.dlq = aws.sqs.Queue(
            f"{name}-dlq",
            name=f"code-remote-{environment}-execution-dlq.fifo",
            fifo_queue=True,
            message_retention_seconds=1209600,  # 14 days
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Main execution queue (FIFO for ordering)
        self.queue = aws.sqs.Queue(
            f"{name}-queue",
            name=f"code-remote-{environment}-execution.fifo",
            fifo_queue=True,
            content_based_deduplication=False,  # We'll use job_id
            visibility_timeout_seconds=60,  # 2x max execution time (30s)
            message_retention_seconds=3600,  # 1 hour (jobs are ephemeral)
            receive_wait_time_seconds=20,  # Long polling
            redrive_policy=self.dlq.arn.apply(
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
                "queue_url": self.queue.url,
                "queue_arn": self.queue.arn,
                "dlq_url": self.dlq.url,
                "dlq_arn": self.dlq.arn,
            }
        )
