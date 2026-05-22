import os
from typing import List, Dict, Any
from app.utils.parsers.base import BaseParser
from loguru import logger

try:
    import pdf2image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

class PDFParser(BaseParser):
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing PDF file: {file_path}")
        results = []
        pypdf_results = []
        
        # 1. Try extracting text using PyPDF
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            total_text = ""
            
            for i, page in enumerate(reader.pages):
                page_num = i + 1
                text = page.extract_text() or ""
                cleaned_text = text.strip()
                total_text += cleaned_text
                
                # Split paragraphs by double newlines
                paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
                
                pypdf_results.append({
                    "content": cleaned_text,
                    "page_number": page_num,
                    "char_start": 0,
                    "char_end": len(cleaned_text),
                    "paragraph_references": paragraphs
                })
                
            # If we successfully extracted text and it is not an empty/scanned PDF
            if len(total_text.strip()) >= 100:
                logger.info(f"Successfully extracted {len(total_text)} characters using PyPDF.")
                return pypdf_results
                
            logger.info("Extracted text is empty or very short (<100 chars). Attempting OCR fallback.")
            
        except Exception as e:
            logger.error(f"Error during PyPDF extraction: {e}. Trying OCR fallback.")

        # 2. OCR Fallback
        if not HAS_OCR:
            logger.warning("OCR packages (pytesseract/pdf2image) are not installed or importable. Returning partial results.")
            return pypdf_results if pypdf_results else []
            
        try:
            # Convert PDF pages to images. Gracefully handle poppler missing errors.
            images = pdf2image.convert_from_path(file_path)
            ocr_results = []
            logger.info(f"Converted PDF to {len(images)} images. Starting pytesseract OCR...")
            
            for i, image in enumerate(images):
                page_num = i + 1
                text = pytesseract.image_to_string(image)
                cleaned_text = text.strip()
                paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
                
                ocr_results.append({
                    "content": cleaned_text,
                    "page_number": page_num,
                    "char_start": 0,
                    "char_end": len(cleaned_text),
                    "paragraph_references": paragraphs
                })
            
            logger.info(f"Successfully OCRed {len(ocr_results)} pages.")
            return ocr_results
            
        except Exception as ocr_err:
            logger.error(f"OCR fallback failed (likely missing system binaries poppler/tesseract): {ocr_err}")
            # Graceful fallback: return whatever pypdf got, or empty
            return pypdf_results if pypdf_results else []
