"""Fargate-based executor service for Lambda environments.

In Lambda, we can't use multiprocessing (no /dev/shm), so we run code
execution as ECS Fargate tasks instead.
"""

import asyncio
import logging
import time
from typing import Any

import boto3

from api.schemas.execution import ExecutionResponse
from common.config import settings

logger = logging.getLogger(__name__)


class FargateExecutorService:
    """Service for executing code via ECS Fargate tasks."""

    def __init__(self):
        """Initialize the Fargate executor service."""
        self.ecs_client = boto3.client("ecs", region_name=settings.cognito_region)
        self.logs_client = boto3.client("logs", region_name=settings.cognito_region)
        self.cluster_arn = settings.fargate_cluster_arn
        self.task_definition_arn = settings.fargate_task_definition_arn
        self.subnets = [s.strip() for s in settings.fargate_subnets.split(",") if s.strip()]
        self.security_group_id = settings.fargate_security_group_id

    def is_configured(self) -> bool:
        """Check if Fargate executor is properly configured."""
        return bool(
            self.cluster_arn
            and self.task_definition_arn
            and self.subnets
            and self.security_group_id
        )

    async def execute(
        self,
        code: str,
        timeout_seconds: float | None = None,
    ) -> ExecutionResponse:
        """Execute Python code in a Fargate task.

        Args:
            code: The Python source code to execute.
            timeout_seconds: Maximum execution time.

        Returns:
            ExecutionResponse with results or error information.
        """
        timeout = timeout_seconds or settings.execution_timeout_seconds

        if not self.is_configured():
            return ExecutionResponse(
                success=False,
                error="Fargate executor not configured",
                error_type="ConfigurationError",
            )

        # Validate code size
        if len(code.encode("utf-8")) > settings.max_code_size_bytes:
            return ExecutionResponse(
                success=False,
                error=f"Code exceeds maximum size of {settings.max_code_size_bytes} bytes",
                error_type="ValidationError",
            )

        start_time = time.time()

        try:
            # Run the ECS task
            response = await asyncio.to_thread(
                self.ecs_client.run_task,
                cluster=self.cluster_arn,
                taskDefinition=self.task_definition_arn,
                launchType="FARGATE",
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": self.subnets,
                        "securityGroups": [self.security_group_id],
                        "assignPublicIp": "DISABLED",
                    }
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": "executor",
                            "environment": [
                                {"name": "CODE_TO_EXECUTE", "value": code},
                                {"name": "TIMEOUT_SECONDS", "value": str(timeout)},
                            ],
                        }
                    ]
                },
            )

            if not response.get("tasks"):
                failures = response.get("failures", [])
                error_msg = (
                    failures[0].get("reason", "Unknown error") if failures else "No tasks started"
                )
                return ExecutionResponse(
                    success=False,
                    error=f"Failed to start Fargate task: {error_msg}",
                    error_type="ExecutionError",
                )

            task_arn = response["tasks"][0]["taskArn"]
            logger.info(f"Started Fargate task: {task_arn}")

            # Wait for task completion
            result = await self._wait_for_task(task_arn, timeout)

            execution_time_ms = int((time.time() - start_time) * 1000)
            result["execution_time_ms"] = execution_time_ms

            return ExecutionResponse(**result)

        except Exception as e:
            logger.exception("Error executing code in Fargate")
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResponse(
                success=False,
                error=str(e),
                error_type="ExecutionError",
                execution_time_ms=execution_time_ms,
            )

    async def _wait_for_task(self, task_arn: str, timeout: float) -> dict[str, Any]:
        """Wait for a Fargate task to complete and get its output.

        Args:
            task_arn: The ARN of the task to wait for.
            timeout: Maximum time to wait.

        Returns:
            Dict with execution results.
        """
        start_time = time.time()
        poll_interval = 1.0  # seconds

        while time.time() - start_time < timeout + 30:  # Extra buffer for task startup
            try:
                response = await asyncio.to_thread(
                    self.ecs_client.describe_tasks,
                    cluster=self.cluster_arn,
                    tasks=[task_arn],
                )

                if not response.get("tasks"):
                    await asyncio.sleep(poll_interval)
                    continue

                task = response["tasks"][0]
                status = task.get("lastStatus", "UNKNOWN")

                if status == "STOPPED":
                    # Task completed - get results from logs or exit code
                    container = task.get("containers", [{}])[0]
                    exit_code = container.get("exitCode", -1)

                    # Try to get output from CloudWatch logs
                    stdout, stderr = await self._get_task_logs(task_arn)

                    return {
                        "success": exit_code == 0,
                        "stdout": stdout,
                        "stderr": stderr,
                        "error": None if exit_code == 0 else f"Exit code: {exit_code}",
                        "error_type": None if exit_code == 0 else "RuntimeError",
                        "timed_out": False,
                        "security_violations": [],
                    }

                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.warning(f"Error polling task status: {e}")
                await asyncio.sleep(poll_interval)

        # Timeout - stop the task
        try:
            await asyncio.to_thread(
                self.ecs_client.stop_task,
                cluster=self.cluster_arn,
                task=task_arn,
                reason="Execution timeout",
            )
        except Exception:
            pass

        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": f"Execution timed out after {timeout} seconds",
            "error_type": "TimeoutError",
            "timed_out": True,
            "security_violations": [],
        }

    async def _get_task_logs(self, task_arn: str) -> tuple[str, str]:
        """Get stdout/stderr from CloudWatch logs.

        Args:
            task_arn: The ARN of the task.

        Returns:
            Tuple of (stdout, stderr).
        """
        # Extract task ID from ARN
        task_id = task_arn.split("/")[-1]
        log_group = "/ecs/code-remote-dev-executor"  # Matches Fargate component

        stdout_lines = []
        stderr_lines = []

        try:
            # Get log streams for this task
            log_stream_prefix = f"executor/executor/{task_id}"

            response = await asyncio.to_thread(
                self.logs_client.filter_log_events,
                logGroupName=log_group,
                logStreamNamePrefix=log_stream_prefix,
                limit=1000,
            )

            for event in response.get("events", []):
                message = event.get("message", "")
                # Simple heuristic: lines starting with ERROR or containing Exception go to stderr
                if "ERROR" in message or "Exception" in message or "Traceback" in message:
                    stderr_lines.append(message)
                else:
                    stdout_lines.append(message)

        except Exception as e:
            logger.warning(f"Failed to get task logs: {e}")

        return "\n".join(stdout_lines), "\n".join(stderr_lines)


# Singleton instance
_fargate_executor: FargateExecutorService | None = None


def get_fargate_executor() -> FargateExecutorService:
    """Get the Fargate executor service instance."""
    global _fargate_executor
    if _fargate_executor is None:
        _fargate_executor = FargateExecutorService()
    return _fargate_executor
