"""
modal_app.py
============
Deploys Google Gemma 4 (or any HuggingFace model) on Modal.com
as a fully OpenAI-compatible /v1/chat/completions endpoint.

Usage:
  modal deploy modal_app.py          # permanent deployment
  modal serve  modal_app.py          # temporary dev server
"""

import modal
import os

# ─── 1. PICK YOUR MODEL ──────────────────────────────────────────────────────
# Swap MODEL_ID to any HuggingFace model ID.  Examples:
#   "google/gemma-3-27b-it"          (27B – needs A100 80GB)
#   "google/gemma-3-12b-it"          (12B – A100 40GB is fine)
#   "google/gemma-3-4b-it"           (4B  – A10G is fine, cheaper)
#   "meta-llama/Meta-Llama-3.1-8B-Instruct"
#   "mistralai/Mistral-7B-Instruct-v0.3"
#   "Qwen/Qwen2.5-Coder-7B-Instruct" (great for coding tasks!)
MODEL_ID   = "google/gemma-3-4b-it"   # change this
MODEL_DIR  = "/models"
APP_NAME   = "gemma-vllm-api"

# ─── 2. GPU SELECTION ─────────────────────────────────────────────────────────
# A10G  = ~$1/hr – good for 4B–7B models
# A100  = ~$3/hr – needed for 12B+ models
# H100  = ~$6/hr – for very large models
GPU_CONFIG = modal.gpu.A10G(count=1)   # upgrade to A100 for bigger models

# ─── 3. CONTAINER IMAGE ──────────────────────────────────────────────────────
vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.9.0-devel-ubuntu22.04",
        add_python="3.12"
    )
    .entrypoint([])
    .pip_install(
        "vllm==0.8.5",
        "huggingface_hub[hf_transfer]==0.26.2",
        "fastapi",
        "uvicorn",
        "python-dotenv",
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",   # 3x faster downloads
        "VLLM_ATTENTION_BACKEND": "FLASH_ATTN",
    })
)

# ─── 4. VOLUME FOR MODEL CACHING ─────────────────────────────────────────────
# Persists the model weights so cold starts are instant after first download.
model_volume = modal.Volume.from_name("gemma-model-cache", create_if_missing=True)

app = modal.App(APP_NAME)

# ─── 5. THE VLLM SERVER CLASS ────────────────────────────────────────────────
@app.cls(
    image=vllm_image,
    gpu=GPU_CONFIG,
    secrets=[modal.Secret.from_name("huggingface-secret")],  # HF_TOKEN env var
    volumes={MODEL_DIR: model_volume},
    container_idle_timeout=10 * 60,   # scale to zero after 10 min idle
    timeout=5 * 60,                   # max request timeout
)
@modal.concurrent(max_inputs=32)
class VLLMServer:

    @modal.enter()
    def load_model(self):
        """Download (once) and load the model into GPU memory."""
        import subprocess, sys

        # Pre-download weights to the persistent volume
        print(f"[gemma-modal] Downloading {MODEL_ID} …")
        subprocess.run(
            [
                sys.executable, "-m", "huggingface_hub.commands.huggingface_cli",
                "download", MODEL_ID,
                "--local-dir", f"{MODEL_DIR}/{MODEL_ID}",
                "--token", os.environ.get("HF_TOKEN", ""),
            ],
            check=False,  # non-gated models don't need token
        )

        from vllm import AsyncLLMEngine, AsyncEngineArgs

        engine_args = AsyncEngineArgs(
            model=f"{MODEL_DIR}/{MODEL_ID}",
            dtype="bfloat16",
            max_model_len=8192,
            gpu_memory_utilization=0.90,
            enable_prefix_caching=True,
        )
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        self.model_id = MODEL_ID
        print(f"[gemma-modal] ✅ {MODEL_ID} loaded and ready.")

    # ── OpenAI-compatible /v1/chat/completions ────────────────────────────────
    @modal.web_endpoint(method="POST", docs=True)
    async def chat(self, request: dict) -> dict:
        """
        POST /chat
        Accepts an OpenAI-style chat/completions body and returns a response.
        """
        from vllm import SamplingParams
        from vllm.entrypoints.openai.protocol import ChatCompletionRequest

        messages   = request.get("messages", [])
        max_tokens = request.get("max_tokens", 1024)
        temperature = request.get("temperature", 0.7)
        stream     = request.get("stream", False)

        # Build a simple prompt from messages (proper chat template applied by vLLM)
        prompt = self._messages_to_prompt(messages)
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=request.get("top_p", 0.95),
            stop=request.get("stop", None),
        )

        import uuid
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        result_generator = self.engine.generate(prompt, sampling_params, request_id=request_id)
        final_output = None
        async for output in result_generator:
            final_output = output

        generated_text = final_output.outputs[0].text if final_output else ""
        prompt_tokens  = len(final_output.prompt_token_ids) if final_output else 0
        compl_tokens   = len(final_output.outputs[0].token_ids) if final_output else 0

        # Return OpenAI-compatible response envelope
        return {
            "id": "chatcmpl-gemma",
            "object": "chat.completion",
            "model": self.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": generated_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": compl_tokens,
                "total_tokens": prompt_tokens + compl_tokens,
            },
        }

    # ── Health check ──────────────────────────────────────────────────────────
    @modal.web_endpoint(method="GET")
    async def health(self) -> dict:
        return {"status": "ok", "model": self.model_id}

    def _messages_to_prompt(self, messages: list) -> str:
        """Simple fallback prompt builder; vLLM uses the model's chat template."""
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"<{role}>{content}</{role}>")
        parts.append("<assistant>")
        return "\n".join(parts)


# ─── 6. LOCAL DEV HELPER ─────────────────────────────────────────────────────
@app.local_entrypoint()
def main():
    """
    Quick smoke-test: run `modal run modal_app.py` to verify the endpoint works.
    """
    import json, urllib.request

    server = VLLMServer()
    payload = json.dumps({
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "Write a Python hello world."}],
        "max_tokens": 200,
    }).encode()

    req = urllib.request.Request(
        "http://localhost:8000/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    print(result["choices"][0]["message"]["content"])
