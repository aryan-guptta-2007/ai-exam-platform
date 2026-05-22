import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.cost import CostRecord
from loguru import logger

# Token pricing estimates (per 1,000,000 tokens)
PRICING_TABLE = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 5.00, "completion": 15.00},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
}

class CostMonitor:
    def __init__(self):
        pass

    def calculate_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculates LLM invocation cost in USD.
        """
        # Clean model name mapping
        clean_name = model_name.lower()
        pricing = PRICING_TABLE.get(clean_name)
        
        # Default fallback pricing (GPT-4o Mini pricing if unknown)
        if not pricing:
            for k in PRICING_TABLE:
                if k in clean_name:
                    pricing = PRICING_TABLE[k]
                    break
            if not pricing:
                pricing = PRICING_TABLE["gpt-4o-mini"]
                
        prompt_cost = (prompt_tokens / 1_000_000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * pricing["completion"]
        
        return prompt_cost + completion_cost

    async def log_cost(
        self, 
        session: AsyncSession, 
        user_id: uuid.UUID, 
        model_name: str, 
        prompt_tokens: int, 
        completion_tokens: int,
        task_name: str = "general"
    ) -> CostRecord:
        """
        Calculates and commits cost record to the database.
        """
        estimated_cost = self.calculate_cost(model_name, prompt_tokens, completion_tokens)
        
        record = CostRecord(
            user_id=user_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimated_cost,
            task_name=task_name
        )
        
        try:
            session.add(record)
            await session.commit()
            logger.info(f"Logged cost record: {estimated_cost:.6f} USD for task '{task_name}' on model '{model_name}'")
            return record
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to log cost record to database: {e}")
            raise e

cost_monitor = CostMonitor()
