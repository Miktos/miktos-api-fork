# miktos_backend/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn # <-- Import uvicorn for the run block

# Import modules containing routers
from api import endpoints, auth, projects, admin

# Import database configuration and base model
# Assuming get_db is defined in config.database or dependencies
# Adjust import if get_db comes from dependencies.py
from config.database import engine, Base, SessionLocal #<-- Import SessionLocal if needed by background tasks
from config.settings import settings

# Import the enhanced rate limiter
from middleware.rate_limiter import create_rate_limiter, RateLimiterMiddleware

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
    version=settings.VERSION,
    # --- Add OpenAPI URL for documentation ---
    openapi_url="/api/v1/openapi.json", # Standard practice to version the OpenAPI spec
    docs_url="/api/v1/docs",            # Serve Swagger UI under versioned path
    redoc_url="/api/v1/redoc"           # Serve ReDoc under versioned path
)

# --- CORS Middleware ---
origins = settings.CORS.ALLOW_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=settings.CORS.ALLOW_METHODS,
    allow_headers=settings.CORS.ALLOW_HEADERS,
)

# --- Add Rate Limiter Middleware ---
if not settings.is_testing():  # Skip in test environment
    from middleware.rate_limiter import RateLimiterMiddleware, get_rate_limiter_config
    rate_limit_config = get_rate_limiter_config()
    app.add_middleware(RateLimiterMiddleware, **rate_limit_config)

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

# Admin Router
app.include_router(
    admin.router,
    prefix="/api/v1/admin", # Admin endpoints under /api/v1/admin
    tags=["Admin"] # Tag is also defined within the router
)

# --- Root Endpoint ---
# This is outside the /api/v1 prefix
@app.get("/", tags=["Root"])
async def root():
    """Provides a simple welcome message for the API root."""
    return {"message": f"Welcome to {settings.APP_NAME} API. Docs at /api/v1/docs"}

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
    uvicorn.run(app, host="127.0.0.1", port=settings.PORT)