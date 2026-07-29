# api/index.py
import sys
import os

# Append the backend directory to Python path so Vercel can resolve local imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# Import the existing FastAPI app instance
# pyrefly: ignore [missing-import]
from main import app