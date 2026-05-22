import json
from typing import Dict, Any, List
from app.services.llm import get_llm_provider
from loguru import logger

class MetadataExtractor:
    def __init__(self):
        self.llm = get_llm_provider()

    async def extract_metadata(self, document_text: str, filename: str) -> Dict[str, Any]:
        """
        Extracts summary, key concepts, and structure metadata from a document.
        Uses LLM provider to structure the extracted data.
        """
        # Trim text to prevent token overflow during metadata extraction
        sample_text = document_text[:6000] 
        
        system_instruction = (
            "You are an AI document metadata extraction system. Analyze the document snippet "
            "and output a JSON response containing fields: 'summary' (str), 'key_concepts' (list of str), "
            "'suggested_title' (str), and 'topics' (list of str). Output ONLY raw JSON."
        )
        
        prompt = f"Document filename: {filename}\nContent:\n{sample_text}"
        
        try:
            raw_response = await self.llm.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1
            )
            # Remove markdown backticks if returned
            clean_response = raw_response.strip().replace("```json", "").replace("```", "").strip()
            metadata = json.loads(clean_response)
            logger.info(f"Successfully extracted metadata for document: {filename}")
            return metadata
        except Exception as e:
            logger.warning(f"Failed to extract metadata using LLM for {filename}: {e}. Falling back to default.")
            return {
                "summary": "Document content summary unavailable.",
                "key_concepts": ["Exam study material"],
                "suggested_title": filename,
                "topics": ["General Study"]
            }
