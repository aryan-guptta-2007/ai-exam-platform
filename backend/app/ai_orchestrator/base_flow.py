from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Awaitable
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

class BaseAIWorkflow(ABC):
    """
    Abstract class for complex AI logic flows.
    Handles stage tracking, progress broadcasts, and retries.
    """
    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        pass

    async def broadcast_progress(
        self, 
        progress_cb: Callable[[str, int, str], Awaitable[None]], 
        status: str, 
        percentage: int, 
        message: str
    ) -> None:
        """
        Sends state updates to the calling client (via WebSocket or HTTP polling).
        """
        if progress_cb:
            try:
                await progress_cb(status, percentage, message)
            except Exception as e:
                logger.warning(f"Failed to execute progress callback in flow '{self.workflow_name}': {e}")
                
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def execute_with_retry(self, step_fn: Callable[[], Awaitable[Any]]) -> Any:
        """
        Executes a workflow step function with exponential backoff retry configuration.
        """
        try:
            return await step_fn()
        except Exception as e:
            logger.error(f"Step in workflow '{self.workflow_name}' failed. Retrying... Error: {e}")
            raise e
