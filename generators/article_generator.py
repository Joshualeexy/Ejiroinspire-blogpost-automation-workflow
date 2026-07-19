import json
import os
import re
import time
from typing import Any, Dict, Optional

from research_agent import ResearchAgent, ResearchResult
from services.ollama_client import OllamaClient


class ArticleGenerator:
    def __init__(self, model_name: str = None, max_retries: int = 3, research_agent: Optional[ResearchAgent] = None):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3:30b")
        self.max_retries = max_retries
        self.client = OllamaClient(self.model_name)
        # Injectable so callers can share one ResearchAgent (and its rate
        # limiting) across many generate() calls, or swap the search backend.
        self.research_agent = research_agent or ResearchAgent()

    # -- search query -------------------------------------------------------

    def _search_query(self, topic: Dict[str, Any]) -> str:
        """Titles are written for readers ("Best Mesh WiFi Systems for Large
        Homes") and search badly -- they pull in blogs and marketplace pages
        instead of the product itself. primary_keyword is already the
        cleaner, product-focused term from topic generation, so prefer it."""
        return topic.get("primary_keyword") or topic["title"]

    # -- prompt --------------------------------------------------------------

    def _format_facts_block(self, research: ResearchResult) -> str:
        if not research.facts:
            return """
No verified reference information was found for this product. Write the
article in general, accurate terms. If a specification is absent from the
supplied reference facts, omit it entirely -- do not infer or estimate it."""

        lines = "\n".join(f"- {fact}" for fact in research.facts)
        return f"""
Reference facts (from live web search, current as of today):
{lines}

Use these as your source of truth for anything specific: specs, pricing
ranges, features, release info. Paraphrase in your own words -- do not copy
sentences verbatim. These facts are not exhaustive. For anything not covered
here:
- Never infer or estimate a number (battery life, dimensions, price,
  benchmarks, etc.).
- If a spec is commonly requested but not in the facts above, say
  specifications vary by model/retailer rather than inventing a value."""

    def _build_prompt(self, topic: Dict[str, Any], research: ResearchResult) -> str:
        if research.official_url:
            link_instructions = f"""
Product link:
{research.official_url}

This is a verified link to the product's likely official page. Include it
exactly as given, as a single natural Markdown link somewhere appropriate in
the article (for example when first introducing the product). Do not modify
it, and do not add any other external product links."""
        else:
            link_instructions = """
No verified product link is available. Do NOT include any product URLs or
links in the article -- do not guess or invent one."""

        facts_block = self._format_facts_block(research)

        return f"""You are a professional affiliate content writer for Ejiro Inspire.

Ejiro Inspire is a consumer review website that helps readers make informed
purchasing decisions through honest reviews, comparisons and buying guides.

Your goal is to create content that ranks well on Google and naturally
converts readers into affiliate clicks.

Write a COMPLETE article.

Requirements:
- Write between 1800 and 3000 words.
- Use Markdown.
- Write naturally.
- Explain products clearly.
- Include pros and cons.
- Include buying advice.
- Include FAQs.
- End with a conclusion.
- Use headings, lists, tables, bold text, blockquotes and fenced code blocks
  when appropriate.
- Ensure every Markdown heading is separated from the preceding paragraph by a
  blank line.
- Do not place headers and body text on the same line. Each heading should be
  clearly separated and easy to scan.
{link_instructions}
{facts_block}

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
    "title": "",
    "excerpt": "",
    "seo_title": "",
    "meta_description": "",
    "content": ""
}}"""

    # -- generation ---------------------------------------------------------

    def generate(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        query = self._search_query(topic)
        research = self.research_agent.research(query)
        prompt = self._build_prompt(topic, research)

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

                # Safety net: if we had a verified URL but the model dropped
                # it, append it rather than silently losing the link.
                if research.official_url and research.official_url not in article["content"]:
                    article["content"] += f"\n\n[Check the current price and availability]({research.official_url})\n"

                article["content"] = self._normalize_markdown(article["content"])
                article["product_url"] = research.official_url
                article["sources"] = [
                    {"title": s.title, "url": s.url, "domain": s.domain}
                    for s in research.sources
                ]
                return article

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                print(f"Retry {attempt + 1}: {e}")
                time.sleep(1)

    def _normalize_markdown(self, content: str) -> str:
        """Ensure Markdown headings are separated by blank lines."""
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        content = re.sub(r"(?m)([^\n])\n(#{1,6} )", r"\1\n\n\2", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip() + "\n"