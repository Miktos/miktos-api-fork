# miktos_backend/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn # <-- Import uvicorn for the run block

# Import modules containing routers
from api import endpoints, auth, projects

# Import database configuration and base model
# Assuming get_db is defined in config.database or dependencies
# Adjust import if get_db comes from dependencies.py
from config.database import engine, Base, SessionLocal #<-- Import SessionLocal if needed by background tasks

# Create database tables if they don't exist (for development)
def create_db_and_tables():
    # In production, you should use migrations (e.g., Alembic)
    print("Checking/Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables checked/created.")
    except Exception as e:
        print(f"Error creating database tables: {e}")

# Call table creation function (consider using lifespan events for more robustness)
create_db_and_tables()

# Initialize the FastAPI app
app = FastAPI(
    title="Miktós AI Orchestrator",
    description="A platform to interact with multiple AI models via a unified interface.",
    version="0.2.0",
    # --- Add OpenAPI URL for documentation ---
    openapi_url="/api/v1/openapi.json", # Standard practice to version the OpenAPI spec
    docs_url="/api/v1/docs",            # Serve Swagger UI under versioned path
    redoc_url="/api/v1/redoc"           # Serve ReDoc under versioned path
)

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Default Vite port
    "http://localhost:5174", # Sometimes Vite uses next port
    "http://localhost:8080", # Common alternative dev port
    "http://localhost",
    # Add your deployed frontend URL here when ready
    # e.g., "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# --- Include API routers ---
# Apply a consistent base prefix for all API V1 routes

# General Endpoints Router (e.g., /generate)
app.include_router(
    endpoints.router,
    prefix="/api/v1", # Base prefix for general endpoints
    tags=["General"]
)

# Authentication Router
app.include_router(
    auth.router,
    prefix="/api/v1/auth", # Apply consistent prefix here
    tags=["Authentication"] # Add tag for docs grouping if not defined in auth.py
)

# Projects Router
# The prefix "/api/v1/projects" is defined within projects.router itself
app.include_router(
    projects.router
    # tags=["Projects"] # Tags are also defined within the router
)


# --- Root Endpoint ---
# This is outside the /api/v1 prefix
@app.get("/", tags=["Root"])
async def root():
    """Provides a simple welcome message for the API root."""
    return {"message": "Welcome to Miktós AI Orchestration Platform API. Docs at /api/v1/docs"}

# --- (Optional) Health Check Endpoint ---
# Also outside /api/v1 prefix, or move into endpoints.router
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    # Could add DB connection check here
    # try:
    #     db = SessionLocal()
    #     db.execute(text("SELECT 1"))
    #     db.close()
    #     db_status = "ok"
    # except Exception as e:
    #     db_status = "error"
    #     print(f"Health check DB error: {e}")
    # return {"status": "ok", "database": db_status}
    return {"status": "ok"}


# --- Run with Uvicorn (if running python main.py directly) ---
if __name__ == "__main__": # pragma: no cover  <--- ADD THIS COMMENT
    print("Starting Uvicorn server directly from main.py...")
    # Use host="127.0.0.1" for local access only, or "0.0.0.0" to be accessible on your network
    # Port 8000 is the default for FastAPI examples
    uvicorn.run(app, host="127.0.0.1", port=8000)