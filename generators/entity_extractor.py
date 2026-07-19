import json
from typing import List, Dict
from services.ollama_client import OllamaClient
from services.prompt_loader import load_prompt

class EntityExtractor:
    def __init__(self):
        self.client = OllamaClient()

    def extract(self, content: str) -> List[Dict[str, str]]:
        """
        Extract entities from article content.
        Returns a list of entity dicts, each with "name", "type", and "context".
        Types are: "product", "brand", "software", "company".
        """
        try:
            prompt = load_prompt("entity_extraction", content=content)
        except Exception:
            # Fallback if prompt is missing
            prompt = (
                f"Extract key entities (brands, products) from this article.\n"
                f"Return ONLY JSON: {{'entities': [{{'name': 'X', 'type': 'brand'}}]}}\n\n"
                f"Article: {content[:3000]}"
            )

        try:
            response = self.client.generate(
                prompt=prompt,
                format="json",
                options={"temperature": 0.2},
            )
            result = json.loads(response["response"])
            entities = result.get("entities", [])
            
            valid_types = {"product", "brand", "software", "company"}
            validated: List[Dict[str, str]] = []
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                name = entity.get("name", "").strip()
                etype = entity.get("type", "").strip().lower()
                if name and etype in valid_types:
                    validated.append(entity)
            return validated
        except Exception as e:
            print(f"Entity extraction failed: {e}")
            return []
