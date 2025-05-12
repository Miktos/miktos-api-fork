import sys
print(f"--- check_import.py: Initial sys.path: {sys.path}")

# Ensure the project root is in sys.path for consistent imports, similar to how pytest might see it.
# (though pytest usually handles this by setting CWD or modifying path based on rootdir)
import os
project_root = "/Users/atorrella/Desktop/Miktos_VS-Code/miktos_backend"
if project_root not in sys.path:
    sys.path.insert(0, project_root)
print(f"--- check_import.py: Modified sys.path: {sys.path}")

print("--- check_import.py: Attempting to import tests.unit.test_gemini_function_calling ---")
try:
    import tests.unit.test_gemini_function_calling
    print("--- check_import.py: Import of tests.unit.test_gemini_function_calling successful ---")
except ModuleNotFoundError:
    print("--- check_import.py: ModuleNotFoundError. Trying to import test_gemini_function_calling directly from tests.unit ---")
    # This might be necessary if the current working directory is already /tests/unit or if PYTHONPATH is set up that way
    try:
        # Temporarily add tests/unit to path to simulate specific scenarios if the above failed
        # This is less ideal as it changes the environment significantly
        # sys.path.insert(0, os.path.join(project_root, "tests/unit"))
        # import test_gemini_function_calling
        print("--- check_import.py: (Skipping direct import attempt for now to avoid path confusion) ---")
        raise # re-raise the ModuleNotFoundError
    except Exception as e_direct:
        print(f"--- check_import.py: Direct import attempt from tests.unit also failed: {e_direct} ---")
        import traceback
        traceback.print_exc()
except Exception as e:
    print(f"--- check_import.py: Import failed with an unexpected error: {e} ---")
    import traceback
    traceback.print_exc()

print("--- check_import.py: Script finished. ---")
