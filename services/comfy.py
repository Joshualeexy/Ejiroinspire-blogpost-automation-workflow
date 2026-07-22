import requests
import json
import time
import subprocess
import os
from pathlib import Path

class ComfyClient:
    """
    Client for interacting with a local ComfyUI server.
    """

    def __init__(
        self,
        workflow_path: str = "workflow.json",
        output_dir: str = "generated",
        comfy_server_process=None,  # For backward compatibility 
    ):
        self.server = "http://127.0.0.1:8188"
        self.client_id = "comfy_client_" + str(int(time.time()))
        self.session = requests.Session()

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        with open(workflow_path, "r", encoding="utf-8") as f:
            self.workflow = json.load(f)

    def start_server(self):
        """Starts the ComfyUI server as a background process and waits for it to become available."""
        from config import COMFY_START_CMD
        import signal
        
        print("Starting ComfyUI server...")
        self.comfy_process = subprocess.Popen(
            COMFY_START_CMD, 
            shell=True, 
            executable="/bin/bash",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid # To allow killing the whole process group
        )
        
        # Poll until server is up
        max_attempts = 120 # Can take a moment to load weights
        for i in range(max_attempts):
            try:
                response = self.session.get(self.server, timeout=2)
                if response.status_code == 200:
                    print("ComfyUI server is ready.")
                    time.sleep(2) # Give it an extra moment to fully initialize
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
            
        print("Warning: ComfyUI server did not start in time. Attempting generation anyway.")

    def stop_server(self):
        """Stops the ComfyUI server."""
        import signal
        if hasattr(self, 'comfy_process') and self.comfy_process:
            print("Stopping ComfyUI server...")
            try:
                # Kill the whole process group
                os.killpg(os.getpgid(self.comfy_process.pid), signal.SIGTERM)
                self.comfy_process.wait(timeout=10)
            except Exception as e:
                print(f"Failed to cleanly stop ComfyUI: {e}")
                try:
                    os.killpg(os.getpgid(self.comfy_process.pid), signal.SIGKILL)
                except Exception:
                    pass
            self.comfy_process = None
            print("ComfyUI server stopped.")

    def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        checkpoint: str = "juggernautXL_ragnarok.safetensors",
        width: int = 1344,
        height: int = 768,
        steps: int = 50,
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

        workflow = self.workflow.copy()

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
            seed if seed is not None else int(time.time()) % (2**63 - 1)
        )

        #
        # Output filename
        #
        workflow["9"]["inputs"]["filename_prefix"] = filename_prefix

        #
        # Submit Workflow
        #
        
        self.start_server()
        try:
            response = self.session.post(
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
        finally:
            self.stop_server()

    def _wait_for_image(self, prompt_id: str) -> str:
        """
        Wait until ComfyUI finishes generation.
        """

        while True:

            response = self.session.get(
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

        response = self.session.get(
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