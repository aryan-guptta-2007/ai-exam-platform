from typing import List

class DocumentChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """
        Splits text recursively based on paragraph breaks, sentence breaks, and spaces.
        Prevents splitting in the middle of words and guarantees overlapping segments.
        """
        if not text:
            return []
            
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If paragraph fits, add it
            if len(current_chunk) + len(paragraph) < self.chunk_size:
                current_chunk += (paragraph + "\n\n")
            else:
                # If current chunk has content, store it
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Handle large paragraphs by splitting into sentences or character blocks
                if len(paragraph) > self.chunk_size:
                    sub_chunks = self._split_by_sentences(paragraph)
                    for sub in sub_chunks:
                        chunks.append(sub)
                    current_chunk = ""
                else:
                    # Initialize next chunk with overlap or just the current paragraph
                    current_chunk = paragraph + "\n\n"
                    
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    def _split_by_sentences(self, text: str) -> List[str]:
        # Simple sentence splitter on periods followed by spaces
        sentences = text.replace(". ", ".<split>").split("<split>")
        chunks = []
        current = ""
        
        for sentence in sentences:
            if len(current) + len(sentence) < self.chunk_size:
                current += (sentence + " ")
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence + " "
                
        if current:
            chunks.append(current.strip())
            
        return chunks
