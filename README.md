# EduLink backend

The FastAPI backend runs locally on your laptop. See the repository root `README.md` for the complete GitHub Pages + local FastAPI + Docker PostgreSQL setup.

Quick start (PowerShell, from this `backend` directory):

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start PostgreSQL first from the repository root with `docker compose up -d postgres`. Edit `.env` and set a private `SECRET_KEY`. Never commit `.env`.
