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

# 환경 변수로 .env 파일 경로를 지정할 수 있도록 허용 (배포용)
# 지정되지 않은 경우 로컬 개발을 위한 기본 상대 경로 사용
_env_path = os.getenv("ENV_FILE_PATH")

if not _env_path:
    _fallback_path = Path(__file__).parent.parent / "backend" / ".env.local"
    if _fallback_path.exists():
        _env_path = str(_fallback_path)

if _env_path:
    load_dotenv(dotenv_path=_env_path)
else:
    # 기본 .env 파일이나 OS 환경변수 폴백
    load_dotenv()

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
