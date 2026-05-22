from typing import List, Dict, Any
from app.utils.parsers.base import BaseParser
from loguru import logger

class DOCXParser(BaseParser):
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing DOCX file: {file_path}")
        results = []
        
        try:
            from docx import Document
            doc = Document(file_path)
            
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            full_text = "\n\n".join(paragraphs)
            
            # DOCX doesn't have native "pages" in python-docx easily, so we treat the entire document as page 1
            results.append({
                "content": full_text,
                "page_number": 1,
                "char_start": 0,
                "char_end": len(full_text),
                "paragraph_references": paragraphs
            })
            
            logger.info(f"Successfully extracted DOCX file: {file_path}")
            return results
            
        except Exception as e:
            logger.error(f"Error parsing DOCX file {file_path}: {e}")
            raise e
