# main.py
from core.redis_client import redis_client
import json # We need this to serialize/deserialize our metadata

import os
import shutil
import uuid
from base64 import urlsafe_b64encode, urlsafe_b64decode
from typing import Dict, List, Any

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# --- Import BOTH engine workflows ---
from core.engine import process_document_llm, process_document_classic, unredact_document
from core.security import generate_key, decrypt_text

app = FastAPI(title="Dual-Engine Document Redaction Service")
# Immediately after app = FastAPI(...)
if redis_client is None:
    print("Shutting down due to Redis connection failure.")
    exit()
# ... (Directories and Data Store remain the same) ...
TEMP_UPLOADS_DIR = "temp_uploads"
REDACTED_FILES_DIR = "redacted_files"
os.makedirs(TEMP_UPLOADS_DIR, exist_ok=True)
os.makedirs(REDACTED_FILES_DIR, exist_ok=True)

# ... (Pydantic models remain the same) ...
class DecryptionRequest(BaseModel):
    document_id: str
    decryption_key: str
class DecryptedPiiItem(BaseModel):
    text: str
    bbox: List[float]
class DecryptionResponse(BaseModel):
    document_id: str
    pages: Dict[str, List[DecryptedPiiItem]]

# ... (cleanup_files helper remains the same) ...
def cleanup_files(files: list):
    for file_path in files:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- Redaction Endpoints ---

@app.post("/redact-llm/", summary="[Advanced] Redact using LLM Vision", tags=["Redaction"])
async def redact_llm_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    severity: int = Form(...)
) -> FileResponse:
    """
    Redacts a document using the advanced LLM Vision engine for the highest accuracy.
    This method is slower and relies on the external Gemini API.
    """
    # ... (This logic is mostly the same, just calls the llm engine function) ...
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    input_path = os.path.join(TEMP_UPLOADS_DIR, unique_filename)
    with open(input_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
    key, document_id = generate_key(), str(uuid.uuid4())
    
    try:
        redacted_file_path, encrypted_metadata = process_document_llm(input_path, severity, key)
        if encrypted_metadata:
            # Convert dict to JSON string and store in Redis with a 24-hour expiry
            redis_client.set(document_id, json.dumps(encrypted_metadata), ex=86400)

        background_tasks.add_task(cleanup_files, [input_path, redacted_file_path])
        headers = {
            "X-Document-ID": document_id,
            "X-Decryption-Key": urlsafe_b64encode(key).decode('utf-8')
        }
        return FileResponse(path=redacted_file_path, media_type=file.content_type, filename=os.path.basename(redacted_file_path), headers=headers)
    except Exception as e:
        background_tasks.add_task(cleanup_files, [input_path])
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/redact-classic/", summary="[Fast] Redact using Classic Engine", tags=["Redaction"])
async def redact_classic_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    severity: int = Form(...)
) -> FileResponse:
    """
    Redacts a document using the fast, local classic engine (Regex + spaCy NER).
    This method is much faster and runs entirely locally, but may be less accurate on complex documents.
    """
    # ... (This logic is identical, but calls the classic engine function) ...
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    input_path = os.path.join(TEMP_UPLOADS_DIR, unique_filename)
    with open(input_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
    key, document_id = generate_key(), str(uuid.uuid4())
    
    try:
        redacted_file_path, encrypted_metadata = process_document_classic(input_path, severity, key)
        if encrypted_metadata:
            # Convert dict to JSON string and store in Redis with a 24-hour expiry
            redis_client.set(document_id, json.dumps(encrypted_metadata), ex=86400)
        background_tasks.add_task(cleanup_files, [input_path, redacted_file_path])
        headers = {
            "X-Document-ID": document_id,
            "X-Decryption-Key": urlsafe_b64encode(key).decode('utf-8')
        }
        return FileResponse(path=redacted_file_path, media_type=file.content_type, filename=os.path.basename(redacted_file_path), headers=headers)
    except Exception as e:
        background_tasks.add_task(cleanup_files, [input_path])
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


# --- Decryption Endpoint (no changes needed) ---
@app.post("/decrypt/", response_model=DecryptionResponse, summary="Decrypt content from any redacted document", tags=["Decryption"])
async def decrypt_endpoint(request: DecryptionRequest):
    # ... (This endpoint works for documents redacted by either engine, no changes needed!) ...
    document_id = request.document_id
    key_b64 = request.decryption_key
    encrypted_data = ENCRYPTED_DATA_STORE.get(document_id)
    if not encrypted_data: raise HTTPException(status_code=404, detail="Document ID not found.")
    try:
        key = urlsafe_b64decode(key_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid decryption key format.")
    decrypted_data = {"document_id": document_id, "pages": {}}
    try:
        for page_num, pii_items in encrypted_data.get("pages", {}).items():
            decrypted_data["pages"][page_num] = []
            for item in pii_items:
                decrypted_text = decrypt_text(key, item["encrypted_text"].encode('utf-8'))
                decrypted_pii_item = DecryptedPiiItem(text=decrypted_text, bbox=item["bbox"])
                decrypted_data["pages"][page_num].append(decrypted_pii_item)
        return DecryptionResponse(**decrypted_data)
    except ValueError:
        raise HTTPException(status_code=403, detail="Decryption failed. The provided key is incorrect.")

# ... (unredact endpoint can also remain, it will work with either method's output) ...

@app.post("/unredact/", summary="Restore a redacted document", tags=["Decryption"])
async def unredact_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="The redacted document file you want to restore."),
    document_id: str = Form(..., description="The unique ID of the document."),
    decryption_key: str = Form(..., description="The one-time decryption key.")
) -> FileResponse:
    """
    Upload a redacted document along with its ID and key to get the original version back.
    """
    # 1. Retrieve the stored encrypted data
    encrypted_metadata_json = redis_client.get(document_id)
    if not encrypted_metadata_json:
        raise HTTPException(status_code=404, detail="Document ID not found or has expired.")
    encrypted_metadata = json.loads(encrypted_metadata_json)
    try:
        key = urlsafe_b64decode(decryption_key)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid decryption key format.")

    # 2. Save the uploaded redacted file temporarily
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_redacted_path = os.path.join(TEMP_UPLOADS_DIR, unique_filename)

    with open(temp_redacted_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 3. Call the engine to perform the un-redaction
        restored_file_path = unredact_document(temp_redacted_path, key, encrypted_metadata)
        
        # 4. Schedule cleanup and return the restored file
        background_tasks.add_task(cleanup_files, [temp_redacted_path, restored_file_path])
        
        return FileResponse(
            path=restored_file_path,
            media_type=file.content_type,
            filename=f"restored_{file.filename.replace('redacted_', '')}"
        )
    except Exception as e:
        background_tasks.add_task(cleanup_files, [temp_redacted_path])
        raise HTTPException(status_code=500, detail=f"An error occurred during un-redaction: {str(e)}")