"""ai/clients.py

Process-wide singletons for external API clients.

- get_openai(): AsyncOpenAI 단일 인스턴스 (lazy)
- close_clients(): FastAPI lifespan 종료 시 호출하여 httpx pool 정리
"""
from __future__ import annotations

from openai import AsyncOpenAI

from ai.config import OPENAI_API_KEY


_openai_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    """Lazy 싱글톤. 첫 호출에서 생성, 이후 같은 인스턴스 반환."""
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set. Check backend/.env.local")
        _openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


async def close_clients() -> None:
    """FastAPI lifespan 종료 시 호출. httpx connection pool 정리."""
    global _openai_client
    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
