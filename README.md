# FastAPI Project

This project is built using [FastAPI](https://fastapi.tiangolo.com/). Follow the steps below to set up a virtual environment, install dependencies, and run the server locally.

---

## 🚀 Setup Instructions

### 1️⃣ Create and Activate a Virtual Environment

In your project root directory:

#### On **Windows (PowerShell)**
```powershell
python -m venv venv
.env\Scriptsctivate
```

#### On **Linux / macOS**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 2️⃣ Install Dependencies

Make sure your virtual environment is active, then run:

```bash
pip install -r requirements.txt
```

---
### 3️⃣ Set Up Redis with Docker

Using Docker Run
```bash
docker run --name redis-container -d -p 6379:6379 redis:alpine
```

### 3️⃣ Run the FastAPI Server

Use **uvicorn** to run the server:

```bash
uvicorn main:app --reload
```

- `main` → the Python file name (without `.py`)  
- `app` → the FastAPI instance name inside that file  
- `--reload` → enables auto-reload on code changes (useful in development)
## Note - Setup API Key in the environment with var as GOOGLE_API_KEY
If your entry file or app instance has a different name, adjust the command accordingly.

---

## 📂 Project Structure

```
project/
│-- core/
│   ├── __init__.py
│   ├── engine.py
│   ├── extractor.py
│   ├── identifier_classic.py
│   ├── identifier_llrn.py
│   ├── redactor.py
│   ├── redis_client.py
│   └── security.py
│-- redacted_files/
│-- restored_files/
│-- temp_uploads/
│-- .gitignore
│-- main.py
│-- README.md
│-- requirements.txt

---

```
## 🌐 Access the App

Once the server is running, open your browser:

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive API docs (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative docs (ReDoc): [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
