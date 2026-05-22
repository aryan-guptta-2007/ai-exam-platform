from typing import List, Dict, Any

class DocumentChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_page(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Splits a parsed page text into chunks, preserving page number, char offsets, and paragraph references.
        """
        text = page["content"]
        page_number = page["page_number"]
        paragraphs = page.get("paragraph_references", [])
        
        if not text:
            return []
            
        if len(text) <= self.chunk_size:
            return [{
                "content": text,
                "page_number": page_number,
                "char_start": 0,
                "char_end": len(text),
                "paragraph_references": paragraphs
            }]
            
        # Split page text into sentences/sections
        sentences = text.replace(". ", ".<split>").split("<split>")
        chunks = []
        current_chunk = ""
        current_start = 0
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            if len(current_chunk) + len(sentence) < self.chunk_size:
                current_chunk += (sentence + " ")
            else:
                if current_chunk:
                    chunk_text = current_chunk.strip()
                    # Find paragraph references contained in or overlapping with this chunk
                    matching_paras = [p for p in paragraphs if p in chunk_text or chunk_text in p]
                    chunks.append({
                        "content": chunk_text,
                        "page_number": page_number,
                        "char_start": current_start,
                        "char_end": current_start + len(chunk_text),
                        "paragraph_references": matching_paras
                    })
                current_start = text.find(sentence, current_start)
                if current_start == -1:
                    current_start = 0
                current_chunk = sentence + " "
                
        if current_chunk:
            chunk_text = current_chunk.strip()
            matching_paras = [p for p in paragraphs if p in chunk_text or chunk_text in p]
            chunks.append({
                "content": chunk_text,
                "page_number": page_number,
                "char_start": current_start,
                "char_end": current_start + len(chunk_text),
                "paragraph_references": matching_paras
            })
            
        return chunks

    def chunk_document(self, parsed_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunks an entire parsed document page-by-page.
        """
        all_chunks = []
        for page in parsed_pages:
            chunks = self.split_page(page)
            all_chunks.extend(chunks)
        return all_chunks
