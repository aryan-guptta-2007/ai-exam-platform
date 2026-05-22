from typing import List, Dict, Any
from app.utils.parsers.base import BaseParser
from loguru import logger

class TXTParser(BaseParser):
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing TXT file: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            cleaned = content.strip()
            # Split by double newline for paragraphs
            paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
            
            return [{
                "content": cleaned,
                "page_number": 1,
                "char_start": 0,
                "char_end": len(cleaned),
                "paragraph_references": paragraphs
            }]
            
        except Exception as e:
            logger.error(f"Error parsing TXT file {file_path}: {e}")
            raise e
