import os
from typing import Dict, Type
from app.utils.parsers.base import BaseParser
from app.utils.parsers.pdf import PDFParser
from app.utils.parsers.pptx import PPTXParser
from app.utils.parsers.docx import DOCXParser
from app.utils.parsers.txt import TXTParser
from app.utils.parsers.markdown import MarkdownParser
from app.utils.parsers.html import HTMLParserService
from loguru import logger

class ParserFactory:
    _parsers: Dict[str, Type[BaseParser]] = {
        ".pdf": PDFParser,
        ".pptx": PPTXParser,
        ".docx": DOCXParser,
        ".txt": TXTParser,
        ".md": MarkdownParser,
        ".html": HTMLParserService,
        ".htm": HTMLParserService,
    }

    @classmethod
    def get_parser(cls, file_path: str) -> BaseParser:
        _, ext = os.path.splitext(file_path.lower())
        parser_cls = cls._parsers.get(ext)
        
        if not parser_cls:
            logger.warning(f"No custom parser found for extension '{ext}'. Falling back to TXTParser.")
            return TXTParser()
            
        return parser_cls()
