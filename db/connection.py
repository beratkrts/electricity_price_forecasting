import os
import hashlib
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
if env_path:
    load_dotenv(env_path)

def get_db_url():
    """Generates PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "enerji_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

def calculate_checksum(data):
    """Calculates SHA-256 hash for raw API data payload (list or dict)."""
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')
    elif isinstance(data, str):
        serialized = data.encode('utf-8')
    else:
        serialized = bytes(data)
    return hashlib.sha256(serialized).hexdigest()
