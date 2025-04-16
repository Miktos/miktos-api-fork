import uvicorn

if __name__ == "__main__":
    print("Starting Miktós API with simplified configuration...")
    uvicorn.run("miktos_backend.main:app", host="0.0.0.0", port=8000, reload=True)