# services/git_service.py
import os
import shutil
from git import Repo, GitCommandError
from sqlalchemy.orm import Session
from models.database_models import Project, ContextStatus
from repositories.project_repository import ProjectRepository
from typing import Callable
from services.context_processor import process_repository_context

REPO_CLONE_BASE_PATH = os.path.abspath("./repo_clones")
os.makedirs(REPO_CLONE_BASE_PATH, exist_ok=True)

def get_project_repo_path(project_id: str) -> str:
    """Generates the local filesystem path for a project's cloned repository."""
    return os.path.join(REPO_CLONE_BASE_PATH, project_id)

def clone_or_update_repository(project_id: str, repo_url: str, session_factory: Callable[[], Session]):
    """
    Clones a repository or fetches updates, then triggers context processing.
    """
    # --- ADDED DEBUG PRINT AT THE VERY START ---
    print(f"--- BACKGROUND TASK STARTED: clone_or_update_repository for Project {project_id} ---")
    # -----------------------------------------

    local_repo_path = get_project_repo_path(project_id)
    # Original print moved slightly or combined
    print(f"[GitService - Project {project_id}] Starting clone/update task for {repo_url} into path {local_repo_path}")

    db: Session | None = None # Initialize db to None
    project_repo = None
    project: Project | None = None
    clone_or_fetch_successful = False

    try:
        # --- Manage DB Session within the background task ---
        print(f"[GitService - Project {project_id}] Attempting to get DB session from factory...")
        db = next(session_factory())
        print(f"[GitService - Project {project_id}] DB session obtained: {type(db)}")
        project_repo = ProjectRepository(db)
        # ---------------------------------------------------

        print(f"[GitService - Project {project_id}] Fetching project from DB...")
        project = project_repo.get(id=project_id) # Use base repo get
        if not project:
             print(f"[GitService - ERROR - Project {project_id}] Project not found in DB.")
             return # Exit early if project doesn't exist

        print(f"[GitService - Project {project_id}] Current status: {project.context_status.value}")
        if project.context_status not in [ContextStatus.PENDING, ContextStatus.FAILED]:
             print(f"[GitService - Project {project_id}] Status not PENDING/FAILED. Skipping clone/update.")
             return

        print(f"[GitService - Project {project_id}] Setting status to INDEXING.")
        project.context_status = ContextStatus.INDEXING
        db.add(project)
        db.commit()
        print(f"[GitService - Project {project_id}] Status updated to INDEXING in DB.")

        print(f"[GitService - Project {project_id}] Attempting git clone/update to {local_repo_path}")
        # --- Git Operations ---
        if os.path.exists(local_repo_path):
            print(f"[GitService - Project {project_id}] Local path exists. Fetching updates...")
            repo = Repo(local_repo_path)
            if repo.remotes.origin.url != repo_url:
                 print(f"[GitService - WARNING - Project {project_id}] Remote URL mismatch! Re-cloning.")
                 shutil.rmtree(local_repo_path)
                 Repo.clone_from(repo_url, local_repo_path)
                 print(f"[GitService - Project {project_id}] Re-clone complete.")
            else:
                 repo.remotes.origin.fetch()
                 print(f"[GitService - Project {project_id}] Fetch complete.")
        else:
            print(f"[GitService - Project {project_id}] Cloning new repository...")
            Repo.clone_from(repo_url, local_repo_path)
            print(f"[GitService - Project {project_id}] Clone complete.")
        # --- End Git Operations ---

        clone_or_fetch_successful = True

    except GitCommandError as e:
        print(f"[GitService - ERROR - Project {project_id}] Git command failed: {e}")
    except Exception as e:
        print(f"[GitService - ERROR - Project {project_id}] An unexpected error occurred during git op or initial DB fetch: {e}")
        # Log traceback for unexpected errors
        import traceback
        traceback.print_exc()

    finally:
        # --- Post-Git Operation Logic ---
        # Ensure we have a db session and repo if we got far enough
        if db and project_repo:
            if clone_or_fetch_successful:
                print(f"[GitService - Project {project_id}] Git operation successful. Triggering context processing.")
                try:
                    process_repository_context(
                        project_id=project_id,
                        repo_path=local_repo_path,
                        session_factory=session_factory # Pass the factory along
                    )
                    # Context processor now handles setting READY/FAILED
                except Exception as process_err:
                    print(f"[GitService - ERROR - Project {project_id}] Context processing function failed: {process_err}")
                    import traceback
                    traceback.print_exc()
                    # Attempt to set status to FAILED if processor crashed
                    try:
                        project = project_repo.get(id=project_id) # Re-fetch with current session
                        if project:
                            project.context_status = ContextStatus.FAILED
                            db.add(project)
                            db.commit()
                            print(f"[GitService - Project {project_id}] Set status to FAILED after processing error.")
                    except Exception as db_err:
                         print(f"[GitService - ERROR - Project {project_id}] Failed to update status to FAILED after processing error: {db_err}")
            else:
                # Git operation failed, set status to FAILED
                print(f"[GitService - Project {project_id}] Git operation failed. Setting status to FAILED.")
                try:
                    project = project_repo.get(id=project_id) # Re-fetch with current session
                    if project:
                        project.context_status = ContextStatus.FAILED
                        db.add(project)
                        db.commit()
                        print(f"[GitService - Project {project_id}] Set status to FAILED after git error.")
                except Exception as db_err:
                     print(f"[GitService - ERROR - Project {project_id}] Failed to update status to FAILED after git error: {db_err}")

                if os.path.exists(local_repo_path):
                    print(f"[GitService - Project {project_id}] Cleaning up failed repository directory: {local_repo_path}")
                    try:
                        shutil.rmtree(local_repo_path)
                        print(f"[GitService - Project {project_id}] Removed failed clone directory.")
                    except Exception as rm_err:
                        print(f"[GitService - WARNING - Project {project_id}] Failed to remove directory {local_repo_path}: {rm_err}")

            # --- Ensure session is always closed for this task ---
            print(f"[GitService - Project {project_id}] Closing DB session for git task.")
            db.close()
            # --------------------------------------------------
        else:
            print(f"[GitService - ERROR - Project {project_id}] DB session was not available in finally block. Cannot update status or close.")

        print(f"--- BACKGROUND TASK FINISHED: clone_or_update_repository for Project {project_id} ---") # Debug end


# --- remove_repository function (keep as is) ---
def remove_repository(project_id: str):
    local_repo_path = get_project_repo_path(project_id)
    print(f"[BG Task/GitService - Project {project_id}] Attempting to remove repository directory: {local_repo_path}")
    if os.path.exists(local_repo_path) and os.path.isdir(local_repo_path):
        try:
            shutil.rmtree(local_repo_path)
            print(f"[BG Task/GitService - Project {project_id}] Removed repository directory successfully.")
        except Exception as e:
            print(f"[BG Task/GitService - ERROR - Project {project_id}] Failed to remove repository directory {local_repo_path}: {e}")
    else:
        print(f"[BG Task/GitService - Project {project_id}] Repository directory not found or not a directory, nothing to remove: {local_repo_path}")