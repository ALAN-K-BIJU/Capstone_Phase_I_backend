# core/extractor.py
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from typing import List, Dict, Any

def extract_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extracts text and bounding boxes from a PDF."""
    document_data = []
    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc):
        # get_text("words") gives us a list of [x0, y0, x1, y1, "word", block_no, line_no, word_no]
        words = page.get_text("words")
        document_data.append({"page": page_num, "words": words})
    return document_data


def extract_from_image(file_path: str) -> List[Dict[str, Any]]:
    """Extracts text and bounding boxes from an image using OCR."""
    try:
        # Use pytesseract to get detailed data about words and their boxes
        data = pytesseract.image_to_data(Image.open(file_path), output_type=pytesseract.Output.DICT)
        words = []
        n_boxes = len(data['level'])
        for i in range(n_boxes):
            if int(data['conf'][i]) > 60: # Only consider words with confidence > 60%
                (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                word = data['text'][i]
                if word.strip():
                    # Format is [x0, y0, x1, y1, "word"]
                    words.append([x, y, x + w, y + h, word])
        
        # Images only have one page
        return [{"page": 0, "words": words}]

    except Exception as e:
        print(f"Error during OCR: {e}")
        return []