import abc
from typing import List, Dict, Any

class BaseParser(abc.ABC):
    @abc.abstractmethod
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parses a file and returns a list of dictionaries with structure:
        [
            {
                "content": str,
                "page_number": int,                # 1-based index
                "char_start": int,                 # start character offset (in page/slide context)
                "char_end": int,                   # end character offset (in page/slide context)
                "paragraph_references": List[str]  # list of paragraphs or lines on this page
            }
        ]
        """
        pass
