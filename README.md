# Ejiro Inspire — Automated Affiliate Content Generator

> A lightweight automation pipeline that generates evergreen product content, image prompts via Ollama, renders images with ComfyUI, and publishes articles via a backend API. Designed for continuous operation and production use — now open-source.

---

## Features

- Autonomously generates SEO-focused article topics and full articles.
- Uses Ollama models to craft image prompts for featured images.
- Optionally unloads Ollama models to free GPU VRAM before ComfyUI (SDXL) runs.
- Publishes content to a backend API (Laravel-style backend included in `backend/`).
- Simple, modular generators (`TopicGenerator`, `ArticleGenerator`, `ImagePromptGenerator`).

---

## Quick Start

1. Clone the repository:

```bash
git clone <repo-url>
cd Ejiroinspire
```

2. Create and activate a Python virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Set environment variables (see **Configuration**).

5. Run the automation:

```bash
python main.py
```

The script runs in a loop producing topics, articles, image prompts, generating images, and publishing.

---

## Configuration

The automation reads configuration from environment variables and local files.

- `OLLAMA_MODEL` — default model used by generators (e.g. `qwen3:8b`).
- Other service config may live in `config.py` or environment variables consumed by the backend API client.

You can create a `.env` file in the project root and use `python-dotenv` to load variables when running locally.

---

## How it Works (Pipeline)

1. Generate Topic (`TopicGenerator`) — produces a JSON topic describing article metadata.
2. Check duplicate topic against the backend API.
3. Generate Article (`ArticleGenerator`) — produces article content in Markdown and metadata.
4. Generate Image Prompt (`ImagePromptGenerator`) — uses Ollama to craft a single prompt for the featured image.
5. Unload Ollama model (`OllamaClient.unload()`) — tries `keep_alive=0` and falls back to `ollama stop <model>` to free GPU memory.
6. Generate image with ComfyUI (`ComfyClient`).
7. Publish the article and uploaded image via the API client.

The code prints concise stage markers so you can follow progress in logs.

---

## Ollama integration and unloading

This project centralizes Ollama usage in `services/ollama_client.py`.

- Use `OllamaClient.generate(...)` to run model inference.
- Call `OllamaClient.unload()` to release Ollama-managed GPU memory:
  - First attempts an API-driven unload with `keep_alive=0`.
  - If the installed Ollama client doesn't support this, it falls back to `ollama stop <model>` using `subprocess`.
  - Failures are logged as warnings — unloading never crashes the pipeline.

In `main.py`, `image_prompt_generator.unload()` is called after generating the prompt and before ComfyUI begins image generation. You will see messages like:

```
Unloading Ollama model...
Ollama model unloaded.
```

---

## Development

- Project layout (high level):

- `main.py` — runner that wires generators and services.
- `generators/` — `topic_generator.py`, `article_generator.py`, `image_prompt_generator.py`.
- `services/` — `ollama_client.py`, `comfy.py`, `api.py`, `markdown.py`.
- `backend/` — optional Laravel backend included for publishing integration.

### Running locally

1. Ensure Ollama is installed and running on the host (https://ollama.ai/docs).
2. Ensure ComfyUI or your SDXL provider is available and configured in `services/comfy.py`.

---

## Requirements

Install the pinned Python packages using `pip install -r requirements.txt`.

requirements.txt
```
annotated-types==0.7.0
anyio==4.14.2
certifi==2026.6.17
charset-normalizer==3.4.9
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.18
ollama==0.6.2
pydantic==2.13.4
pydantic_core==2.46.4
python-dotenv==1.2.2
requests==2.34.2
typing-inspection==0.4.2
typing_extensions==4.16.0
urllib3==2.7.0
markdown==3.7
```

---

## Contributing

Contributions welcome. Suggested workflow:

1. Fork the repo.
2. Create a feature branch.
3. Run tests (if added) and ensure formatting.
4. Open a PR with a clear description.

Please be careful when changing the behavior of generators — the public generator APIs are relied upon by `main.py`.

---

## License

Choose a license (e.g., MIT) and add a `LICENSE` file before publishing the repo. This README does not apply a license by default.

---

If you'd like, I can also add a `CONTRIBUTING.md`, a sample `.env.example`, and a minimal `LICENSE` file. Want me to add those?
