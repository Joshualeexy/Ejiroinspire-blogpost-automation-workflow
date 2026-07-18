import os
from services.ollama_client import OllamaClient


class ImagePromptGenerator:

    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv(
            "OLLAMA_MODEL",
            "qwen3:8b"
        )
        self.client = OllamaClient(self.model_name)

    def generate(self, topic, article) -> str:

        prompt = f"""
You are an expert Stable Diffusion XL prompt engineer.

Generate ONE prompt for a blog featured image.

Requirements:

- Photorealistic
- Professional
- Modern
- Premium lighting
- High detail
- 16:9 composition
- Clean background
- No people unless necessary
- No text
- No logos
- No watermark
- Suitable for a technology or consumer review website

Topic:

{topic["title"]}

Article excerpt:

{article["excerpt"]}

Return ONLY the image prompt.
"""

        response = self.client.generate(
            prompt=prompt,
        )

        print(response["response"].strip())
        return response["response"].strip()

    def unload(self) -> None:
        try:
            print("Unloading Ollama model...")
            self.client.unload()
            print("Ollama model unloaded.")
        except Exception as e:
            print(f"Warning: failed to unload Ollama model: {e}")