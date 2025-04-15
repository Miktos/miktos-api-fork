# miktos_backend/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import the endpoints module
from miktos_backend.api import endpoints

# Import database dependency - we'll uncomment this after setting up dependencies
# from miktos_backend.dependencies import get_db

# Initialize the FastAPI app
app = FastAPI(
    title="Miktós AI Orchestrator",
    description="A platform to interact with multiple AI models via a unified interface.",
    version="0.1.0-mvp"
)

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include API routers ---
app.include_router(endpoints.router, prefix="/api/v1")

# We'll uncomment auth after setting it up
# app.include_router(auth.router, prefix="/api/v1")

# --- Root Endpoint ---
@app.get("/")
async def root():
    return {"message": "Welcome to Miktós AI Orchestration Platform"}