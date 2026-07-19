import os
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str, **kwargs) -> str:
    """
    Load a prompt template from the prompts/ directory and substitute variables.

    Args:
        name: The prompt filename without extension (e.g. "outline", "article_buying_guide").
        **kwargs: Variables to substitute into the template using string.Template.

    Returns:
        The prompt string with variables substituted.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    raw = path.read_text(encoding="utf-8")

    if kwargs:
        template = Template(raw)
        return template.safe_substitute(**kwargs)
    return raw
