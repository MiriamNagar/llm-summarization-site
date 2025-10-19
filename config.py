import os

# Point this to your running FastAPI service:
# e.g. API_URL = "http://127.0.0.1:8000"  (uvicorn app.main:app --reload)
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
