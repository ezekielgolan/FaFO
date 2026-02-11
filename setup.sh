#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found. Installing via Homebrew..."
  brew install ffmpeg
fi

echo "Setup complete."

if [ -z "${OPENAI_API_KEY:-}" ]; then
  read -r -p "Enter OPENAI_API_KEY (will be saved to .env): " OPENAI_API_KEY
  echo "OPENAI_API_KEY=${OPENAI_API_KEY}" > .env
  echo "Saved .env. To load it in your shell: source .env"
else
  echo "OPENAI_API_KEY already set in this shell."
fi
