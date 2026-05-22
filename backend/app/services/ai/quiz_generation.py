import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import get_llm_provider
from app.services.ai.retrieval import retrieval_service
from loguru import logger

class QuizGenerationService:
    def __init__(self):
        self.llm = get_llm_provider()

    async def generate_quiz(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
        topic: str,
        num_questions: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generates simple check-your-understanding quizzes.
        """
        logger.info(f"Generating quiz on '{topic}' for doc {document_id}")
        context = await retrieval_service.retrieve_context(session, topic, document_id, limit=3)
        
        system_instruction = "You are a teacher producing multiple choice questions in JSON."
        prompt = (
            f"Write a {num_questions}-question multiple choice quiz on '{topic}' using this context:\n"
            f"{context}\n\n"
            f"Response MUST be a JSON array. Format:\n"
            f"[\n"
            f"  {{\n"
            f"    \"question\": \"Question string\",\n"
            f"    \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"],\n"
            f"    \"correct_option\": 0\n"
            f"  }}\n"
            f"]"
        )
        
        try:
            raw_response = await self.llm.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.3
            )
            clean = raw_response.strip().replace("```json", "").replace("```", "").strip()
            import json
            return json.loads(clean)
        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")
            return []

quiz_generation_service = QuizGenerationService()
