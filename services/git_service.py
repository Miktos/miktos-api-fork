# services/git_service.py
import os
import shutil
from git import Repo, GitCommandError
from sqlalchemy.orm import Session
from models.database_models import Project, ContextStatus # Ensure these are correctly defined
from repositories.project_repository import ProjectRepository # Ensure this is correctly defined
from typing import Callable
from services.context_processor import process_repository_context # Ensure this is correctly defined
import traceback # Import traceback

# Define the base path for cloning repositories
REPO_CLONE_BASE_PATH = os.path.abspath("./repo_clones")
# Ensure the base directory exists
os.makedirs(REPO_CLONE_BASE_PATH, exist_ok=True)

def get_project_repo_path(project_id: str) -> str:
    """Generates the local filesystem path for a project's cloned repository."""
    # Use project_id directly as the directory name within the base path
    return os.path.join(REPO_CLONE_BASE_PATH, project_id)

def clone_or_update_repository(project_id: str, repo_url: str, session_factory: Callable[[], Session]):
    """
    Clones a repository or fetches updates, then triggers context processing.
    Handles status updates and error conditions.
    """
    print(f"--- BACKGROUND TASK STARTED: clone_or_update_repository for Project {project_id} ---")

    local_repo_path = get_project_repo_path(project_id)
    print(f"[GitService - Project {project_id}] Starting clone/update task for {repo_url} into path {local_repo_path}")

    db: Session | None = None
    project_repo: ProjectRepository | None = None
    project: Project | None = None
    clone_or_fetch_successful = False
    # Flag to track if processing was skipped due to initial status
    skipped_due_to_status = False

    try:
        # --- Manage DB Session within the background task ---
        print(f"[GitService - Project {project_id}] Attempting to get DB session from factory...")
        db = next(session_factory())
        print(f"[GitService - Project {project_id}] DB session obtained: {type(db)}")
        project_repo = ProjectRepository(db)
        # ---------------------------------------------------

        print(f"[GitService - Project {project_id}] Fetching project from DB...")
        project = project_repo.get(id=project_id)
        if not project:
             print(f"[GitService - ERROR - Project {project_id}] Project not found in DB.")
             # No project means nothing further to do, finally block will handle session close
             return

        # Use .value if comparing enum members, or just compare the enum members directly
        print(f"[GitService - Project {project_id}] Current status: {project.context_status}")
        # Check if status allows processing
        if project.context_status not in [ContextStatus.PENDING, ContextStatus.FAILED]:
             print(f"[GitService - Project {project_id}] Status not PENDING/FAILED. Skipping clone/update.")
             # Set flag before early exit
             skipped_due_to_status = True
             return # Exit early

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
            # Check if the remote URL matches the one provided
            if repo.remotes.origin.url != repo_url:
                 print(f"[GitService - WARNING - Project {project_id}] Remote URL mismatch! Existing: '{repo.remotes.origin.url}', Requested: '{repo_url}'. Re-cloning.")
                 # Need to remove the old directory before cloning again
                 shutil.rmtree(local_repo_path)
                 Repo.clone_from(repo_url, local_repo_path)
                 print(f"[GitService - Project {project_id}] Re-clone complete.")
            else:
                 # URL matches, just fetch updates
                 repo.remotes.origin.fetch()
                 print(f"[GitService - Project {project_id}] Fetch complete.")
        else:
            # Directory doesn't exist, clone fresh
            print(f"[GitService - Project {project_id}] Cloning new repository...")
            Repo.clone_from(repo_url, local_repo_path)
            print(f"[GitService - Project {project_id}] Clone complete.")
        # --- End Git Operations ---

        clone_or_fetch_successful = True # Mark git operation as successful

    except GitCommandError as e:
        print(f"[GitService - ERROR - Project {project_id}] Git command failed: {e}")
        # clone_or_fetch_successful remains False
    except Exception as e:
        print(f"[GitService - ERROR - Project {project_id}] An unexpected error occurred during git op or initial DB fetch: {e}")
        traceback.print_exc() # Log traceback for unexpected errors
        # clone_or_fetch_successful remains False

    # *** CORRECTED INDENTATION FOR FINALLY BLOCK ***
    finally:
        # --- Post-Operation Logic ---
        print(f"[GitService - Project {project_id}] Entering finally block.") # Debugging print
        if db and project_repo: # Check if DB session and repo were initialized

            # *** Check the flag first ***
            if skipped_due_to_status:
                print(f"[GitService - Project {project_id}] Final block: Deliberately skipped due to initial status. No status change or cleanup needed here.")
            elif clone_or_fetch_successful:
                # ... (Successful processing path - no changes needed here) ...
                print(f"[GitService - Project {project_id}] Final block: Git successful. Triggering context processing.")
                try:
                    process_repository_context(
                        project_id=project_id,
                        repo_path=local_repo_path,
                        session_factory=session_factory
                    )
                    print(f"[GitService - Project {project_id}] Final block: Context processing call finished.")
                except Exception as process_err:
                    print(f"[GitService - ERROR - Project {project_id}] Final block: Context processing function crashed: {process_err}")
                    traceback.print_exc()
                    try:
                        project_update = project_repo.get(id=project_id)
                        if project_update:
                            project_update.context_status = ContextStatus.FAILED
                            db.add(project_update)
                            db.commit()
                            print(f"[GitService - Project {project_id}] Final block: Set status to FAILED after processing crash.")
                        else:
                             print(f"[GitService - WARN - Project {project_id}] Final block: Project not found, cannot set status to FAILED after processing crash.")
                    except Exception as db_err:
                         print(f"[GitService - ERROR - Project {project_id}] Final block: Failed to update status to FAILED after processing crash: {db_err}")
            else:
                # Failure path: Git operation failed OR an error occurred before git started OR project not found initially
                # *** Check: Was the failure because the project didn't exist initially? ***
                # Use the 'project' variable captured in the 'try' block
                if project is None:
                     print(f"[GitService - Project {project_id}] Final block: Failure handling skipped because project was not found initially.")
                else:
                    # Project existed initially, but some other failure occurred
                    print(f"[GitService - Project {project_id}] Final block: Git operation failed or other error occurred. Setting status to FAILED.")
                    try:
                        # Attempt to set status to FAILED
                        # Use the 'project' variable which is still in scope if it wasn't None initially
                        project.context_status = ContextStatus.FAILED
                        db.add(project)
                        db.commit()
                        print(f"[GitService - Project {project_id}] Final block: Set status to FAILED after error.")

                        # Attempt cleanup only if a failure occurred during git op
                        if os.path.exists(local_repo_path):
                             print(f"[GitService - Project {project_id}] Final block: Cleaning up failed repository directory: {local_repo_path}")
                             try:
                                 shutil.rmtree(local_repo_path)
                                 print(f"[GitService - Project {project_id}] Final block: Removed failed clone directory.")
                             except Exception as rm_err:
                                 print(f"[GitService - WARNING - Project {project_id}] Final block: Failed to remove directory {local_repo_path}: {rm_err}")
                        else:
                             print(f"[GitService - Project {project_id}] Final block: Repository directory {local_repo_path} not found, no cleanup needed.")

                    except Exception as db_err:
                         print(f"[GitService - ERROR - Project {project_id}] Final block: Failed during failure handling (setting status or cleanup): {db_err}")

            # --- Ensure session is always closed ---
            print(f"[GitService - Project {project_id}] Final block: Closing DB session.")
            db.close()
            # ---------------------------------------
        else:
             # Handle case where db session/repo wasn't obtained (e.g., factory failed or project not found early return)
             if db: # If session exists but repo might not (project not found)
                print(f"[GitService - Project {project_id}] Final block: Closing DB session (project repo not initialized or project not found).")
                db.close()
             else:
                print(f"[GitService - ERROR - Project {project_id}] Final block: DB session was not available. Cannot perform final actions.")

        print(f"--- BACKGROUND TASK FINISHED: clone_or_update_repository for Project {project_id} ---")


# --- remove_repository function ---
def remove_repository(project_id: str):
    """Removes the locally cloned repository directory for a given project."""
    local_repo_path = get_project_repo_path(project_id)
    print(f"[BG Task/GitService - Project {project_id}] Attempting to remove repository directory: {local_repo_path}")
    if os.path.exists(local_repo_path) and os.path.isdir(local_repo_path):
        try:
            # Use shutil.rmtree to remove the directory and its contents
            shutil.rmtree(local_repo_path)
            print(f"[BG Task/GitService - Project {project_id}] Removed repository directory successfully.")
        except Exception as e:
            # Log potential errors during removal (e.g., permissions)
            print(f"[BG Task/GitService - ERROR - Project {project_id}] Failed to remove repository directory {local_repo_path}: {e}")
            traceback.print_exc() # Log full traceback for unexpected errors
    else:
        # Log if the directory wasn't found or wasn't a directory
        print(f"[BG Task/GitService - Project {project_id}] Repository directory not found or not a directory, nothing to remove: {local_repo_path}")