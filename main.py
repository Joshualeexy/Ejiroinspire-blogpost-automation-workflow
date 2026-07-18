from generators.topic_generator import TopicGenerator
from generators.article_generator import ArticleGenerator
from generators.image_prompt_generator import ImagePromptGenerator

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

            #
            # Generate Topic
            #
            topic = topic_generator.generate()

            print(f"\nTopic: {topic['title']}")

            #
            # Skip duplicate topics
            #
            if api.topic_exists(topic["title"]):
                print("Topic already exists. Skipping.")
                continue

            #
            # Generate Article
            #
            article = article_generator.generate(topic)

            #
            # Convert Markdown content to HTML for publishing
            #
            article["content"] = to_html(article["content"])

            #
            # Generate Image Prompt
            #
            image_prompt = image_prompt_generator.generate(
                topic,
                article,
            )

            #
            # Generate Featured Image
            #
            image = comfy.generate(
                prompt=image_prompt,
            )

            #
            # Publish Article
            # (publish uploads the image internally)
            #
            api.publish(
                article,
                image,
            )

            print(f"✓ Published: {topic['title']}")

        except KeyboardInterrupt:
            print("\nStopping automation...")
            break

        except Exception as e:
            print(f"\nError: {e}")
            continue


if __name__ == "__main__":
    main()