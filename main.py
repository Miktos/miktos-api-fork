# miktos_backend/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import modules containing routers
# Ensure these modules exist and contain correctly configured 'router' objects
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
    version="0.2.0" # Updated version for Phase 2 completion target
)

# --- CORS Middleware ---
# Define allowed origins for your frontend development server(s)
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
    "http://localhost",
    # Add your deployed frontend URL here when ready
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include API routers ---

# General Endpoints Router
# Assumes prefix="/api/v1" is needed here because paths like "/health"
# are defined directly in endpoints.router without a prefix.
# Tags defined here.
app.include_router(
    endpoints.router,
    prefix="/api/v1",
    tags=["General"]
)

# Authentication Router
# Assumes prefix="/api/v1/auth" and tags=["Authentication"]
# are defined INSIDE api/auth.py on its APIRouter.
# Include without prefix or tags here.
app.include_router(auth.router)

# Projects Router
# Assumes prefix="/api/v1/projects" and tags=["Projects"]
# are defined INSIDE api/projects.py on its APIRouter.
# Include without prefix or tags here.
app.include_router(projects.router) # <-- REMOVED tags=["Projects"]


# --- Root Endpoint ---
@app.get("/", tags=["Root"]) # Tag for the root endpoint
async def root():
    """Provides a simple welcome message for the API root."""
    return {"message": "Welcome to Miktós AI Orchestration Platform API"}