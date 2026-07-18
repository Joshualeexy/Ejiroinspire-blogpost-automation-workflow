import json
from services.ollama_client import OllamaClient
import os
import time
from typing import Dict, Any


class ArticleGenerator:
    def __init__(self, model_name: str = None, max_retries: int = 3):
        self.model_name = model_name or os.getenv(
            "OLLAMA_MODEL",
            "qwen3:30b"
        )
        self.max_retries = max_retries
        self.client = OllamaClient(self.model_name)

    def generate(self, topic: Dict[str, Any]) -> Dict[str, Any]:

        prompt = f"""
You are a professional affiliate content writer for Ejiro Inspire.

Ejiro Inspire is a consumer review website that helps readers make informed purchasing decisions through honest reviews, comparisons and buying guides.

Your goal is to create content that ranks well on Google and naturally converts readers into affiliate clicks.

Write a COMPLETE article.

Requirements:

- Write between 1800 and 3000 words.
- Use Markdown.
- Write naturally.
- Be factual.
- Don't invent specifications.
- Explain products clearly.
- Include pros and cons.
- Include buying advice.
- Include FAQs.
- End with a conclusion.
- Use headings, lists, tables, bold text, blockquotes and fenced code blocks when appropriate.

SEO:

Primary keyword:
{topic["primary_keyword"]}

Secondary keywords:
{", ".join(topic["secondary_keywords"])}

Category:
{topic["category"]}

Title:
{topic["title"]}

Return ONLY valid JSON.

{{
    "title":"",
    "excerpt":"",
    "seo_title":"",
    "meta_description":"",
    "content":""
}}
"""

        for attempt in range(self.max_retries):

            try:

                response = self.client.generate(
                    prompt=prompt,
                    format="json",
                    options={
                        "temperature": 0.6
                    }
                )

                article = json.loads(response["response"])

                required = [
                    "title",
                    "excerpt",
                    "seo_title",
                    "meta_description",
                    "content",
                ]

                for field in required:
                    if not article.get(field):
                        raise ValueError(f"Missing {field}")

                return article

            except Exception:

                if attempt == self.max_retries - 1:
                    raise

                time.sleep(1)