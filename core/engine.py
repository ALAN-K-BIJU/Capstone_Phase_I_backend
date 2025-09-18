# core/engine.py
import os
import shutil
import fitz  # PyMuPDF
from typing import Dict, Any, Tuple

from .security import decrypt_text, encrypt_text
from .redactor import redact_pdf, redact_image, write_on_image, write_on_pdf
from .extractor import extract_from_pdf, extract_from_image

# --- Import BOTH identifier modules ---
from .identifier_llm import find_pii as find_pii_llm
from .identifier_classic import find_pii_classic

API_CALL_DELAY_SECONDS = 5

# --- WORKFLOW 1: LLM-based (Hybrid Vision + OCR) ---
def process_document_llm(file_path: str, severity: int, encryption_key: bytes) -> Tuple[str, Dict[str, Any]]:
    # This is the advanced hybrid approach from our last step
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == ".pdf":
        ocr_pages_data = extract_from_pdf(file_path)
    elif file_extension in [".png", ".jpg", ".jpeg", "tiff"]:
        ocr_pages_data = extract_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    page_images = []
    temp_image_dir = "temp_page_images"
    os.makedirs(temp_image_dir, exist_ok=True)
    if file_extension == ".pdf":
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            image_path = os.path.join(temp_image_dir, f"page_{i}.png")
            pix.save(image_path)
            page_images.append((i, image_path))
        doc.close()
    else:
        page_images.append((0, file_path))

    redaction_visuals = []
    encrypted_metadata = {"pages": {}}

    for i, (page_num, image_path) in enumerate(page_images):
        print(f"Processing page {page_num+1}/{len(page_images)} with LLM...")
        ocr_words_on_page = ocr_pages_data[page_num]["words"]
        pii_text_list = find_pii_llm(image_path, severity)
        
        if not pii_text_list: continue
        encrypted_metadata["pages"][str(page_num)] = []

        for pii in pii_text_list:
            pii_plaintext = pii.get("text")
            if not pii_plaintext: continue
            pii_words = pii_plaintext.split()
            found_bboxes = []
            for i in range(len(ocr_words_on_page) - len(pii_words) + 1):
                is_match = all(ocr_words_on_page[i+j][4] == pii_words[j] for j in range(len(pii_words)))
                if is_match:
                    found_bboxes = [fitz.Rect(ocr_words_on_page[i+j][:4]) for j in range(len(pii_words))]
                    break
            if found_bboxes:
                final_bbox = fitz.Rect()
                for bbox in found_bboxes: final_bbox.include_rect(bbox)
                encrypted_text = encrypt_text(encryption_key, pii_plaintext)
                encrypted_metadata["pages"][str(page_num)].append({
                    "encrypted_text": encrypted_text.decode('utf-8'),
                    "bbox": [final_bbox.x0, final_bbox.y0, final_bbox.x1, final_bbox.y1]
                })
                redaction_visuals.append((page_num, final_bbox) if file_extension == ".pdf" else final_bbox)
        
        if i < len(page_images) - 1:
            print(f"Waiting for {API_CALL_DELAY_SECONDS} seconds...")
            time.sleep(API_CALL_DELAY_SECONDS)

    if os.path.exists(temp_image_dir): shutil.rmtree(temp_image_dir)
    
    # ... (Rest of redaction logic is the same, simplified for brevity)
    if not redaction_visuals: return file_path, {}
    output_dir, base_filename = "redacted_files", os.path.basename(file_path)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"redacted_llm_{base_filename}")
    if file_extension == ".pdf": redact_pdf(file_path, redaction_visuals, output_path)
    else: redact_image(file_path, redaction_visuals, output_path)
    return output_path, encrypted_metadata


# --- WORKFLOW 2: Classic (Regex + spaCy) ---
def process_document_classic(file_path: str, severity: int, encryption_key: bytes) -> Tuple[str, Dict[str, Any]]:
    # This is the original text-based mapping approach
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == ".pdf":
        pages_data = extract_from_pdf(file_path)
    elif file_extension in [".png", ".jpg", ".jpeg", "tiff"]:
        pages_data = extract_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    redaction_visuals = []
    encrypted_metadata = {"pages": {}}

    for page_data in pages_data:
        page_num = page_data["page"]
        words = page_data["words"]
        full_text = " ".join([word[4] for word in words])
        
        pii_locations = find_pii_classic(full_text, severity)
        if not pii_locations: continue
        encrypted_metadata["pages"][str(page_num)] = []

        char_offset, word_indices = 0, {}
        for i, word_info in enumerate(words):
            start, end = char_offset, char_offset + len(word_info[4])
            word_indices[i] = {'start': start, 'end': end, 'bbox': fitz.Rect(word_info[0:4]), 'text': word_info[4]}
            char_offset = end + 1

        for pii in pii_locations:
            pii_start, pii_end = pii['start'], pii['end']
            pii_words_bboxes, pii_plaintext_parts = [], []
            for i, word_info in word_indices.items():
                if max(pii_start, word_info['start']) < min(pii_end, word_info['end']):
                    pii_words_bboxes.append(word_info['bbox'])
                    pii_plaintext_parts.append(word_info['text'])
            if pii_words_bboxes:
                final_bbox = fitz.Rect()
                for bbox in pii_words_bboxes: final_bbox.include_rect(bbox)
                pii_plaintext = " ".join(pii_plaintext_parts)
                encrypted_text = encrypt_text(encryption_key, pii_plaintext)
                encrypted_metadata["pages"][str(page_num)].append({
                    "encrypted_text": encrypted_text.decode('utf-8'),
                    "bbox": [final_bbox.x0, final_bbox.y0, final_bbox.x1, final_bbox.y1]
                })
                redaction_visuals.append((page_num, final_bbox) if file_extension == ".pdf" else final_bbox)

    if not redaction_visuals: return file_path, {}
    output_dir, base_filename = "redacted_files", os.path.basename(file_path)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"redacted_classic_{base_filename}")
    if file_extension == ".pdf": redact_pdf(file_path, redaction_visuals, output_path)
    else: redact_image(file_path, redaction_visuals, output_path)
    return output_path, encrypted_metadata

def unredact_document(redacted_file_path: str, encryption_key: bytes, encrypted_metadata: Dict[str, Any]) -> str:
    """
    Orchestrates the process of writing decrypted text back onto a redacted document.
    Returns the path to the fully restored file.
    """
    file_extension = os.path.splitext(redacted_file_path)[1].lower()
    
    restored_data_for_writer = []
    
    # Decrypt all the PII first
    for page_num, pii_items in encrypted_metadata.get("pages", {}).items():
        for item in pii_items:
            try:
                decrypted_text = decrypt_text(encryption_key, item["encrypted_text"].encode('utf-8'))
                bbox = item["bbox"]
                if file_extension == ".pdf":
                    restored_data_for_writer.append((int(page_num), bbox, decrypted_text))
                else:
                    restored_data_for_writer.append((bbox, decrypted_text))
            except ValueError:
                # Handle cases where decryption might fail for a specific item
                print(f"Warning: Could not decrypt an item on page {page_num}.")
                continue
    
    if not restored_data_for_writer:
        raise ValueError("No data could be decrypted or restored.")

    # Define where the final output file will be saved
    output_dir = "restored_files"
    os.makedirs(output_dir, exist_ok=True)
    base_filename = os.path.basename(redacted_file_path).replace("redacted_", "")
    output_path = os.path.join(output_dir, f"restored_{base_filename}")
    
    # Call the appropriate writer function from the redactor module
    if file_extension == ".pdf":
        write_on_pdf(redacted_file_path, restored_data_for_writer, output_path)
    elif file_extension in [".png", ".jpg", ".jpeg", ".tiff"]:
        write_on_image(redacted_file_path, restored_data_for_writer, output_path)
    else:
        raise ValueError(f"Unsupported file type for un-redaction: {file_extension}")
        
    return output_path