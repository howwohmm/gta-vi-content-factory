#!/bin/bash
# Starts the Content Factory and opens it in your browser. Keep this window open while it posts.
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ ! -x .venv/bin/python ]; then
  echo "First time? Run ./install.sh first."; exit 1
fi
exec ./.venv/bin/python -m factory "$@"
