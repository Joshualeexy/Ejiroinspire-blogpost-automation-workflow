import json
from enum import Enum
from services.ollama_client import OllamaClient

class ArticleType(Enum):
    BUYING_GUIDE = "buying_guide"
    REVIEW = "review"
    COMPARISON = "comparison"
    TUTORIAL = "tutorial"
    INFORMATIONAL = "informational"
    LISTICLE = "listicle"

class Classifier:
    def __init__(self):
        self.client = OllamaClient()

    def classify(self, topic: str) -> ArticleType:
        """Classify the given topic into an ArticleType."""
        # Simple inline prompt for classification since we might not have classifier.txt
        prompt = (
            f"Analyze this blog post topic: '{topic}'\n"
            f"Classify it into one of the following types: {', '.join([t.value for t in ArticleType])}.\n"
            f"Return ONLY a JSON object with a single key 'type' containing the classification."
        )
        try:
            response = self.client.generate(prompt=prompt, format="json", options={"temperature": 0.1})
            result = json.loads(response["response"])
            type_str = result.get("type", "informational")
            return ArticleType(type_str)
        except Exception:
            return ArticleType.INFORMATIONAL

def classify(topic: str) -> ArticleType:
    return Classifier().classify(topic)
