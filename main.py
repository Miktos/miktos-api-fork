# miktos_backend/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import modules containing routers
from api import endpoints, auth, projects # Ensure these modules exist and contain 'router' variables

# Import database configuration and base model
from config.database import get_db, engine, Base

# Create database tables if they don't exist (for development)
# In production, you should use migrations (e.g., Alembic)
# Consider moving this call elsewhere if it causes issues with async startup or tests
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
# In production, restrict this to your actual frontend domain
origins = [
    "http://localhost:3000",    # Common React port
    "http://localhost:5173",    # Common Vite/Vue/Svelte port
    "http://localhost:5174",    # Another common Vite port
    "http://localhost:8080",    # Common Vue port
    "http://localhost",         # Sometimes needed
    # Add your deployed frontend URL here when ready
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # Allows specified origins
    allow_credentials=True,     # Allows cookies/auth headers
    allow_methods=["*"],        # Allows all standard methods (GET, POST, etc.)
    allow_headers=["*"],        # Allows all headers
)

# --- Include API routers (Corrected Prefix Handling) ---

# Router for general endpoints (like /health, /generate)
# Assumes endpoints defined in 'endpoints.router' are relative (e.g., "/health")
# Add tags for organization in Swagger UI
app.include_router(
    endpoints.router,
    prefix="/api/v1",
    tags=["General"]
)

# Router for authentication endpoints
# Assumes 'auth.router' ALREADY has the prefix "/api/v1/auth" defined within api/auth.py
# DO NOT add the prefix again here. Tags are defined in auth.py.
app.include_router(auth.router)

# Router for project endpoints
# Assumes 'projects.router' ALREADY has the prefix "/api/v1/projects" defined within api/projects.py
# DO NOT add the prefix again here. Add tags in projects.py or here if needed.
app.include_router(projects.router, tags=["Projects"]) # Added tag here for example


# --- Root Endpoint ---
@app.get("/", tags=["Root"]) # Add tag for organization
async def root():
    """Provides a simple welcome message for the API root."""
    return {"message": "Welcome to Miktós AI Orchestration Platform API"}

# Note: If you have a health check endpoint defined in endpoints.router like /health,
# it will now be accessible at /api/v1/health due to the prefix added during inclusion.