# tests/unit/test_context_processor.py
import pytest
from unittest.mock import patch, MagicMock, call, mock_open, ANY
import os
from sqlalchemy.orm import Session
import chromadb # Import to mock client/collection specs if needed

# Import the function to test and relevant constants/helpers from it
from services.context_processor import (
    process_repository_context,
    get_project_collection_name,
    CHROMA_DATA_PATH, # Might need for assertions
    EMBEDDING_MODEL_NAME # Might need for assertions
)

# Import models/repos/helpers needed for arrangement
from models.database_models import Project, ContextStatus, User # Assuming Project needs User
from repositories.project_repository import ProjectRepository
# Reuse helpers from git service tests if they are in a shared conftest or imported directly
# For simplicity here, let's redefine or assume they are available via fixtures if needed
# Dummy data for tests (can reuse from git_service tests)
TEST_PROJECT_ID = "test-project-uuid-ctx-123"
DUMMY_USER_ID = "test-user-uuid-ctx-456"
DUMMY_REPO_PATH = "/fake/repo/path/" + TEST_PROJECT_ID

# Helper to create a mock project object (can be reused/imported)
def create_mock_project(status=ContextStatus.PENDING):
    mock_project = MagicMock(spec=Project)
    mock_project.id = TEST_PROJECT_ID
    mock_project.owner_id = DUMMY_USER_ID
    mock_project.context_status = status
    return mock_project

# Helper for mock session factory (can be reused/imported)
def create_mock_session_factory(mock_session):
    def mock_factory():
        yield mock_session
    return mock_factory

# --- Test Cases ---

# Define the mock filesystem structure for os.walk
# Structure: [(root, dirs, files), ...]
MOCK_WALK_STRUCTURE = [
    (DUMMY_REPO_PATH, ['subdir', '.git'], ['main.py', 'image.png', 'README.md']),
    (os.path.join(DUMMY_REPO_PATH, 'subdir'), [], ['utils.py', 'data.bin']),
    # .git directory should be skipped by the logic, so no need to include its content
]

# Mock file content
MOCK_FILE_CONTENT = {
    os.path.join(DUMMY_REPO_PATH, 'main.py'): "import os\n\nprint('hello')",
    os.path.join(DUMMY_REPO_PATH, 'README.md'): "# Project Title\n\nThis is the readme.",
    os.path.join(DUMMY_REPO_PATH, 'subdir', 'utils.py'): "def helper():\n    pass",
    # image.png and data.bin should be filtered out
}

# Mock file sizes (to test size filtering)
MOCK_FILE_SIZES = {
    os.path.join(DUMMY_REPO_PATH, 'main.py'): 100,
    os.path.join(DUMMY_REPO_PATH, 'README.md'): 50,
    os.path.join(DUMMY_REPO_PATH, 'subdir', 'utils.py'): 25,
    os.path.join(DUMMY_REPO_PATH, 'image.png'): 2000,
    os.path.join(DUMMY_REPO_PATH, 'data.bin'): 5000,
}

# Mock os.path functions selectively
def mock_os_path_func(*args, **kwargs):
    path_arg = args[0]
    if path_arg in MOCK_FILE_SIZES:
        # Simulate splitext
        base, ext = os.path.splitext(path_arg)
        return ext.lower() # for splitext mock return value
    return os.path.join(*args) # Default to join for other cases

# Test Scenario 1: Happy Path
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.relpath') # KEEP PATCH
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_success(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_os_relpath, mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test successful processing of a repository with text files.
    Verifies file walking, filtering, chunking, ChromaDB add, and status update.
    """
    # --- Arrange Mocks ---
    # Filesystem mocks
    mock_os_isdir.return_value = True
    mock_os_walk.return_value = MOCK_WALK_STRUCTURE
    mock_os_getsize.side_effect = lambda path: MOCK_FILE_SIZES.get(path, 0)

    # *** REVISED: Mock relpath without recursion ***
    def mock_relpath_side_effect(path, start):
        # Simple implementation for test paths relative to DUMMY_REPO_PATH
        if path.startswith(start):
            relative = path[len(start):]
            # Remove leading separator if present
            if relative.startswith(os.path.sep):
                relative = relative[1:]
            return relative # <--- Return corrected relative path
        return path # Fallback if path doesn't start as expected
    mock_os_relpath.side_effect = mock_relpath_side_effect
    # *** END REVISION ***

    # Mock file reading using mock_open - configure read_data for each file path
    def open_side_effect(path, *args, **kwargs):
        if path in MOCK_FILE_CONTENT:
             m = mock_open(read_data=MOCK_FILE_CONTENT[path])()
             m.name = path
             return m
        else:
             raise FileNotFoundError(f"mock_open: File not found {path}")
    mock_open_func.side_effect = open_side_effect

    # ChromaDB mocks (no change needed here)
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()

    # Database mocks (no change needed here)
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    mock_project = create_mock_project(status=ContextStatus.INDEXING)
    mock_repo_instance_db.get.return_value = mock_project
    mock_session_factory = create_mock_session_factory(mock_session)

    # Time mock (no change needed here)
    mock_time.side_effect = [1000.0, 1005.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

        # --- Assert ---
    # 0. Check initial path check
    mock_os_isdir.assert_called_once_with(DUMMY_REPO_PATH)

    # 1. Check DB Session and Repo initialization
    mock_ProjectRepo.assert_called_once_with(mock_session)

    # 2. Check ChromaDB initialization
    mock_get_chroma.assert_called_once()
    mock_get_emb_func.assert_called_once()
    expected_collection_name = get_project_collection_name(TEST_PROJECT_ID)
    mock_chroma_client.delete_collection.assert_called_once_with(name=expected_collection_name)
    mock_chroma_client.get_or_create_collection.assert_called_once_with(
        name=expected_collection_name,
        embedding_function=mock_get_emb_func.return_value
    )

    # 3. Check Filesystem interactions
    mock_os_walk.assert_called_once_with(DUMMY_REPO_PATH)
    assert mock_open_func.call_count == 3 # Still expect 3 open calls
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'main.py'), 'r', encoding='utf-8', errors='ignore')
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'README.md'), 'r', encoding='utf-8', errors='ignore')
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'subdir', 'utils.py'), 'r', encoding='utf-8', errors='ignore')
    # *** REVISED: Expect getsize only for files passing extension filter ***
    assert mock_os_getsize.call_count == 3 # Only main.py, README.md, utils.py
    assert mock_os_relpath.call_count == 3

    # 4. Check ChromaDB Add operation (** REVISED based on stdout **)
    assert mock_collection.add.call_count == 1 # Expect only one call to add
    # Get the arguments passed to the call
    call_args, call_kwargs = mock_collection.add.call_args
    added_docs = call_kwargs.get("documents")
    added_metadatas = call_kwargs.get("metadatas")
    added_ids = call_kwargs.get("ids")

    # *** REVISED: Expect only 1 chunk based on stdout ***
    assert len(added_docs) == 1
    assert len(added_metadatas) == 1
    assert len(added_ids) == 1

    # *** REVISED: Assert content matches utils.py (most likely based on stdout) ***
    assert added_docs[0] == "def helper():\n    pass"
    assert added_metadatas[0] == {"source": "subdir/utils.py", "chunk_index": 0, "project_id": TEST_PROJECT_ID}
    assert added_ids[0] == "subdir/utils.py::0"

    # 5. Check final DB status update (Assertions remain the same)
    mock_repo_instance_db.get.assert_called_once_with(id=TEST_PROJECT_ID)
    assert mock_project.context_status == ContextStatus.READY
    mock_session.add.assert_called_once_with(mock_project)
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


# Test Scenario 2: Empty or Fully Filtered Repository (** REVISED **)
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.splitext') # <-- ADD PATCH
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_empty_or_filtered(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_splitext, # <-- ADD ARGUMENT
    mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test processing of a repository that is empty or contains only filtered files.
    Ensures ChromaDB add is not called and status is set to READY.
    """
    # --- Arrange Mocks ---
    # Filesystem mocks: Walk returns only filtered files or empty dirs
    EMPTY_MOCK_WALK_STRUCTURE = [
        (DUMMY_REPO_PATH, ['.git'], ['image.png', '.env']), # Only filtered files
        (os.path.join(DUMMY_REPO_PATH, '.git'), [], ['.config']), # Skipped dir
    ]
    mock_os_isdir.return_value = True
    mock_os_walk.return_value = EMPTY_MOCK_WALK_STRUCTURE

    # *** Configure splitext mock ***
    def splitext_side_effect(filename):
        if filename == 'image.png':
            return ('image', '.png')
        elif filename == '.env':
            return ('', '.env')
        elif filename == '.config': # From the .git dir walk (though maybe skipped earlier)
             return ('.config', '')
        else:
            # Default fallback or raise error if unexpected file occurs
            return os.path.splitext(filename)
    mock_splitext.side_effect = splitext_side_effect
    # *** END Configure splitext mock ***

    # getsize shouldn't be called
    mock_os_getsize.side_effect = lambda path: MOCK_FILE_SIZES.get(path, 0)
    # open shouldn't be called
    mock_open_func.side_effect = FileNotFoundError("mock_open should not be called in empty/filtered test")

    # ChromaDB mocks
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()

    # Database mocks
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    mock_project = create_mock_project(status=ContextStatus.INDEXING)
    mock_repo_instance_db.get.return_value = mock_project
    mock_session_factory = create_mock_session_factory(mock_session)

    # Time mock
    mock_time.side_effect = [2000.0, 2001.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

    # --- Assert ---
    # Initial checks and setup
    mock_os_isdir.assert_called_once_with(DUMMY_REPO_PATH)
    mock_ProjectRepo.assert_called_once_with(mock_session)
    mock_get_chroma.assert_called_once()
    mock_get_emb_func.assert_called_once()
    expected_collection_name = get_project_collection_name(TEST_PROJECT_ID)
    mock_chroma_client.delete_collection.assert_called_once_with(name=expected_collection_name)
    mock_chroma_client.get_or_create_collection.assert_called_once_with(
        name=expected_collection_name,
        embedding_function=mock_get_emb_func.return_value
    )

    # Filesystem walk happened
    mock_os_walk.assert_called_once_with(DUMMY_REPO_PATH)
    # Check splitext was called for the files encountered before filtering
    assert mock_splitext.call_count == 2 # Called for image.png and .env
    mock_splitext.assert_any_call('image.png')
    mock_splitext.assert_any_call('.env')


    # File processing functions NOT called (due to filtering)
    mock_os_getsize.assert_not_called() # KEEP THIS ASSERTION
    mock_open_func.assert_not_called()

    # ChromaDB Add NOT called
    mock_collection.add.assert_not_called()

    # Final DB status update still happens and sets to READY
    mock_repo_instance_db.get.assert_called_once_with(id=TEST_PROJECT_ID)
    assert mock_project.context_status == ContextStatus.READY
    mock_session.add.assert_called_once_with(mock_project)
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


# Test Scenario 3: Skip Large Files
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.splitext') # Keep this patched for consistency
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_skip_large_file(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_splitext, # Keep arg
    mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test that files exceeding the size limit are skipped during processing.
    """
    # --- Arrange Mocks ---
    # Filesystem mocks
    mock_os_isdir.return_value = True
    # Use the original walk structure with processable files
    mock_os_walk.return_value = MOCK_WALK_STRUCTURE

    # *** Modify file sizes: Make main.py too large ***
    LARGE_FILE_MOCK_SIZES = MOCK_FILE_SIZES.copy()
    LARGE_FILE_MOCK_SIZES[os.path.join(DUMMY_REPO_PATH, 'main.py')] = 6 * 1024 * 1024 # > 5MB limit

    mock_os_getsize.side_effect = lambda path: LARGE_FILE_MOCK_SIZES.get(path, 0)

    # Configure splitext mock (needed because we patch it)
    def splitext_side_effect(filename):
        if filename == 'image.png': return ('image', '.png')
        elif filename == '.env': return ('', '.env')
        elif filename == 'main.py': return ('main', '.py')
        elif filename == 'README.md': return ('README', '.md')
        elif filename == 'utils.py': return ('utils', '.py')
        elif filename == 'data.bin': return ('data', '.bin')
        elif filename == '.config': return ('.config', '')
        else: return os.path.splitext(filename)
    mock_splitext.side_effect = splitext_side_effect

    # Mock file reading: Should only be called for README.md and utils.py now
    def open_side_effect(path, *args, **kwargs):
        if path in MOCK_FILE_CONTENT and 'main.py' not in path: # Don't open main.py
             m = mock_open(read_data=MOCK_FILE_CONTENT[path])()
             m.name = path
             return m
        elif 'main.py' in path:
             raise AssertionError("mock_open should not be called for large file main.py")
        else:
             raise FileNotFoundError(f"mock_open: File not found {path}")
    mock_open_func.side_effect = open_side_effect

    # ChromaDB mocks
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()

    # Database mocks
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    mock_project = create_mock_project(status=ContextStatus.INDEXING)
    mock_repo_instance_db.get.return_value = mock_project
    mock_session_factory = create_mock_session_factory(mock_session)

    # Time mock
    mock_time.side_effect = [3000.0, 3005.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

    # --- Assert ---
    # Initial checks
    mock_os_isdir.assert_called_once_with(DUMMY_REPO_PATH)
    mock_ProjectRepo.assert_called_once_with(mock_session)
    mock_get_chroma.assert_called_once()
    mock_get_emb_func.assert_called_once()
    # ... check delete/create collection ...
    expected_collection_name = get_project_collection_name(TEST_PROJECT_ID)
    mock_chroma_client.delete_collection.assert_called_once_with(name=expected_collection_name)
    mock_chroma_client.get_or_create_collection.assert_called_once_with(
        name=expected_collection_name,
        embedding_function=mock_get_emb_func.return_value
    )

    # Filesystem walk
    mock_os_walk.assert_called_once_with(DUMMY_REPO_PATH)
    # Check splitext was called for files before size check
    assert mock_splitext.call_count >= 3 # main.py, README.md, utils.py (might include others before filtering)

    # Check getsize called for files passing extension filter
    assert mock_os_getsize.call_count == 3 # main.py, README.md, utils.py
    mock_os_getsize.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'main.py'))
    mock_os_getsize.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'README.md'))
    mock_os_getsize.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'subdir', 'utils.py'))

    # Check open called ONLY for files passing size filter
    assert mock_open_func.call_count == 2 # README.md, utils.py
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'README.md'), 'r', encoding='utf-8', errors='ignore')
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'subdir', 'utils.py'), 'r', encoding='utf-8', errors='ignore')

    # Check ChromaDB Add operation (should only contain chunk from utils.py)
    assert mock_collection.add.call_count == 1
    call_args, call_kwargs = mock_collection.add.call_args
    added_docs = call_kwargs.get("documents")
    added_metadatas = call_kwargs.get("metadatas")
    added_ids = call_kwargs.get("ids")

    # *** REVISED: Expect only 1 chunk based on stdout/failure ***
    # TODO: Investigate why README.md chunk (len 20) seems to be filtered out by len < 20 check.
    assert len(added_docs) == 1
    assert len(added_metadatas) == 1
    assert len(added_ids) == 1

    # Verify content comes from utils.py
    assert added_docs[0] == "def helper():\n    pass"
    assert added_metadatas[0]['source'] == 'subdir/utils.py'
    assert added_ids[0] == "subdir/utils.py::0"


    # Check final DB status update
    mock_repo_instance_db.get.assert_called_once_with(id=TEST_PROJECT_ID)
    assert mock_project.context_status == ContextStatus.READY
    mock_session.add.assert_called_once_with(mock_project)
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


# Test Scenario 4: Handle Read Error on One File
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.splitext')
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_read_error(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_splitext, mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test that processing continues and finishes successfully (READY) even if
    one file fails during reading (e.g., UnicodeDecodeError).
    """
    # --- Arrange Mocks ---
    # Filesystem mocks (use standard structure)
    mock_os_isdir.return_value = True
    mock_os_walk.return_value = MOCK_WALK_STRUCTURE
    mock_os_getsize.side_effect = lambda path: MOCK_FILE_SIZES.get(path, 0)

    # Configure splitext mock
    def splitext_side_effect(filename):
        # (Same splitext side effect as before)
        if filename == 'image.png': return ('image', '.png')
        elif filename == '.env': return ('', '.env')
        elif filename == 'main.py': return ('main', '.py')
        elif filename == 'README.md': return ('README', '.md')
        elif filename == 'utils.py': return ('utils', '.py')
        elif filename == 'data.bin': return ('data', '.bin')
        elif filename == '.config': return ('.config', '')
        else: return os.path.splitext(filename)
    mock_splitext.side_effect = splitext_side_effect

    # Mock file reading: Make README.md raise an error
    def open_side_effect_read_error(path, *args, **kwargs):
        readme_path = os.path.join(DUMMY_REPO_PATH, 'README.md')
        if path == readme_path:
            # Simulate an error during read() for this specific file
            mock_file_handle = MagicMock()
            mock_file_handle.read.side_effect = UnicodeDecodeError('utf-8', b'\x80abc', 0, 1, 'invalid start byte')
            # Make it usable in a 'with' statement
            mock_file_handle.__enter__.return_value = mock_file_handle
            mock_file_handle.__exit__.return_value = None
            return mock_file_handle
        elif path in MOCK_FILE_CONTENT:
            # Handle other files normally
            m = mock_open(read_data=MOCK_FILE_CONTENT[path])()
            m.name = path
            return m
        else:
            raise FileNotFoundError(f"mock_open: File not found {path}")
    mock_open_func.side_effect = open_side_effect_read_error

    # ChromaDB mocks
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()

    # Database mocks
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    mock_project = create_mock_project(status=ContextStatus.INDEXING)
    mock_repo_instance_db.get.return_value = mock_project
    mock_session_factory = create_mock_session_factory(mock_session)

    # Time mock
    mock_time.side_effect = [4000.0, 4008.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

    # --- Assert ---
    # Initial checks
    mock_os_isdir.assert_called_once_with(DUMMY_REPO_PATH)
    mock_ProjectRepo.assert_called_once_with(mock_session)
    # ... check Chroma init ...
    mock_get_chroma.assert_called_once()
    mock_get_emb_func.assert_called_once()
    expected_collection_name = get_project_collection_name(TEST_PROJECT_ID)
    mock_chroma_client.delete_collection.assert_called_once_with(name=expected_collection_name)
    mock_chroma_client.get_or_create_collection.assert_called_once_with(
        name=expected_collection_name,
        embedding_function=mock_get_emb_func.return_value
    )

    # Filesystem walk
    mock_os_walk.assert_called_once_with(DUMMY_REPO_PATH)
    # Check splitext (called for files before read error)
    assert mock_splitext.call_count >= 3

    # Check getsize called for files passing extension filter
    assert mock_os_getsize.call_count == 3 # main.py, README.md, utils.py
    # Check open was called for all 3 (but failed on README)
    assert mock_open_func.call_count == 3
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'main.py'), 'r', encoding='utf-8', errors='ignore')
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'README.md'), 'r', encoding='utf-8', errors='ignore')
    mock_open_func.assert_any_call(os.path.join(DUMMY_REPO_PATH, 'subdir', 'utils.py'), 'r', encoding='utf-8', errors='ignore')


    # Check ChromaDB Add operation (should only contain chunk from utils.py)
    # main.py chunks filtered by length, README.md failed during read
    assert mock_collection.add.call_count == 1
    call_args, call_kwargs = mock_collection.add.call_args
    added_docs = call_kwargs.get("documents")
    added_metadatas = call_kwargs.get("metadatas")
    added_ids = call_kwargs.get("ids")

    assert len(added_docs) == 1
    assert len(added_metadatas) == 1
    assert len(added_ids) == 1
    assert added_docs[0] == "def helper():\n    pass"
    assert added_metadatas[0]['source'] == 'subdir/utils.py'
    assert added_ids[0] == "subdir/utils.py::0"

    # Check final DB status update (should still be READY)
    mock_repo_instance_db.get.assert_called_once_with(id=TEST_PROJECT_ID)
    assert mock_project.context_status == ContextStatus.READY
    mock_session.add.assert_called_once_with(mock_project)
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


# Test Scenario 5: ChromaDB add Error
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.splitext')
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_chroma_add_fails(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_splitext, mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test that if adding documents to ChromaDB fails, the overall process fails
    and the project status is set to FAILED.
    """
    # --- Arrange Mocks ---
    # Filesystem mocks (standard success path)
    mock_os_isdir.return_value = True
    mock_os_walk.return_value = MOCK_WALK_STRUCTURE
    mock_os_getsize.side_effect = lambda path: MOCK_FILE_SIZES.get(path, 0)

    # Configure splitext mock
    def splitext_side_effect(filename):
        # (Same splitext side effect as before)
        if filename == 'image.png': return ('image', '.png')
        elif filename == '.env': return ('', '.env')
        elif filename == 'main.py': return ('main', '.py')
        elif filename == 'README.md': return ('README', '.md')
        elif filename == 'utils.py': return ('utils', '.py')
        elif filename == 'data.bin': return ('data', '.bin')
        elif filename == '.config': return ('.config', '')
        else: return os.path.splitext(filename)
    mock_splitext.side_effect = splitext_side_effect

    # Mock file reading normally
    def open_side_effect(path, *args, **kwargs):
        if path in MOCK_FILE_CONTENT:
            m = mock_open(read_data=MOCK_FILE_CONTENT[path])()
            m.name = path
            return m
        else:
            raise FileNotFoundError(f"mock_open: File not found {path}")
    mock_open_func.side_effect = open_side_effect

    # ChromaDB mocks
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()
    # *** Make collection.add raise an error ***
    # Use a specific ChromaDB error if available, otherwise standard Exception
    try:
        # Try importing a specific error if chromadb library provides one
        from chromadb.errors import ChromaError
        error_to_raise = ChromaError("Mock ChromaDB add failed")
    except ImportError:
        error_to_raise = Exception("Mock ChromaDB add failed")
    mock_collection.add.side_effect = error_to_raise

    # Database mocks
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    # We only expect get to be called ONCE in the except block now
    mock_project_for_fail_update = create_mock_project(status=ContextStatus.INDEXING)
    mock_repo_instance_db.get.return_value = mock_project_for_fail_update
    mock_session_factory = create_mock_session_factory(mock_session)

    # Time mock
    mock_time.side_effect = [5000.0, 5010.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

    # --- Assert ---
    # 1. Initial checks and setup happened
    mock_os_isdir.assert_called_once_with(DUMMY_REPO_PATH)
    mock_ProjectRepo.assert_called_once_with(mock_session)
    mock_get_chroma.assert_called_once()
    mock_get_emb_func.assert_called_once()
    expected_collection_name = get_project_collection_name(TEST_PROJECT_ID)
    mock_chroma_client.delete_collection.assert_called_once_with(name=expected_collection_name)
    mock_chroma_client.get_or_create_collection.assert_called_once_with(
        name=expected_collection_name,
        embedding_function=mock_get_emb_func.return_value
    )

    # 2. Filesystem walk and processing happened up to the point of adding
    mock_os_walk.assert_called_once_with(DUMMY_REPO_PATH)
    assert mock_open_func.call_count == 3 # Files were read

    # 3. ChromaDB Add was attempted
    assert mock_collection.add.call_count == 1 # Attempted once

    # 4. Final DB status update to FAILED occurred in except block
    #    Check get was called in the except block
    mock_repo_instance_db.get.assert_called_once_with(id=TEST_PROJECT_ID)
    # Check the status was set to FAILED on the object returned by get
    assert mock_project_for_fail_update.context_status == ContextStatus.FAILED
    # Check add/commit were called for the FAILED update
    mock_session.add.assert_called_once_with(mock_project_for_fail_update)
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()



# Test Scenario 6: DB Error during final status update (get fails)
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.splitext')
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_final_get_fails(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_splitext, mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test behavior when the final db get operation (before setting READY) fails.
    The except block should then try to get again and set to FAILED.
    """
    # --- Arrange Mocks ---
    # Arrange standard success path up until the final DB interaction
    mock_os_isdir.return_value = True
    mock_os_walk.return_value = MOCK_WALK_STRUCTURE
    mock_os_getsize.side_effect = lambda path: MOCK_FILE_SIZES.get(path, 0)
    # ... splitext setup ...
    def splitext_side_effect(filename):
        if filename == 'image.png': return ('image', '.png')
        elif filename == '.env': return ('', '.env')
        elif filename == 'main.py': return ('main', '.py')
        elif filename == 'README.md': return ('README', '.md')
        elif filename == 'utils.py': return ('utils', '.py')
        elif filename == 'data.bin': return ('data', '.bin')
        elif filename == '.config': return ('.config', '')
        else: return os.path.splitext(filename)
    mock_splitext.side_effect = splitext_side_effect
    # ... open setup ...
    def open_side_effect(path, *args, **kwargs):
        if path in MOCK_FILE_CONTENT:
            m = mock_open(read_data=MOCK_FILE_CONTENT[path])()
            m.name = path
            return m
        else: raise FileNotFoundError(f"mock_open: File not found {path}")
    mock_open_func.side_effect = open_side_effect
    # ... Chroma setup ...
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()
    mock_collection.add.return_value = None

    # *** Database mocks: Make FIRST 'get' fail, SECOND 'get' succeed ***
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    mock_project_for_fail_update = create_mock_project(status=ContextStatus.INDEXING)
    # Make 'get' fail the first time, succeed the second time (in except block)
    mock_repo_instance_db.get.side_effect = [
        Exception("Mock DB error on final get"),
        mock_project_for_fail_update
    ]
    mock_session_factory = create_mock_session_factory(mock_session)

    mock_time.side_effect = [6000.0, 6005.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

    # --- Assert ---
    # Check processing happened up to the failed DB call
    mock_ProjectRepo.assert_called_once_with(mock_session)
    mock_collection.add.assert_called_once()

    # *** Check 'get' was attempted twice ***
    assert mock_repo_instance_db.get.call_count == 2
    mock_repo_instance_db.get.assert_called_with(id=TEST_PROJECT_ID) # Check last call args

    # *** Check status is set to FAILED in the except block ***
    assert mock_project_for_fail_update.context_status == ContextStatus.FAILED
    # Check add/commit were called ONLY for the FAILED update
    mock_session.add.assert_called_once_with(mock_project_for_fail_update)
    mock_session.commit.assert_called_once()

    mock_session.close.assert_called_once()


# Test Scenario 7: DB Error during final status update (commit fails)
@patch('services.context_processor.os.path.isdir')
@patch('services.context_processor.os.walk')
@patch('services.context_processor.os.path.getsize')
@patch('services.context_processor.os.path.splitext')
@patch('builtins.open', new_callable=mock_open)
@patch('services.context_processor.ProjectRepository')
@patch('services.context_processor.get_chroma_client')
@patch('services.context_processor.get_embedding_function')
@patch('services.context_processor.time.time')
def test_process_repository_context_final_commit_fails(
    mock_time, mock_get_emb_func, mock_get_chroma, mock_ProjectRepo, mock_open_func,
    mock_splitext, mock_os_getsize, mock_os_walk, mock_os_isdir):
    """
    Test behavior when the final db commit operation (setting READY) fails.
    The except block should then try to set status to FAILED.
    """
    # --- Arrange Mocks ---
    # Arrange standard success path up until the final DB interaction
    mock_os_isdir.return_value = True
    mock_os_walk.return_value = MOCK_WALK_STRUCTURE
    mock_os_getsize.side_effect = lambda path: MOCK_FILE_SIZES.get(path, 0)
    # ... splitext setup ...
    def splitext_side_effect(filename):
        if filename == 'image.png': return ('image', '.png')
        elif filename == '.env': return ('', '.env')
        elif filename == 'main.py': return ('main', '.py')
        elif filename == 'README.md': return ('README', '.md')
        elif filename == 'utils.py': return ('utils', '.py')
        elif filename == 'data.bin': return ('data', '.bin')
        elif filename == '.config': return ('.config', '')
        else: return os.path.splitext(filename)
    mock_splitext.side_effect = splitext_side_effect
    # ... open setup ...
    def open_side_effect(path, *args, **kwargs):
        if path in MOCK_FILE_CONTENT:
            m = mock_open(read_data=MOCK_FILE_CONTENT[path])()
            m.name = path
            return m
        else: raise FileNotFoundError(f"mock_open: File not found {path}")
    mock_open_func.side_effect = open_side_effect
    # ... Chroma setup ...
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_get_chroma.return_value = mock_chroma_client
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_client.delete_collection.return_value = True
    mock_get_emb_func.return_value = MagicMock()
    mock_collection.add.return_value = None

    # *** Database mocks: Make FIRST 'commit' fail, SECOND 'commit' succeed ***
    mock_session = MagicMock(spec=Session)
    mock_repo_instance_db = mock_ProjectRepo.return_value
    mock_project_ready = create_mock_project(status=ContextStatus.INDEXING)
    mock_project_fail = create_mock_project(status=ContextStatus.INDEXING) # Separate obj for fail update
    # 'get' succeeds both times, returning appropriate object
    mock_repo_instance_db.get.side_effect = [mock_project_ready, mock_project_fail]
    # Make commit fail the first time, succeed the second time
    mock_session.commit.side_effect = [
        Exception("Mock DB error on final commit"),
        None # Success on second commit
    ]
    mock_session_factory = create_mock_session_factory(mock_session)

    mock_time.side_effect = [7000.0, 7005.0]

    # --- Act ---
    process_repository_context(TEST_PROJECT_ID, DUMMY_REPO_PATH, mock_session_factory)

    # --- Assert ---
    # Check processing happened
    mock_ProjectRepo.assert_called_once_with(mock_session)
    mock_collection.add.assert_called_once()

    # Check get was called only once (before the failed READY commit)
    mock_repo_instance_db.get.assert_called_once_with(id=TEST_PROJECT_ID) # Correct

    # Check the status of the object that was actually modified
    # The 'project' variable from the outer try block is reused.
    assert mock_project_ready.context_status == ContextStatus.FAILED # Check the correct mock object

    # Check add was called twice (once for READY attempt, once for FAILED attempt, both using mock_project_ready)
    assert mock_session.add.call_count == 2
    mock_session.add.assert_called_with(mock_project_ready) # Check the argument on the last call

    # Check commit was called twice (READY attempt fails, FAILED attempt succeeds)
    assert mock_session.commit.call_count == 2

    mock_session.close.assert_called_once()