# core/identifier_classic.py
import re
import spacy
from typing import List, Dict

# Load the spaCy model once
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'...")
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Define regular expressions for high-confidence PII
REGEX_PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "PHONE": re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "PNR": re.compile(r"\b\d{10}\b"),
    "TRANSACTION_ID": re.compile(r"Transaction ID:\s*(\d+)"),
    "INVOICE_NUMBER": re.compile(r"Invoice Number:\s*([A-Z0-9]+)"),
}

SEVERITY_MAPPING = {
    0: [],
    20: ["CREDIT_CARD", "SSN"],
    40: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER"],
    60: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER", "PERSON"],
    80: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER", "PERSON", "GPE", "DATE"],
    100: ["CREDIT_CARD", "SSN", "EMAIL", "PHONE", "PNR", "TRANSACTION_ID", "INVOICE_NUMBER", "PERSON", "GPE", "DATE", "ORG"],
}

def find_pii_classic(text: str, severity: int) -> List[Dict[str, int]]:
    """
    Finds PII using Regex and spaCy NER.
    """
    pii_to_find = SEVERITY_MAPPING.get(severity, [])
    if not pii_to_find:
        return []

    found_pii = []

    # 1. Regex-based search
    for pii_type, pattern in REGEX_PATTERNS.items():
        if pii_type in pii_to_find:
            for match in pattern.finditer(text):
                try:
                    start, end = match.span(1)
                except IndexError:
                    start, end = match.span()
                found_pii.append({"start": start, "end": end, "label": pii_type})

    # 2. NER-based search using spaCy
    ner_types = [ptype for ptype in pii_to_find if ptype not in REGEX_PATTERNS]
    if ner_types:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ in ner_types:
                found_pii.append({"start": ent.start_char, "end": ent.end_char, "label": ent.label_})

    return found_pii