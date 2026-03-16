#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
else
  if ! ./.venv/bin/python3 -c "from pip._internal.cli.main import main" >/dev/null 2>&1; then
    echo "Detected broken pip in .venv; recreating environment..."
    rm -rf .venv
    python3 -m venv .venv
  fi
fi

source .venv/bin/activate

python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
python3 -m pip install -r "files and folders organizer - requirements.txt"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found. Installing via Homebrew..."
  brew install ffmpeg
fi

if ! python3 -c "import openai; import sys; sys.exit(0 if getattr(openai,'OpenAI',None) and openai.__file__ else 1)"; then
  echo "Detected broken openai install; reinstalling with no cache..."
  python3 -m pip uninstall -y openai
  python3 -m pip install --no-cache-dir openai
fi

echo "Setup complete."

if [ -z "${OPENAI_API_KEY:-}" ]; then
  read -r -p "Enter OPENAI_API_KEY (will be saved to files and folders organizer - .env): " OPENAI_API_KEY
  echo "export OPENAI_API_KEY=${OPENAI_API_KEY}" > "files and folders organizer - .env"
  echo "Saved .env. To load it in your shell: source \"files and folders organizer - .env\""
else
  echo "OPENAI_API_KEY already set in this shell."
fi
