import time
from typing import Dict, Any
from loguru import logger

class AnalyticsTracker:
    """
    Tracks application usage, latencies, success rates, and statistics.
    Useful for system diagnostic insights and product metric calculations.
    """
    def __init__(self):
        pass

    def track_pipeline_latency(self, pipeline_name: str, duration_seconds: float, metadata: Dict[str, Any] = None) -> None:
        """
        Logs duration telemetry for async jobs.
        """
        meta_str = f" | Metadata: {metadata}" if metadata else ""
        logger.info(f"[TELEMETRY] Pipeline: {pipeline_name} | Duration: {duration_seconds:.3f}s{meta_str}")

    def track_llm_call(self, model_name: str, duration_seconds: float, success: bool, error: str = "") -> None:
        status = "SUCCESS" if success else f"FAILED ({error})"
        logger.info(f"[TELEMETRY] LLM Call | Model: {model_name} | Duration: {duration_seconds:.3f}s | Status: {status}")

analytics_tracker = AnalyticsTracker()
