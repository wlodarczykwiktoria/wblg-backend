import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Brak DATABASE_URL w .env lub w zmiennych środowiskowych")

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in CORS_ORIGINS.split(",")] if CORS_ORIGINS != "*" else ["*"]
