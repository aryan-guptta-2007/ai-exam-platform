from typing import Dict, Any, Optional
from app.core.config import settings
from loguru import logger

class FeatureFlags:
    """
    Manages operational flags. Can be extended to integrate with tools like
    LaunchDarkly, PostHog, or database configurations in production.
    """
    def __init__(self):
        # Default flags loaded from config settings
        self._local_flags = {
            "hybrid_retrieval": settings.USE_HYBRID_RETRIEVAL,
            "hallucination_validation": settings.ENABLE_HALLUCINATION_VALIDATION,
            "detailed_cost_tracking": settings.ENABLE_DETAILED_COST_TRACKING,
            "stream_explanations": True
        }

    def is_enabled(self, flag_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Checks if a feature flag is enabled.
        Context can be used for user-specific targeting (e.g. user_id, tier).
        """
        flag_val = self._local_flags.get(flag_name.lower())
        
        if flag_val is None:
            logger.warning(f"Feature flag '{flag_name}' is not registered. Defaulting to False.")
            return False
            
        # Example targeting rule stub:
        if context and "user_id" in context:
            # We can run targeting strategies, A/B rollouts, etc.
            pass
            
        return flag_val

    def set_flag(self, flag_name: str, value: bool) -> None:
        self._local_flags[flag_name.lower()] = value
        logger.info(f"Local feature flag updated: {flag_name} = {value}")

feature_flags = FeatureFlags()
