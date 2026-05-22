from typing import Dict, Any, List
from app.services.llm import get_llm_provider
from loguru import logger

class HallucinationDetector:
    """
    Core IP component: Uses LLM-as-a-judge checks to confirm that generated
    answers/explanations contain no ungrounded assertions or hallucinated facts.
    """
    def __init__(self):
        self.llm = get_llm_provider()

    async def detect_hallucination(self, generated_text: str, source_context: str) -> Dict[str, Any]:
        """
        Evaluates the generated text against the reference context.
        Returns a dictionary containing:
            - is_hallucinated: bool
            - score: float (0.0 to 1.0, where 1.0 means fully grounded, 0.0 means complete hallucination)
            - reasons: List[str]
        """
        system_instruction = (
            "You are a strict academic verification assistant. Your job is to verify if a generated explanation "
            "or answer is fully supported by the provided source context. "
            "Analyze the generation line by line and identify any assertions NOT supported by or contradicting the context. "
            "Output a JSON response containing fields: "
            "'is_hallucinated' (bool), 'groundedness_score' (float between 0.0 and 1.0), and 'contradictions' (list of str). "
            "Output ONLY raw JSON."
        )

        prompt = (
            f"SOURCE CONTEXT:\n{source_context}\n\n"
            f"GENERATED CONTENT TO VERIFY:\n{generated_text}"
        )

        try:
            raw_response = await self.llm.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.0 # low temperature for deterministic evaluation
            )
            
            clean = raw_response.strip().replace("```json", "").replace("```", "").strip()
            import json
            result = json.loads(clean)
            
            return {
                "is_hallucinated": result.get("is_hallucinated", False),
                "score": result.get("groundedness_score", 1.0),
                "reasons": result.get("contradictions", [])
            }
        except Exception as e:
            logger.error(f"Error executing hallucination detection check: {e}")
            # Safe fallback: fail open, but log warning
            return {
                "is_hallucinated": False,
                "score": 1.0,
                "reasons": [f"Evaluation error: {e}"]
            }
