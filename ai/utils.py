"""
ai/utils.py

Shared utility functions for the ai/ module.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """
    Load a prompt file from the ai/prompts/ directory.

    Args:
        filename: e.g. "system_prompt.md"

    Returns:
        The file content as a string.

    Raises:
        FileNotFoundError: if the prompt file does not exist.
    """
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}. "
            f"Make sure ai/prompts/{filename} exists."
        )
    return path.read_text(encoding="utf-8")


def load_crisis_response() -> str:
    """Return the pre-written crisis response text."""
    return load_prompt("crisis_response.md")
