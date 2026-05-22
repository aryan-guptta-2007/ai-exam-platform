from typing import Dict, Any
from app.prompts import v1
from loguru import logger

class PromptManager:
    """
    Centralized system to fetch versioned prompts.
    Useful for running A/B tests or swapping prompts on-the-fly.
    """
    def __init__(self):
        self._versions: Dict[str, Any] = {
            "v1": v1
        }

    def get_prompt(self, key: str, version: str = "v1") -> str:
        """
        Retrieves a prompt template by key and version.
        """
        ver_module = self._versions.get(version)
        if not ver_module:
            logger.warning(f"Requested prompt version '{version}' not found. Defaulting to 'v1'.")
            ver_module = self._versions["v1"]

        # Try to read matching constant from module
        prompt_val = getattr(ver_module, key, None)
        if not prompt_val:
            raise KeyError(f"Prompt template '{key}' not found in version '{version}'.")
            
        return prompt_val

prompt_manager = PromptManager()
