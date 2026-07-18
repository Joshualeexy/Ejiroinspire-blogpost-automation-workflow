import json
import os
import time
from typing import Any, Dict

import ollama


class TopicGenerator:
    def __init__(self, model_name: str | None = None, max_retries: int = 3):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.max_retries = max_retries

    def generate(self) -> Dict[str, Any]:

        prompt = """
You are the lead SEO strategist for Ejiro Inspire.

Ejiro Inspire is an affiliate marketing website that helps consumers choose the best products before purchasing.

The website publishes:

- Product Reviews
- Product Comparisons
- Buying Guides
- Best Product Lists
- Alternatives
- Pros & Cons
- Product Roundups

The goal is to generate articles that attract high-buying-intent Google traffic and naturally monetize through affiliate links.

Generate ONE unique article idea.

Rules:

Generate ONE unique article idea.

This automation runs continuously.

Assume every topic you have previously generated already exists.

Your job is to maximize diversity.

Requirements:

- Every response MUST be substantially different from previous ones.
- Do not repeat the same products, brands or comparisons.
- Rotate naturally across brands, categories and article formats.
- Avoid generating MacBook, iPhone, Dell XPS and other extremely common examples unless they are genuinely the best choice.
- Prefer less obvious but commercially valuable products.
- Generate evergreen topics with strong affiliate intent.
- Focus only on products or software people research before buying.
- Do not generate news or trending topics.
- Do not generate politics, celebrities, entertainment, crypto, gambling, medical or legal topics.
- Do not generate generic lifestyle content.

Year rules:

- Do NOT append years just because it is common SEO practice.
- Buying Guides should NEVER contain a year.
- Reviews should NEVER contain a year unless the product's official name contains one.
- Comparisons should NEVER contain a year unless comparing model years.
- Alternatives should NEVER contain a year.
- Pros and Cons should NEVER contain a year.
- "Best Product Lists" MAY contain the current year only if it genuinely improves clarity.
- If the year is not essential, omit it completely.

Examples:

GOOD
✓ Best Mesh WiFi Systems
✓ Dyson V15 Detect Review
✓ MacBook Air M4 vs Surface Laptop 7
✓ Best Password Managers
✓ Logitech MX Master 3S Review

BAD
✗ Best WiFi Routers 2024
✗ Buying Guide 2024
✗ Best Headphones 2025
✗ Complete Router Guide 2026

Possible categories include (not limited to):

Smartphones
Laptops
Monitors
Gaming
PC Components
Headphones
Keyboards
Mice
Networking
Routers
Printers
Web Hosting
VPNs
Password Managers
Antivirus
Cloud Storage
Productivity Software
Streaming Services
AI Software
Video Editing Software
Office Equipment
Kitchen Appliances
Coffee Machines
Robot Vacuums
Smart Home
TVs
Projectors
Fitness Equipment
Beauty Products
Baby Products
Outdoor Gear
Automotive Accessories

Possible article formats:

Review
Comparison
Buying Guide
Best Product List
Best Product Under Budget
Alternatives
Pros and Cons
Is It Worth It?

Return ONLY valid JSON.

JSON structure:

{
  "type": string,
  "title": string,
  "category": string,
  "primary_keyword": string,
  "secondary_keywords": [
    string,
    string,
    string
  ]
}
"""

        valid_types = {
            "review",
            "comparison",
            "buying guide",
            "best product list",
            "best product under budget",
            "alternatives",
            "pros and cons",
            "is it worth it",
        }

        for attempt in range(self.max_retries):

            try:

                response = ollama.generate(
                    model=self.model_name,
                    prompt=prompt,
                    format="json",
                    options={
                        "temperature": 0.9,
                        "top_p": 0.95,
                        "repeat_penalty": 1.15,
                    },
                )

                topic = json.loads(response["response"])

                required = [
                    "type",
                    "title",
                    "category",
                    "primary_keyword",
                    "secondary_keywords",
                ]

                for field in required:
                    if field not in topic:
                        raise ValueError(f"Missing field: {field}")

                if not isinstance(topic["secondary_keywords"], list):
                    raise ValueError("secondary_keywords must be a list")

                if len(topic["secondary_keywords"]) < 3:
                    raise ValueError("Need at least 3 secondary keywords")

                if not all(
                    isinstance(x, str) and x.strip()
                    for x in topic["secondary_keywords"]
                ):
                    raise ValueError("Invalid secondary keywords")

                article_type = topic["type"].strip().lower()

                if article_type not in valid_types:
                    raise ValueError(f"Invalid article type: {article_type}")

                return topic

            except Exception as e:

                if attempt == self.max_retries - 1:
                    raise

                print(f"Retry {attempt + 1}: {e}")
                time.sleep(1)