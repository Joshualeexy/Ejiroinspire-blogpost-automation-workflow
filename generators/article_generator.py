import json
import os
import string
import time
from typing import Any, Dict
from services.ollama_client import OllamaClient
from services.prompt_loader import load_prompt
from generators.classifier import ArticleType
from research.base import ResearchReport

class ArticleGenerator:
    def __init__(self, model_name: str = None, max_retries: int = 3):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3:30b")
        self.max_retries = max_retries
        self.client = OllamaClient(self.model_name)

    def generate(self, topic: Dict[str, Any], article_type: ArticleType, outline: dict, research_report: ResearchReport = None) -> Dict[str, Any]:
        
        # Load the specific prompt for this article type
        prompt_name = f"article_{article_type.value}"
        try:
            prompt_template = string.Template(load_prompt(prompt_name))
        except Exception:
            # Fallback to a generic informational prompt if specific one is missing
            prompt_template = string.Template(load_prompt("article_informational"))

        research_context = ""
        if research_report and research_report.results:
            research_context = "RESEARCH CONTEXT:\n" + research_report.results[0].content[:3000]

        outline_str = json.dumps(outline, indent=2)

        prompt = prompt_template.safe_substitute(
            title=topic.get("title", ""),
            category=topic.get("category", ""),
            primary_keyword=topic.get("primary_keyword", ""),
            secondary_keywords=", ".join(topic.get("secondary_keywords", [])),
            year="2026",
            outline=outline_str,
            research_context=research_context
        )

        for attempt in range(self.max_retries):
            try:
                response = self.client.generate(
                    prompt=prompt,
                    format="json",
                    options={"temperature": 0.6},
                )

                article = json.loads(response["response"])

                required = ["title", "excerpt", "seo_title", "meta_description", "content"]
                for field in required:
                    if not article.get(field):
                        raise ValueError(f"Missing {field}")

                return article

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                print(f"Retry {attempt + 1}: {e}")
                time.sleep(1)