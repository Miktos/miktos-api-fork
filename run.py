# run.py
import uvicorn
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    port = int(os.environ.get("PORT", 8000))
    print(f"Attempting to run app 'miktos_backend.main:app' on port {port} with reload...")
    uvicorn.run("miktos_backend.main:app", host="0.0.0.0", port=port, reload=True)