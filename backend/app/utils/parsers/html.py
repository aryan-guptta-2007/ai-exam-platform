from typing import List, Dict, Any
from html.parser import HTMLParser
from app.utils.parsers.base import BaseParser
from loguru import logger

class StripHTMLTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
        
    def handle_data(self, d):
        self.fed.append(d)
        
    def get_data(self):
        return "".join(self.fed)

class HTMLParserService(BaseParser):
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing HTML file: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()
                
            parser = StripHTMLTags()
            parser.feed(html_content)
            plain_text = parser.get_data().strip()
            
            # Split by double newline for paragraph references
            paragraphs = [p.strip() for p in plain_text.split("\n\n") if p.strip()]
            
            return [{
                "content": plain_text,
                "page_number": 1,
                "char_start": 0,
                "char_end": len(plain_text),
                "paragraph_references": paragraphs
            }]
            
        except Exception as e:
            logger.error(f"Error parsing HTML file {file_path}: {e}")
            raise e
