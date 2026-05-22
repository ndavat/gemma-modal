#!/usr/bin/env bash
# scripts/deploy.sh
# ==================
# One-shot: sets up secrets, deploys to Modal, and prints the endpoint URL.
#
# Usage:
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh
#
# Prerequisites:
#   pip install modal
#   modal token new           # authenticate with Modal
#   export HF_TOKEN=hf_xxx    # optional, needed for gated models (Gemma, Llama)

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║        Gemma on Modal – Deployment Script            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ─── 1. Check modal CLI is installed ─────────────────────────────────────────
if ! command -v modal &> /dev/null; then
  echo "❌  modal not found.  Installing…"
  pip install modal
fi

# ─── 2. Create HuggingFace secret in Modal (if HF_TOKEN is set) ──────────────
if [ -n "${HF_TOKEN:-}" ]; then
  echo "🔑  Creating/updating HuggingFace secret in Modal…"
  modal secret create huggingface-secret HF_TOKEN="$HF_TOKEN" --force || \
  modal secret create huggingface-secret HF_TOKEN="$HF_TOKEN"
  echo "   ✅  Secret 'huggingface-secret' created."
else
  echo "ℹ️   HF_TOKEN not set. Only public (non-gated) models will work."
  echo "     For Gemma or Llama, set: export HF_TOKEN=hf_your_token"
  # Create a dummy secret so the app doesn't error
  modal secret create huggingface-secret HF_TOKEN="" --force 2>/dev/null || true
fi

echo ""
echo "🚀  Deploying to Modal…"
echo "    (First deploy downloads the model – may take 5-10 min)"
echo ""

# ─── 3. Deploy ────────────────────────────────────────────────────────────────
modal deploy modal_openai_server.py

echo ""
echo "✅  Deployment complete!"
echo ""
echo "📋  Your OpenAI-compatible endpoint:"
echo ""
echo "    Base URL: https://YOUR-WORKSPACE--gemma-openai-server-openai-server.modal.run/v1"
echo "    Model ID: google/gemma-3-4b-it"
echo ""
echo "    (Find exact URL: modal app list | grep gemma)"
echo ""
echo "🔧  VS Code setup:"
echo "    1. Install GitHub Copilot extension (it's free with Copilot Free plan)"
echo "    2. Open Command Palette → 'Chat: Manage Language Models'"
echo "    3. Click 'Add Models' → 'OpenAI Compatible'"
echo "    4. Paste the Base URL above + any API key string"
echo "    5. Use Gemma in Copilot Chat (Ctrl+Alt+I)"
echo ""
