from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key)


def create_text_embedding(text: str) -> list[float]:
    """Create a single embedding vector from input text."""
    if not text or not text.strip():
        raise ValueError("query_text must not be empty")

    settings = get_settings()
    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.rag_embedding_model,
        input=text,
    )

    embedding = response.data[0].embedding
    if len(embedding) != settings.rag_embedding_dimensions:
        raise RuntimeError(
            f"Unexpected embedding dimension: {len(embedding)} != {settings.rag_embedding_dimensions}"
        )

    return embedding
