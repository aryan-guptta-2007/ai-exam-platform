import uuid
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import get_llm_provider
from app.services.ai.retrieval import retrieval_service
from app.prompts.manager import prompt_manager
from app.analytics.tracker import analytics_tracker
from loguru import logger

class TeachingService:
    def __init__(self):
        self.llm = get_llm_provider()

    async def explain_concept(
        self, 
        session: AsyncSession, 
        concept: str, 
        document_id: Optional[uuid.UUID] = None
    ) -> str:
        """
        Explains a concept with context retrieved from RAG.
        """
        logger.info(f"Explaining concept: '{concept}'")
        
        # 1. Retrieve RAG context
        context = await retrieval_service.retrieve_context(session, concept, document_id, limit=3)
        
        # 2. Build prompt from manager
        template = prompt_manager.get_prompt("EXPLAIN_CONCEPT_PROMPT")
        prompt = template.format(concept=concept, context=context)
        
        # 3. Call LLM
        system_instruction = "You are a friendly and precise academic tutor."
        explanation = await self.llm.generate_text(
            prompt=prompt,
            system_instruction=system_instruction
        )
        
        return explanation

    async def explain_concept_stream(
        self, 
        session: AsyncSession, 
        concept: str, 
        document_id: Optional[uuid.UUID] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streams concept explanation with context retrieved from RAG.
        """
        logger.info(f"Streaming explanation for concept: '{concept}'")
        context = await retrieval_service.retrieve_context(session, concept, document_id, limit=3)
        
        template = prompt_manager.get_prompt("EXPLAIN_CONCEPT_PROMPT")
        prompt = template.format(concept=concept, context=context)
        
        system_instruction = "You are a friendly and precise academic tutor."
        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            system_instruction=system_instruction
        ):
            yield chunk

teaching_service = TeachingService()
