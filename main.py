import argparse
import json
import time
import traceback
from pathlib import Path

from generators.topic_generator import TopicGenerator
from generators.article_generator import ArticleGenerator
from generators.image_prompt_generator import ImagePromptGenerator
from generators.classifier import Classifier, ArticleType
from generators.outline_generator import OutlineGenerator
from generators.entity_extractor import EntityExtractor
from validation.article_validator import ArticleValidator
from research.crawl4ai_provider import Crawl4AiProvider
from research.duckduckgo import DuckDuckGoProvider

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

def run_pipeline(
    api: ApiClient, 
    comfy: ComfyClient, 
    topic_generator: TopicGenerator, 
    article_generator: ArticleGenerator, 
    image_prompt_generator: ImagePromptGenerator,
    classifier: Classifier,
    researcher: Crawl4AiProvider,
    outline_generator: OutlineGenerator,
    validator: ArticleValidator,
    entity_extractor: EntityExtractor
) -> None:
    state = load_state() or {"stage": "start", "status": "running"}

    if STATE_PATH.exists():
        print(f"Resuming saved pipeline state from stage: {state.get('stage')}")

    try:
        # 1. Topic Generation
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

        # 2. Topic Classification
        article_type_val = state.get("article_type")
        if state["stage"] in {"topic_checked", "topic_classified"}:
            if not article_type_val:
                print("Starting stage: Classify Topic")
                article_type = classifier.classify(topic["title"])
                print(f"Completed stage: Classify Topic — {article_type.value}")
                state.update({"stage": "topic_classified", "article_type": article_type.value})
                save_state(state)
            else:
                print(f"Resuming stage: Topic already classified — {article_type_val}")

        # 3. Research
        research_dict = state.get("research_report")
        if state["stage"] in {"topic_classified", "research_completed"}:
            if not research_dict:
                print("Starting stage: Research")
                query = f"{topic['primary_keyword']} {topic['title']}"
                report = researcher.search(query)
                print(f"Completed stage: Research — Found {len(report.results)} results")
                # Convert dataclass to dict for JSON serialization
                report_dict = {
                    "query": report.query,
                    "results": [{"url": r.url, "title": r.title, "content": r.content, "snippet": r.snippet} for r in report.results]
                }
                state.update({"stage": "research_completed", "research_report": report_dict})
                save_state(state)

        # Reconstruct research report object if exists
        from research.base import ResearchReport, SearchResult
        research_report = None
        if state.get("research_report"):
            rd = state["research_report"]
            results = [SearchResult(**r) for r in rd.get("results", [])]
            research_report = ResearchReport(query=rd["query"], results=results)

        # 4. Outline Generation
        outline = state.get("outline")
        if state["stage"] in {"research_completed", "outline_generated"}:
            if not outline:
                print("Starting stage: Generate Outline")
                article_type_enum = ArticleType(state["article_type"])
                outline = outline_generator.generate(topic, article_type_enum, research_report)
                print("Completed stage: Generate Outline")
                state.update({"stage": "outline_generated", "outline": outline})
                save_state(state)

        # 5. Article Generation
        article = state.get("article")
        if state["stage"] in {"outline_generated", "article_generated"}:
            if not article:
                print("Starting stage: Generate Article")
                article_type_enum = ArticleType(state["article_type"])
                article = article_generator.generate(topic, article_type_enum, outline, research_report)
                print("Completed stage: Generate Article")
                state.update({"stage": "article_generated", "article": article})
                save_state(state)

        # 6. Article Validation
        if state["stage"] == "article_generated":
            print("Starting stage: Validate Article")
            article_type_enum = ArticleType(state["article_type"])
            report = validator.validate(state["article"]["content"], article_type_enum)
            if not report.passed:
                print("Validation failed! Looping back to article generation.")
                for issue in report.issues:
                    print(f"[{issue.severity.upper()}] {issue.check}: {issue.message}")
                # Reset state to generate article again
                state["stage"] = "outline_generated"
                state["article"] = None
                save_state(state)
                return # Break out and let loop restart
            else:
                print("Completed stage: Validate Article — Passed")
                state["stage"] = "article_validated"
                save_state(state)

        # 7. Entity Extraction
        entities = state.get("entities")
        if state["stage"] in {"article_validated", "entities_extracted"}:
            if not entities:
                print("Starting stage: Extract Entities")
                entities = entity_extractor.extract(state["article"]["content"])
                print(f"Completed stage: Extract Entities — Extracted {len(entities)} entities")
                state["article"]["entities"] = entities
                state["article"]["article_type"] = state["article_type"]
                state.update({"stage": "entities_extracted", "entities": entities})
                save_state(state)

        # 8. Markdown Conversion
        if state["stage"] == "entities_extracted":
            print("Starting stage: Convert Markdown -> HTML")
            state["article"]["content"] = to_html(state["article"]["content"])
            print("Completed stage: Convert Markdown -> HTML")
            state["stage"] = "markdown_converted"
            save_state(state)

        # 9. Image Prompt Generation
        image_prompt = state.get("image_prompt")
        if state["stage"] in {"markdown_converted", "image_prompt_generated"}:
            if not image_prompt:
                print("Starting stage: Generate Image Prompt")
                image_prompt = image_prompt_generator.generate(topic, state["article"])
                print("Completed stage: Generate Image Prompt")
                state.update({"stage": "image_prompt_generated", "image_prompt": image_prompt})
                save_state(state)

        # 10. Unload Ollama
        if state["stage"] == "image_prompt_generated":
            try:
                print("Unloading Ollama model...")
                image_prompt_generator.unload()
                print("Ollama model unloaded.")
            except Exception as e:
                print(f"Warning: failed to unload Ollama model: {e}")
            state["stage"] = "image_generated"
            save_state(state)

        # 11. Image Generation
        image_path = state.get("image_path")
        if state["stage"] in {"image_generated", "publish_ready"}:
            if not image_path:
                print("Starting stage: Generate Featured Image")
                image_path = comfy.generate(prompt=image_prompt)
                print("Completed stage: Generate Featured Image")
                state.update({"stage": "publish_ready", "image_path": image_path})
                save_state(state)

        # 12. Publish
        if state["stage"] == "publish_ready":
            print("Starting stage: Publish Article")
            api.publish(state["article"], image_path)
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
    
    # Initialize new modules
    classifier = Classifier()
    researcher = Crawl4AiProvider()
    outline_generator = OutlineGenerator()
    validator = ArticleValidator()
    entity_extractor = EntityExtractor()

    while True:
        run_pipeline(
            api, comfy, topic_generator, article_generator, image_prompt_generator,
            classifier, researcher, outline_generator, validator, entity_extractor
        )

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
