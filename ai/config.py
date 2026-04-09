"""
ai/config.py

Loads environment variables for the ai/ module.
The backend's .env.local is the single source of truth for secrets.
This module loads it directly so ai/tools/ can access API keys
without importing from backend/app/.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Locate backend/.env.local relative to this file
# ai/config.py → ai/ → MoodPick/ → backend/.env.local
_env_path = Path(__file__).parent.parent / "backend" / ".env.local"

if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    # Fallback: try OS environment variables directly (e.g. in Docker / CI)
    pass

# --- Exported constants used by ai/tools/ ---
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Sanity check at import time (warns, does not raise)
_missing = [k for k, v in {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
}.items() if not v]

if _missing:
    import warnings
    warnings.warn(
        f"[ai/config] Missing environment variables: {_missing}. "
        f"Check backend/.env.local",
        stacklevel=2,
    )
