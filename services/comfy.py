import copy
import json
import random
import time
import uuid
from pathlib import Path

import requests

from config import COMFY_URL


class ComfyClient:
    """
    Client for interacting with a local ComfyUI server.
    """

    def __init__(
        self,
        workflow_path: str = "workflow.json",
        output_dir: str = "generated",
    ):
        self.server = COMFY_URL.rstrip("/")
        self.client_id = str(uuid.uuid4())

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        with open(workflow_path, "r", encoding="utf-8") as f:
            self.workflow = json.load(f)

    def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        checkpoint: str = "juggernautXL_ragnarok.safetensors",
        width: int = 1344,
        height: int = 768,
        steps: int = 25,
        cfg: float = 7,
        sampler: str = "euler",
        scheduler: str = "normal",
        denoise: float = 1.0,
        batch_size: int = 1,
        seed: int | None = None,
        filename_prefix: str = "featured",
    ) -> str:
        """
        Generate an image using ComfyUI.

        Returns:
            Local path to the generated image.
        """

        workflow = copy.deepcopy(self.workflow)

        #
        # Checkpoint
        #
        workflow["4"]["inputs"]["ckpt_name"] = checkpoint

        #
        # Positive Prompt
        #
        workflow["6"]["inputs"]["text"] = prompt

        #
        # Negative Prompt (optional override)
        #
        if negative_prompt:
            workflow["7"]["inputs"]["text"] = negative_prompt

        #
        # Image Size
        #
        workflow["5"]["inputs"]["width"] = width
        workflow["5"]["inputs"]["height"] = height
        workflow["5"]["inputs"]["batch_size"] = batch_size

        #
        # Sampler Settings
        #
        workflow["3"]["inputs"]["steps"] = steps
        workflow["3"]["inputs"]["cfg"] = cfg
        workflow["3"]["inputs"]["sampler_name"] = sampler
        workflow["3"]["inputs"]["scheduler"] = scheduler
        workflow["3"]["inputs"]["denoise"] = denoise

        #
        # Random Seed
        #
        workflow["3"]["inputs"]["seed"] = (
            seed if seed is not None else random.randint(0, 2**63 - 1)
        )

        #
        # Output filename
        #
        workflow["9"]["inputs"]["filename_prefix"] = filename_prefix

        #
        # Submit Workflow
        #
        response = requests.post(
            f"{self.server}/prompt",
            json={
                "prompt": workflow,
                "client_id": self.client_id,
            },
            timeout=30,
        )

        response.raise_for_status()

        prompt_id = response.json()["prompt_id"]

        return self._wait_for_image(prompt_id)

    def _wait_for_image(self, prompt_id: str) -> str:
        """
        Wait until ComfyUI finishes generation.
        """

        while True:

            response = requests.get(
                f"{self.server}/history/{prompt_id}",
                timeout=30,
            )

            response.raise_for_status()

            history = response.json()

            if prompt_id not in history:
                time.sleep(1)
                continue

            outputs = history[prompt_id]["outputs"]

            for node in outputs.values():

                if "images" not in node:
                    continue

                image = node["images"][0]

                return self._download(image)

            time.sleep(1)

    def _download(self, image: dict) -> str:
        """
        Download generated image from ComfyUI.
        """

        response = requests.get(
            f"{self.server}/view",
            params={
                "filename": image["filename"],
                "subfolder": image["subfolder"],
                "type": image["type"],
            },
            timeout=60,
        )

        response.raise_for_status()

        output = self.output_dir / image["filename"]

        output.write_bytes(response.content)

        return str(output.resolve())