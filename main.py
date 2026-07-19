from generators.topic_generator import TopicGenerator
from generators.article_generator import ArticleGenerator
from generators.image_prompt_generator import ImagePromptGenerator
from datetime import datetime
import argparse
import json
import time
import traceback
from pathlib import Path

from services.api import ApiClient
from services.comfy import ComfyClient
from services.markdown import to_html

STATE_PATH = Path("pipeline_state.json")


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to load saved state: {e}")
        return None


def clear_state() -> None:
    STATE_PATH.unlink(missing_ok=True)


def run_pipeline(api: ApiClient, comfy: ComfyClient, topic_generator: TopicGenerator, article_generator: ArticleGenerator, image_prompt_generator: ImagePromptGenerator) -> None:
    state = load_state() or {"stage": "start", "status": "running"}

    if STATE_PATH.exists():
        print(f"Resuming saved pipeline state from stage: {state.get('stage')}")

    try:
        topic = state.get("topic")
        if state["stage"] in {"start", "topic_generated"}:
            if not topic:
                print("Starting stage: Generate Topic")
                topic = topic_generator.generate()
                print(f"Completed stage: Generate Topic — Topic: {topic['title']}")
                state.update({"stage": "topic_generated", "topic": topic})
                save_state(state)
            else:
                print(f"Resuming stage: Topic already generated — {topic['title']}")

            if api.topic_exists(topic["title"]):
                print("Topic already exists. Skipping.")
                clear_state()
                return

            state["stage"] = "topic_checked"
            save_state(state)

        article = state.get("article")
        if state["stage"] in {"topic_checked", "article_generated"}:
            if not article:
                print("Starting stage: Generate Article")
                article = article_generator.generate(topic)
                print("Completed stage: Generate Article")
                state.update({"stage": "article_generated", "article": article})
                save_state(state)

        if state["stage"] == "article_generated":
            print("Starting stage: Convert Markdown -> HTML")
            article["content"] = to_html(article["content"])
            print("Completed stage: Convert Markdown -> HTML")
            state.update({"stage": "markdown_converted", "article": article})
            save_state(state)

        image_prompt = state.get("image_prompt")
        if state["stage"] in {"markdown_converted", "image_prompt_generated"}:
            if not image_prompt:
                print("Starting stage: Generate Image Prompt")
                image_prompt = image_prompt_generator.generate(topic, article)
                print("Completed stage: Generate Image Prompt")
                state.update({"stage": "image_prompt_generated", "image_prompt": image_prompt})
                save_state(state)

        if state["stage"] == "image_prompt_generated":
            try:
                print("Unloading Ollama model...")
                image_prompt_generator.unload()
                print("Ollama model unloaded.")
            except Exception as e:
                print(f"Warning: failed to unload Ollama model: {e}")
            state["stage"] = "image_generated"
            save_state(state)

        image_path = state.get("image_path")
        if state["stage"] in {"image_generated", "publish_ready"}:
            if not image_path:
                print("Starting stage: Generate Featured Image")
                image_path = comfy.generate(prompt=image_prompt)
                print("Completed stage: Generate Featured Image")
                state.update({"stage": "publish_ready", "image_path": image_path})
                save_state(state)

        if state["stage"] == "publish_ready":
            print("Starting stage: Publish Article")
            api.publish(article, image_path)
            print(f"Completed stage: Publish Article — ✓ Published: {topic['title']}")
            clear_state()

    except KeyboardInterrupt:
        print("\nStopping automation...")
        state["status"] = "interrupted"
        save_state(state)
        raise

    except Exception:
        traceback.print_exc()
        state["status"] = "failed"
        save_state(state)
        print("Pipeline failed and state was saved. Restart the process to resume.")
        return


def main(clear_saved_state: bool = False):
    if clear_saved_state:
        print("Clearing saved pipeline state before starting.")
        clear_state()

    api = ApiClient()
    comfy = ComfyClient(workflow_path="services/workflow.json")

    topic_generator = TopicGenerator()
    article_generator = ArticleGenerator()
    image_prompt_generator = ImagePromptGenerator()

    while True:
        run_pipeline(api, comfy, topic_generator, article_generator, image_prompt_generator)

        if STATE_PATH.exists():
            print("Saved state exists. Exiting to avoid overwriting incomplete session.")
            break

        print("Sleeping before next session...")
        time.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Ejiro Inspire automation pipeline.")
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear saved pipeline state before starting a new run.",
    )
    args = parser.parse_args()
    main(clear_saved_state=args.clear_state)
