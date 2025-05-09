# services/context_processor.py
import os
import chromadb
import logging
from chromadb.utils import embedding_functions
from chromadb.config import Settings as ChromaSettings
from sqlalchemy.orm import Session
from typing import Callable, List, Dict, Any
import uuid
import time # To measure processing time

# Import project models and repository
from models.database_models import Project, ContextStatus
from repositories.project_repository import ProjectRepository
# --- REMOVED IMPORT from services.git_service ---

# Setup logger
logger = logging.getLogger(__name__)

# --- Configuration ---
CHROMA_DATA_PATH = os.path.abspath("./chroma_db_data")
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME_PREFIX = "project_context_"
os.makedirs(CHROMA_DATA_PATH, exist_ok=True)

# --- ChromaDB Client Setup ---
def get_chroma_client():
    client = chromadb.PersistentClient(
        path=CHROMA_DATA_PATH,
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    return client

# --- Sentence Transformer Model Setup ---
def get_embedding_function():
    st_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME,
    )
    return st_ef

# --- Helper Function for Chroma Collection Name ---
def get_project_collection_name(project_id: str) -> str:
    return f"{COLLECTION_NAME_PREFIX}{project_id.replace('-', '_')}"

# --- Main Processing Function ---
# --- UPDATED SIGNATURE: Accept repo_path ---
def process_repository_context(project_id: str, repo_path: str, session_factory: Callable[[], Session]):
    """
    Scans a cloned repository, chunks files, generates embeddings, and stores them in ChromaDB.
    Updates the project's context_status.

    Args:
        project_id: The ID of the project.
        repo_path: The absolute path to the already cloned repository. <--- NEW ARG
        session_factory: Callable to get a new DB Session.
    """
    start_time = time.time()
    logger.info(f"[Project {project_id}] Starting repository processing for path: {repo_path}")

    # --- UPDATED: Use passed repo_path directly ---
    # repo_path = get_project_repo_path(project_id) # <--- REMOVED CALCULATION
    if not os.path.isdir(repo_path):
        logger.error(f"[Project {project_id}] Repository path not found: {repo_path}")
        return

    # --- Initialize DB Session ---
    db: Session = next(session_factory())
    project_repo = ProjectRepository(db)
    project: Project | None = None
    # -----------------------------

    try:
        # --- Initialize ChromaDB & Model ---
        logger.info(f"[Project {project_id}] Initializing ChromaDB client and embedding model...")
        chroma_client = get_chroma_client()
        embedding_function = get_embedding_function()
        collection_name = get_project_collection_name(project_id)

        logger.info(f"[Project {project_id}] Getting/Creating Chroma collection: {collection_name}")
        # --- Delete existing collection ---
        try:
             chroma_client.delete_collection(name=collection_name)
             logger.info(f"[Project {project_id}] Deleted existing collection.")
        except Exception as delete_err:
             logger.warning(f"[Project {project_id}] Could not delete collection {collection_name} (maybe didn't exist): {delete_err}")
        # --- Recreate collection ---
        collection = chroma_client.get_or_create_collection(
             name=collection_name,
             embedding_function=embedding_function
        )
        logger.info(f"[Project {project_id}] Ensured collection exists.")

        # --- File Traversal, Filtering, Chunking ---
        logger.info(f"[Project {project_id}] Starting file traversal in {repo_path}...")
        all_chunks: List[str] = []
        all_metadatas: List[Dict[str, Any]] = []
        all_ids: List[str] = []
        file_count = 0
        chunk_count = 0

        for root, _, files in os.walk(repo_path):
             if ".git" in root.split(os.sep):
                 continue
             for file in files:
                 # --- IMPROVED FILTERING ---
                 # Skip common non-text/code files - expand this list as needed
                 _, ext = os.path.splitext(file)
                 if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.lock', '.bin', '.exe', '.dll', '.so', '.dylib', '.zip', '.gz', '.tar', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.o', '.a', '.obj', '.class', '.env']:
                      continue
                 # Consider adding .gitignore parsing here for more robust filtering
                 # --------------------------

                 file_path = os.path.join(root, file)
                 relative_path = os.path.relpath(file_path, repo_path)
                 try:
                     # Check file size before reading - skip huge files?
                     if os.path.getsize(file_path) > 5 * 1024 * 1024: # Skip files larger than 5MB
                          logger.warning(f"[Project {project_id}] Skipping large file {relative_path}")
                          continue

                     with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                         content = f.read()

                     # --- Basic Chunking (replace with better method like LangChain later) ---
                     chunks = [chunk for chunk in content.split('\n\n') if chunk.strip()]
                     if not chunks and content.strip():
                         chunks = [content]
                     # -----------------------------------------------------------------------

                     for i, chunk in enumerate(chunks):
                         chunk_text = chunk.strip()
                         if len(chunk_text) < 20: continue

                         chunk_id = f"{relative_path}::{i}" # Use relative path for ID
                         metadata = {"source": relative_path, "chunk_index": i, "project_id": project_id} # Add project_id to metadata

                         all_chunks.append(chunk_text[:4000]) # Limit chunk size (check embedding model limits)
                         all_metadatas.append(metadata)
                         all_ids.append(chunk_id)
                         chunk_count += 1
                     file_count += 1
                 except Exception as read_err:
                      logger.warning(f"[Project {project_id}] Failed to read/process file {file_path}: {read_err}")

        logger.info(f"[Project {project_id}] Processed {file_count} files, generated {chunk_count} chunks.")

        # --- Embedding and Storing ---
        if all_chunks:
            logger.info(f"[Project {project_id}] Adding {len(all_chunks)} chunks to Chroma collection...")
            # Add documents (ChromaDB handles batching)
            collection.add(
                documents=all_chunks,
                metadatas=all_metadatas,
                ids=all_ids
            )
            logger.info(f"[Project {project_id}] Successfully added chunks to Chroma.")
        else:
            logger.info(f"[Project {project_id}] No processable chunks found in repository.")

        # --- Update DB Status to READY ---
        project = project_repo.get(project_id)
        if project:
            project.context_status = ContextStatus.READY
            db.add(project)
            db.commit()
        else:
            logger.warning(f"[Project {project_id}] Project not found after processing.")
        logger.info(f"[Project {project_id}] Successfully processed repository context.")

    except Exception as e:
        logger.error(f"[Project {project_id}] Failed during context processing: {e}", exc_info=True)
        # --- Update DB Status to FAILED ---
        try:
            if not project: 
                project = project_repo.get(project_id)
            if project:
                project.context_status = ContextStatus.FAILED
                db.add(project)
                db.commit()
            else:
                logger.error(f"[Project {project_id}] Project not found")
        except Exception as db_err:
            logger.error(f"[Project {project_id}] Failed to update status to FAILED in DB: {db_err}", exc_info=True)
    finally:
        logger.info(f"[Project {project_id}] Closing DB session.")
        db.close()

    end_time = time.time()
    logger.info(f"[Project {project_id}] Processing finished in {end_time - start_time:.2f} seconds.")