"""
modal_openai_server.py
======================
Alternative: runs vLLM's BUILT-IN OpenAI server directly.
This gives you 100% OpenAI API compatibility including:
  GET  /v1/models
  POST /v1/chat/completions
  POST /v1/completions
  POST /v1/embeddings  (if model supports it)

This is the recommended approach for plugging into GitHub Copilot BYOK.

Deploy:  modal deploy modal_openai_server.py
"""

import modal
import os

MODEL_ID  = "google/gemma-3-4b-it"   # ← change this freely
MODEL_DIR = "/models"
APP_NAME  = "gemma-openai-server"

vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.9.0-devel-ubuntu22.04",
        add_python="3.12",
    )
    .entrypoint([])
    .pip_install(
        "vllm==0.8.5",
        "huggingface_hub[hf_transfer]==0.26.2",
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "VLLM_ATTENTION_BACKEND": "FLASH_ATTN",
    })
)

model_volume = modal.Volume.from_name("gemma-model-cache", create_if_missing=True)
app = modal.App(APP_NAME)


@app.function(
    image=vllm_image,
    gpu=modal.gpu.A10G(),
    secrets=[modal.Secret.from_name("huggingface-secret")],
    volumes={MODEL_DIR: model_volume},
    container_idle_timeout=600,
    timeout=600,
    allow_concurrent_inputs=64,
)
@modal.asgi_app()
def openai_server():
    """
    Launches vLLM's native OpenAI-compatible FastAPI server.
    Returns the ASGI app to Modal for serving.
    """
    import subprocess, sys, os

    # Download model weights on first start
    local_model_path = f"{MODEL_DIR}/{MODEL_ID.replace('/', '--')}"
    if not os.path.exists(f"{local_model_path}/config.json"):
        print(f"[gemma-modal] Downloading {MODEL_ID} to volume …")
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=MODEL_ID,
            local_dir=local_model_path,
            token=os.environ.get("HF_TOKEN"),
            ignore_patterns=["*.msgpack", "flax_model*", "tf_model*"],
        )
        print("[gemma-modal] ✅ Download complete.")
    else:
        print(f"[gemma-modal] ✅ Model found in volume cache, skipping download.")

    from vllm.entrypoints.openai.api_server import build_async_engine_client_from_engine_args
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.entrypoints.openai.api_server import create_server_socket, init_app_state
    import vllm.entrypoints.openai.api_server as vllm_server

    # Build engine args
    engine_args = AsyncEngineArgs(
        model=local_model_path,
        dtype="bfloat16",
        max_model_len=8192,
        gpu_memory_utilization=0.90,
        enable_prefix_caching=True,
        served_model_name=MODEL_ID,  # so clients see the real model name
    )

    from vllm.entrypoints.openai.cli_args import make_arg_parser
    import argparse

    parser = make_arg_parser(argparse.ArgumentParser())
    args = parser.parse_args([
        "--model", local_model_path,
        "--dtype", "bfloat16",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.90",
        "--enable-prefix-caching",
        "--served-model-name", MODEL_ID,
        "--host", "0.0.0.0",
        "--port", "8000",
    ])

    # Use vLLM's built-in router
    from vllm.entrypoints.openai.api_server import build_app
    fastapi_app = build_app(args)
    return fastapi_app
