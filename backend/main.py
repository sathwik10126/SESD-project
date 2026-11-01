from contextlib import asynccontextmanager
from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.database import initialize_database
from app.routers import admin, answers, auth, help_requests, notices, procedures, questions, resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not initialize_database():
        raise RuntimeError(
            "EduLink database initialization failed. Check DATABASE_URL and database availability."
        )
    yield


app = FastAPI(
    title="EduLink API",
    description="Smart Student Help & Information Hub",
    version="5.0.0",
    lifespan=lifespan,
)

default_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]
configured_origins = [
    item.strip()
    for item in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if item.strip()
]
frontend_origins = configured_origins or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core routes (used directly by script.js: /auth, /questions, /resources, etc.)
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(answers.router)
app.include_router(resources.router)
app.include_router(notices.router)
app.include_router(procedures.router)
app.include_router(help_requests.router)
app.include_router(admin.router)

# Aliased with /api prefix for full backwards compatibility
app.include_router(auth.router, prefix="/api", include_in_schema=False)
app.include_router(questions.router, prefix="/api", include_in_schema=False)
app.include_router(answers.router, prefix="/api", include_in_schema=False)
app.include_router(resources.router, prefix="/api", include_in_schema=False)
app.include_router(notices.router, prefix="/api", include_in_schema=False)
app.include_router(procedures.router, prefix="/api", include_in_schema=False)
app.include_router(help_requests.router, prefix="/api", include_in_schema=False)
app.include_router(admin.router, prefix="/api", include_in_schema=False)


@app.get("/")
def root():
    return {
        "message": "EduLink API is running",
        "version": "5.0.0",
        "docs": "/docs",
    }


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "healthy"}
