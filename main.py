# miktos_backend/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import modules containing routers
from api import endpoints, auth, projects

# Import database configuration and base model
from config.database import get_db, engine, Base

# Create database tables if they don't exist (for development)
# In production, you should use migrations (e.g., Alembic)
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created.")
except Exception as e:
    print(f"Error creating database tables: {e}")

# Initialize the FastAPI app
app = FastAPI(
    title="Miktós AI Orchestrator",
    description="A platform to interact with multiple AI models via a unified interface.",
    version="0.2.0"
)

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Default Vite port
    "http://localhost:5174", # Sometimes Vite uses next port
    "http://localhost:8080", # Common alternative dev port
    "http://localhost",
    # Add your deployed frontend URL here when ready
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# --- Include API routers ---

# General Endpoints Router (e.g., /health, /generate)
# Prefix is applied here because router in endpoints.py might not have it.
app.include_router(
    endpoints.router,
    prefix="/api/v1", # Base prefix for general endpoints
    tags=["General"]   # Tag for docs grouping
)

# Authentication Router
# Assuming prefix "/api/v1/auth" is defined within api/auth.py router itself
app.include_router(auth.router)

# Projects Router
# --- CORRECTION: Add prefix here as it's not defined in api/projects.py ---
app.include_router(
    projects.router,
    prefix="/api/v1/projects", # Apply the correct prefix
    # Tags are already defined in api/projects.py, but specifying here doesn't hurt
    # and can override if needed. Let's keep it consistent with how tags are defined there.
    # tags=["Projects"] # Redundant if already tagged in projects.py
)


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def root():
    """Provides a simple welcome message for the API root."""
    return {"message": "Welcome to Miktós AI Orchestration Platform API"}

# --- (Optional) Health Check Endpoint ---
# Often useful, can be added to endpoints.py or here
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    # Could add DB connection check here if needed
    return {"status": "ok"}