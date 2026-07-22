# Ejiro Inspire Automation

Automated content pipeline for Ejiro Inspire. It generates affiliate-focused article topics, researches the web, creates an outline and long-form article with Ollama, validates the result, extracts entities, generates a featured image through ComfyUI, and publishes the final HTML article to the backend API.

The project is designed to run locally with GPU-backed services. It keeps resumable state in `pipeline_state.json`, so interrupted runs can continue from the last completed stage.

## What It Does

- Generates diverse affiliate article topics from curated product and lifestyle categories.
- Avoids recently used categories and exact duplicate titles through `generated_topics.json`.
- Rejects stale year patterns in titles, especially `2024` style SEO leftovers.
- Maps topic formats such as `Review`, `Buying Guide`, `Alternatives`, and `Is It Worth It` to the closest article template.
- Uses DuckDuckGo plus Crawl4AI to fetch live research context.
- Builds a structured outline before article generation.
- Generates long-form Markdown articles using strict prompt templates in `prompts/`.
- Validates minimum content quality before continuing.
- Converts Markdown to HTML before publishing.
- Extracts entities for products, brands, software, and companies.
- Generates an SDXL-style featured image prompt, unloads Ollama, starts ComfyUI, renders the image, and uploads it with the article.

## Requirements

- Python 3.10 or newer.
- Ollama installed and running.
- A local Ollama model suitable for JSON and long-form content generation.
- Playwright browser dependencies for Crawl4AI.
- ComfyUI available locally.
- Backend API credentials for topic checking and publishing.

Install Python packages:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

Make sure Ollama is running and the configured model exists:

```bash
ollama list
```

## Configuration

Runtime configuration is loaded from the local `config.py`, which is intentionally ignored by git because it can contain sensitive values. Keep that file local.

Expected values:

```python
OLLAMA_MODEL = "qwen3:30b"
API_URL = "https://your-api.example.com/api/admin"
API_TOKEN = "your_api_token"
COMFY_URL = "http://127.0.0.1:8188"
COMFY_START_CMD = "cd ~/comfyui/ComfyUI && source venv/bin/activate && python main.py"
```

Notes:

- `API_URL` is used for `/automation/check-topic` and `/automation/publish`.
- `API_TOKEN` is sent as a bearer token.
- `COMFY_START_CMD` is executed when image generation begins.
- The current Comfy client posts to `http://127.0.0.1:8188`, so run ComfyUI on that address unless you update `services/comfy.py`.
- `OLLAMA_MODEL` is used by default across topic, outline, article, entity, and image prompt generation. Some generators define fallback model names if the environment value is missing.

## Running The Pipeline

Start or resume automation:

```bash
python main.py
```

Start fresh and discard saved pipeline state:

```bash
python main.py --clear-state
```

The script runs continuously. After one article publishes successfully, it clears `pipeline_state.json`, waits 10 seconds, and starts the next article.

## Pipeline Stages

`main.py` runs these stages in order:

1. `topic_generated`: `TopicGenerator` picks a category, product family, and article format, then asks Ollama for a short SEO topic.
2. `topic_checked`: `ApiClient.topic_exists()` checks whether the backend already has the topic.
3. `topic_classified`: the generated topic format is mapped to an `ArticleType`; the classifier is only used as a fallback.
4. `research_completed`: `Crawl4AiProvider` searches DuckDuckGo and crawls up to 3 pages.
5. `outline_generated`: `OutlineGenerator` creates a JSON outline from the topic and research context.
6. `article_generated`: `ArticleGenerator` uses the matching prompt in `prompts/article_*.txt` and requires valid JSON article output.
7. `article_validated`: `ArticleValidator` checks content presence, minimum words, and Markdown heading structure.
8. `entities_extracted`: `EntityExtractor` adds product, brand, software, and company entities.
9. `markdown_converted`: Markdown article content is converted to HTML.
10. `image_prompt_generated`: `ImagePromptGenerator` creates a featured-image prompt.
11. `image_generated`: Ollama is unloaded to free VRAM, then ComfyUI generates the image.
12. `publish_ready`: `ApiClient.publish()` uploads article fields plus the generated image.

## State And Recovery

`pipeline_state.json` stores the latest successful stage and data needed to resume. If the process stops after a partial run, start it again with:

```bash
python main.py
```

Use `--clear-state` when you want to abandon the saved run:

```bash
python main.py --clear-state
```

Important behavior:

- Topic generation failures before a topic exists do not preserve state because there is nothing useful to resume.
- Article validation failures reset the stage to `outline_generated` and retry article generation automatically.
- After 3 validation failures, state is saved for inspection instead of looping forever.
- Publish or image generation failures save state so the same article can resume after the dependency is fixed.

## Topic Generation

Topic generation is controlled by `generators/topic_generator.py`.

It uses curated categories and product families, then asks Ollama for JSON shaped like:

```json
{
  "type": "Review",
  "title": "WD Red NAS Drives Review",
  "category": "NAS",
  "primary_keyword": "WD Red NAS drives",
  "secondary_keywords": ["NAS hard drives", "WD Red review", "home NAS storage"]
}
```

Safeguards:

- Exact duplicate titles are rejected against `generated_topics.json`.
- Recent categories are avoided to reduce repetitive article runs.
- Titles are capped by prompt rules at short, punchy SEO titles.
- Stale or disallowed year patterns are rejected or stripped.
- Each retry chooses a fresh category, product family, and format.

## Article Prompts

Article prompts live in:

- `prompts/article_review.txt`
- `prompts/article_buying_guide.txt`
- `prompts/article_comparison.txt`
- `prompts/article_listicle.txt`
- `prompts/article_tutorial.txt`
- `prompts/article_informational.txt`

Each prompt requires:

- JSON-only response.
- Required fields: `title`, `excerpt`, `seo_title`, `meta_description`, `content`.
- Complete Markdown article in `content`.
- 1800 to 3000 words.
- H2 and H3 structure.
- FAQ section.
- No article-body images or placeholders.
- No banned AI filler phrases.

The code also rejects article outputs under 500 words or without `##` headings before saving them.

## Research

Research is handled by `research/crawl4ai_provider.py`.

The provider:

- Uses DuckDuckGo via `ddgs`.
- Uses the `lite` backend for better reliability in automated environments.
- Crawls up to 3 results with `AsyncWebCrawler`.
- Saves URL, title, snippet, and Markdown content into pipeline state.
- Falls back from `primary_keyword + title` to `title`, then to `primary_keyword` if no results are found.

Crawl4AI is pointed at the project directory with `CRAWL4_AI_BASE_DIRECTORY` to avoid write issues in locked-down home directories.

## Image Generation

Image generation has two phases:

1. `ImagePromptGenerator` asks Ollama for a photorealistic SDXL-style featured image prompt.
2. `ComfyClient` starts ComfyUI, submits `services/workflow.json`, waits for the image, downloads it into `generated/`, then stops the ComfyUI process it started.

Default Comfy parameters:

- Server: `http://127.0.0.1:8188`
- Workflow: `services/workflow.json`
- Output directory: `generated/`
- Checkpoint: `juggernautXL_ragnarok.safetensors`
- Size: `1344x768`
- Steps: `50`
- Sampler: `euler`

Before ComfyUI starts, the pipeline calls `OllamaClient.unload()` to free VRAM. It first tries `keep_alive=0`, then falls back to `ollama stop <model>`.

## Backend API Contract

`services/api.py` expects these endpoints under `API_URL`:

### Check Topic

```text
POST /automation/check-topic
```

Request body:

```json
{
  "title": "Article title"
}
```

Expected response:

```json
{
  "exists": false
}
```

### Publish

```text
POST /automation/publish
```

Multipart fields:

- `title`
- `slug`
- `excerpt`
- `content`
- `category_id`, if present
- `featured_image`

The client retries failed publish attempts up to 3 times and prints the response body when available.

## Generated And Local Files

- `pipeline_state.json`: resumable run state. Safe to delete when abandoning a run.
- `generated_topics.json`: local title/category history for deduplication.
- `generated/`: downloaded ComfyUI images.
- `.crawl4ai/`: Crawl4AI runtime data.
- `config.py`: local sensitive configuration, ignored by git.
- `.env`: optional local environment file, ignored by git.

## Troubleshooting

### The script says saved state exists and exits

Open `pipeline_state.json` and check `stage` and `status`.

- If the dependency is fixed and the state is resumable, run `python main.py`.
- If you want a fresh article, run `python main.py --clear-state`.

### Topic generation keeps failing

Common causes:

- The model keeps returning duplicate titles already in `generated_topics.json`.
- The model keeps adding stale years.
- The selected model is too small or not following JSON instructions reliably.

The generator retries with fresh topic inputs. If failures persist, inspect `generated_topics.json` and consider using a stronger Ollama model.

### Articles are too short

The article prompts require long-form output, and `ArticleGenerator` rejects short outputs under 500 words. If this still happens repeatedly:

- Use a stronger model for `OLLAMA_MODEL`.
- Check that the correct prompt file exists for the article type.
- Inspect `pipeline_state.json` for the selected `article_type`.
- Check Ollama context limits for the configured model.

### ComfyUI starts but image generation fails

Check:

- ComfyUI is available at `127.0.0.1:8188`.
- `COMFY_START_CMD` points to the correct ComfyUI environment.
- `services/workflow.json` matches your installed ComfyUI nodes.
- The checkpoint name exists in your ComfyUI models directory.
- Ollama was unloaded successfully before image generation.

### Publish fails

Check:

- `API_URL` is correct.
- `API_TOKEN` is valid.
- The backend accepts the expected multipart fields.
- The generated image path in `pipeline_state.json` exists.

## Development Notes

Run a syntax check after code edits:

```bash
python -m py_compile main.py generators/*.py services/*.py research/*.py validation/*.py
```

The project currently has no automated test suite. The safest manual test is a full run with a real Ollama model, Crawl4AI browser install, ComfyUI setup, and backend API credentials.
