"""Revocation Registry Manager."""

import asyncio

from shared.log_config import get_logger

logger = get_logger(__name__)


class RevRegManager:
    """Manages automatic creation of revocation registries."""

    def __init__(
        self,
    ) -> None:
        """Initialize the revocation processor."""
        self._background_tasks: set[asyncio.Task] = set()
        self._stop_event = asyncio.Event()

    async def start_background_processing(self) -> None:
        """Start background processing tasks."""
        logger.info("Starting background processing tasks")

    async def stop_background_processing(self) -> None:
        """Stop background processing tasks."""
        logger.info("Stopping background processing tasks")
        self._stop_event.set()

        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for all tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()
