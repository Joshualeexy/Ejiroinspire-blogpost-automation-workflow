import json
import string
from services.ollama_client import OllamaClient
from services.prompt_loader import load_prompt
from generators.classifier import ArticleType

class OutlineGenerator:
    def __init__(self):
        self.client = OllamaClient()

    def generate(self, topic: dict, article_type: ArticleType, research_report=None) -> dict:
        """Generate a structured outline for the given topic."""
        # We will load the outline prompt. We might not have it saved, so I will fall back
        try:
            prompt_template = string.Template(load_prompt("outline"))
            research_context = ""
            if research_report and research_report.results:
                research_context = "RESEARCH CONTEXT:\n" + research_report.results[0].content[:2000]
                
            prompt = prompt_template.safe_substitute(
                title=topic.get("title", ""),
                article_type=article_type.value,
                category=topic.get("category", ""),
                primary_keyword=topic.get("primary_keyword", ""),
                secondary_keywords=", ".join(topic.get("secondary_keywords", [])),
                year="2026",
                research_context=research_context
            )
        except Exception:
            # Fallback if outline.txt is missing
            prompt = (
                f"Create a detailed article outline for: '{topic.get('title')}'\n"
                f"Type: {article_type.value}\n"
                f"Return ONLY valid JSON with a 'sections' list."
            )

        try:
            response = self.client.generate(prompt=prompt, format="json", options={"temperature": 0.4})
            return json.loads(response["response"])
        except Exception as e:
            print(f"Outline generation failed: {e}")
            return {"sections": []}
