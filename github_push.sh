#!/usr/bin/env bash
# scripts/github_push.sh
# ======================
# Creates a GitHub repo and pushes the code.
# Requires: gh CLI (https://cli.github.com/)
#
# Usage:
#   chmod +x scripts/github_push.sh
#   gh auth login          # authenticate GitHub CLI first
#   ./scripts/github_push.sh

set -euo pipefail

REPO_NAME="gemma-modal"
DESCRIPTION="Run Gemma/HuggingFace LLMs on Modal.com as OpenAI-compatible API for VS Code Copilot"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║      Creating GitHub Repo & Pushing Code             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Init git if not already
if [ ! -d ".git" ]; then
  git init
  echo "✅  Git repo initialized."
fi

# Create .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
*.pyo
.env
.env.local
*.modal.toml
.modal.toml
node_modules/
.DS_Store
EOF

echo "✅  .gitignore created."

# Stage all files
git add -A

# Initial commit
git commit -m "feat: deploy Gemma/HuggingFace LLM on Modal with OpenAI-compatible API

- modal_openai_server.py: full vLLM OpenAI-compatible server
- modal_app.py: lightweight custom endpoint
- GitHub Actions CI/CD for auto-deploy on push
- VS Code Copilot BYOK configuration
- Deploy and test scripts" || echo "Nothing new to commit."

# Create GitHub repo (public – change to --private if preferred)
echo ""
echo "🐙  Creating GitHub repo '$REPO_NAME'…"
gh repo create "$REPO_NAME" \
  --public \
  --description "$DESCRIPTION" \
  --source . \
  --remote origin \
  --push

echo ""
echo "✅  Done!  Your repo:"
gh repo view --web || echo "   https://github.com/$(gh api user -q .login)/$REPO_NAME"
echo ""
echo "📋  Next steps:"
echo "   1. Add secrets to GitHub: Settings → Secrets → Actions"
echo "      MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, HF_TOKEN"
echo "   2. Push to main → auto-deploys via GitHub Actions"
echo "   3. Or deploy now: modal deploy modal_openai_server.py"
