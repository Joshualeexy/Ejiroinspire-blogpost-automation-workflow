import logging
import subprocess
import os
from typing import Any

try:
    import ollama
except Exception:
    ollama = None

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, model_name: str = None):
        self.model = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5")

    def generate(self, prompt: str, format: str | None = None, options: dict | None = None, **kwargs) -> Any:
        if ollama is None:
            raise RuntimeError("ollama package is not available")

        params = dict(kwargs)
        if format is not None:
            params["format"] = format
        if options is not None:
            params["options"] = options

        # Use the standard ollama.generate API and allow callers to pass keep_alive
        return ollama.generate(model=self.model, prompt=prompt, **params)

    def unload(self) -> None:
        # Try to unload via the Ollama API (keep_alive=0). If that fails, fall back to 'ollama stop <model>' subprocess.
        try:
            if ollama is None:
                raise RuntimeError("ollama package is not available")

            try:
                # Some Ollama versions accept keep_alive=0 on generate to immediately unload.
                ollama.generate(model=self.model, prompt="", keep_alive=0)
                logger.info("Requested Ollama to unload model via keep_alive=0")
                return
            except TypeError:
                # Older/newer client may not accept keep_alive param; fall through to subprocess fallback.
                raise
        except Exception as e:
            logger.warning("Ollama keep_alive unload failed (%s); falling back to `ollama stop`", e)

        # Fallback: run `ollama stop <model_name>` via subprocess
        try:
            subprocess.run(["ollama", "stop", self.model], check=True, capture_output=True)
            logger.info("Called `ollama stop %s` successfully", self.model)
        except Exception as e:
            logger.warning("Failed to unload Ollama model '%s' via subprocess: %s", self.model, e)
