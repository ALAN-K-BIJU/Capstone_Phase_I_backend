# core/identifier.py
import os
import json
import google.generativeai as genai
from PIL import Image
from typing import List, Dict, Any

# --- Configuration ---
try:
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
except Exception as e:
    print(f"FATAL: Could not configure Google AI. Check GOOGLE_API_KEY: {e}")

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
model = genai.GenerativeModel('gemini-1.5-flash-latest', safety_settings=safety_settings)

SEVERITY_MAPPING = {
    0: [],
    20: ["CREDIT_CARD", "SSN"],
    40: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER"],
    60: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER", "PERSON"],
    80: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER", "PERSON", "GPE", "DATE"],
    100: ["ALL_POSSIBLE_PII"],
}


def identify_pii_text_with_vision(image_path: str, severity: int) -> List[Dict[str, str]]:
    """
    Identifies PII text from an image using Gemini Vision.
    This version DOES NOT ask for bounding boxes, only for the text and label.
    """
    pii_to_find = SEVERITY_MAPPING.get(severity)
    if not pii_to_find:
        return []

    pii_list_str = ", ".join(pii_to_find)
    if "ALL_POSSIBLE_PII" in pii_list_str:
        pii_list_str = "all possible PII..."

    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"Could not open image file at {image_path}: {e}")
        return []
        
    prompt = f"""
    You are an expert data security analyst. Analyze the provided document image and identify all instances of the following PII types: [{pii_list_str}].

    You must respond ONLY with a valid JSON object. Do not include markdown or explanations.
    The JSON object must be a list of PII objects. Each object MUST have these exact keys:
    - "text": The exact text of the PII identified.
    - "label": The category of the PII (e.g., "PERSON", "PNR").

    Example of a valid response:
    [
      {{"text": "John Doe", "label": "PERSON"}},
      {{"text": "test@example.com", "label": "EMAIL"}}
    ]
    """

    try:
        response = model.generate_content([prompt, image], stream=False)
        response_text = response.text
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json\n").strip("`\n")
            
        pii_list = json.loads(response_text)
        return pii_list

    except Exception as e:
        print(f"An error occurred with the Google Gemini API call: {e}")
        return []

find_pii = identify_pii_text_with_vision