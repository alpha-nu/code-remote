"""
Executor Worker - Processes code execution requests from the job queue.

This worker runs inside isolated containers and processes execution
requests one at a time for maximum security isolation.
"""

import asyncio
import json
import os
import signal
import sys
from typing import NoReturn

from common.logging import get_logger
from executor.models import ExecutionRequest
from executor.runner import PythonRunner

logger = get_logger(__name__)


class ExecutorWorker:
    """
    Worker process that handles code execution requests.

    In production, this listens to a Redis/SQS queue for jobs.
    Each execution happens in a fresh process for isolation.
    """

    def __init__(self) -> None:
        self.runner = PythonRunner()
        self.running = True
        self.debug = os.getenv("EXECUTOR_DEBUG", "false").lower() == "true"

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def process_request(self, request_data: dict) -> dict:
        """
        Process a single execution request.

        Args:
            request_data: Dictionary containing 'code' and optional 'timeout'

        Returns:
            Dictionary with execution results
        """
        try:
            request = ExecutionRequest(
                code=request_data.get("code", ""),
                timeout=request_data.get("timeout", 30),
            )

            logger.info(f"Executing code (length={len(request.code)})")
            result = await self.runner.execute(request)

            return {
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "execution_time": result.execution_time,
            }

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time": 0.0,
            }

    async def run_stdin_mode(self) -> NoReturn:
        """
        Run in stdin mode - read requests from stdin, write results to stdout.

        This mode is used when the executor is invoked directly by the API
        (e.g., via kubectl exec or direct container invocation).
        """
        logger.info("Starting executor in stdin mode")

        while self.running:
            try:
                # Read a single line from stdin
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

                if not line:
                    break

                request_data = json.loads(line.strip())
                result = await self.process_request(request_data)

                # Write result to stdout
                print(json.dumps(result), flush=True)

            except json.JSONDecodeError as e:
                error_result = {
                    "success": False,
                    "output": "",
                    "error": f"Invalid JSON: {e}",
                    "execution_time": 0.0,
                }
                print(json.dumps(error_result), flush=True)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                if self.debug:
                    raise

    async def run_queue_mode(self) -> NoReturn:
        """
        Run in queue mode - poll a job queue for execution requests.

        This is the primary production mode where the worker continuously
        polls Redis/SQS for new execution jobs.
        """
        logger.info("Starting executor in queue mode")

        # In production, this would connect to Redis/SQS
        # For now, we just wait and handle shutdown
        while self.running:
            await asyncio.sleep(1)
            # TODO: Implement queue polling
            # - Connect to Redis/SQS
            # - Receive message with execution request
            # - Process request
            # - Send result back
            # - Acknowledge message

        logger.info("Queue worker shutdown complete")

    async def run(self) -> None:
        """Start the worker in the appropriate mode."""
        mode = os.getenv("EXECUTOR_MODE", "stdin")

        if mode == "stdin":
            await self.run_stdin_mode()
        elif mode == "queue":
            await self.run_queue_mode()
        else:
            logger.error(f"Unknown executor mode: {mode}")
            sys.exit(1)


def main() -> None:
    """Entry point for the executor worker."""
    logger.info("Executor worker starting...")

    worker = ExecutorWorker()

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)

    logger.info("Executor worker stopped")


if __name__ == "__main__":
    main()
