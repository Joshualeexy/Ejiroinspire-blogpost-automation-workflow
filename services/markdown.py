import markdown
from typing import Any


def to_html(markdown_text: str) -> str:
    """
    Convert Markdown text to HTML with table and fenced code extensions.
    
    Args:
        markdown_text (str): The Markdown text to convert
        
    Returns:
        str: The converted HTML string
    """
    html = markdown.markdown(
        markdown_text,
        extensions=['tables', 'fenced_code']
    )
    return html