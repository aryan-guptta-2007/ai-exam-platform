import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import get_llm_provider
from app.services.ai.retrieval import retrieval_service
from app.prompts.manager import prompt_manager
from app.validation.completeness import CompletenessValidator
from app.validation.hallucination import HallucinationDetector
from app.feature_flags.client import feature_flags
from loguru import logger

class ExamGenerationService:
    def __init__(self):
        self.llm = get_llm_provider("gpt4") # prefer OpenAI for structured reasoning tasks
        self.completeness_validator = CompletenessValidator()
        self.hallucination_detector = HallucinationDetector()

    async def generate_exam(
        self, 
        session: AsyncSession, 
        document_id: uuid.UUID, 
        title: str, 
        num_questions: int = 5,
        topic_focus: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top context for the document and generates a complete,
        validated set of exam questions, expected answers, and grading rubrics.
        """
        logger.info(f"Generating exam: '{title}' from doc {document_id}")
        
        # 1. Retrieve Context (Get broad document text)
        query = topic_focus or "major concepts and core learning points"
        context = await retrieval_service.retrieve_context(session, query, document_id, limit=8)
        
        # 2. Build prompt
        template = prompt_manager.get_prompt("GENERATE_EXAM_PROMPT")
        prompt = template.format(num_questions=num_questions, context=context)
        
        system_instruction = "You are an expert university professor that writes structured exam JSON."
        
        # 3. Call LLM
        raw_response = await self.llm.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.3
        )
        
        # 4. Validate output completeness
        questions = self.completeness_validator.validate_exam_json(raw_response)
        logger.info(f"Completed initial JSON validation. Got {len(questions)} questions.")
        
        # 5. Hallucination checks (if enabled)
        if feature_flags.is_enabled("hallucination_validation"):
            validated_questions = []
            for question in questions:
                # Check expected answer against source context
                content_to_check = f"Question: {question['text']}\nExpected Answer: {question['expected_answer']}"
                detection_result = await self.hallucination_detector.detect_hallucination(
                    generated_text=content_to_check,
                    source_context=context
                )
                
                if detection_result["is_hallucinated"]:
                    logger.warning(
                        f"Hallucination detected in generated question '{question['text'][:40]}...' "
                        f"Score: {detection_result['score']}. Re-evaluating or omitting..."
                    )
                    # For production: we could retry or flag. Here we append with a validation warning in metadata.
                    question["validation_warnings"] = detection_result["reasons"]
                else:
                    question["validation_warnings"] = []
                    
                validated_questions.append(question)
            return validated_questions
            
        return questions

exam_generation_service = ExamGenerationService()
