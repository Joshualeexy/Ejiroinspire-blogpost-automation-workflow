from generators.topic_generator import TopicGenerator
from generators.article_generator import ArticleGenerator
from generators.image_prompt_generator import ImagePromptGenerator
from datetime import datetime
import traceback

from services.api import ApiClient
from services.comfy import ComfyClient
from services.markdown import to_html


def main():

    api = ApiClient()
    comfy = ComfyClient(workflow_path="services/workflow.json")

    topic_generator = TopicGenerator()
    article_generator = ArticleGenerator()
    image_prompt_generator = ImagePromptGenerator()

    while True:

        try:

            print(f"\n--- New session starting: {datetime.now().isoformat()} ---")

            # Generate Topic
            print("Starting stage: Generate Topic")
            topic = topic_generator.generate()
            print(f"Completed stage: Generate Topic — Topic: {topic['title']}")

            #
            # Skip duplicate topics
            #
            if api.topic_exists(topic["title"]):
                print("Topic already exists. Skipping.")
                continue

            # Generate Article
            print("Starting stage: Generate Article")
            article = article_generator.generate(topic)
            print("Completed stage: Generate Article")

            # Convert Markdown content to HTML for publishing
            print("Starting stage: Convert Markdown -> HTML")
            article["content"] = to_html(article["content"])
            print("Completed stage: Convert Markdown -> HTML")

            # Generate Image Prompt
            print("Starting stage: Generate Image Prompt")
            image_prompt = image_prompt_generator.generate(
                topic,
                article,
            )
            print("Completed stage: Generate Image Prompt")

            # Unload Ollama model to free GPU before SDXL image generation
            try:
                print("Unloading Ollama model...")
                image_prompt_generator.unload()
                print("Ollama model unloaded.")
            except Exception as e:
                print(f"Warning: failed to unload Ollama model: {e}")

            # Generate Featured Image
            print("Starting stage: Generate Featured Image")
            image = comfy.generate(
                prompt=image_prompt,
            )
            print("Completed stage: Generate Featured Image")

            # Publish Article (publish uploads the image internally)
            print("Starting stage: Publish Article")
            api.publish(
                article,
                image,
            )
            print(f"Completed stage: Publish Article — ✓ Published: {topic['title']}")

        except KeyboardInterrupt:
            print("\nStopping automation...")
            break

        except Exception:
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()