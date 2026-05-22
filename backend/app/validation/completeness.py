import json
from typing import Dict, List, Any
from loguru import logger

class CompletenessValidator:
    """
    Validates that LLM generations contain all required fields
    and meet structural expectations.
    """
    def __init__(self):
        pass

    def validate_exam_json(self, raw_json_text: str) -> List[Dict[str, Any]]:
        """
        Parses raw text response to verify it is a valid list of questions,
        where each question contains: 'text', 'expected_answer', and 'rubric'.
        Raises ValueError if structural validation fails.
        """
        try:
            # Clean string
            cleaned = raw_json_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            
            if not isinstance(data, list):
                raise ValueError("Generated output is not a JSON list.")
                
            validated_questions = []
            for idx, item in enumerate(data):
                # Enforce fields
                text = item.get("text")
                expected_answer = item.get("expected_answer")
                rubric = item.get("rubric")
                
                if not text or not expected_answer or not rubric:
                    raise ValueError(f"Question at index {idx} is missing required fields (text/expected_answer/rubric).")
                    
                validated_questions.append({
                    "text": str(text),
                    "expected_answer": str(expected_answer),
                    "rubric": str(rubric)
                })
                
            return validated_questions
        except json.JSONDecodeError as je:
            logger.error(f"JSON validation failed: {je}")
            raise ValueError(f"Output is not valid JSON: {je}")
        except Exception as e:
            logger.error(f"Completeness verification error: {e}")
            raise e
