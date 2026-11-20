#!/bin/bash
# GTA VI Content Factory installer for macOS.
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/<you>/gta-vi-content-factory/main/install.sh)"
# or, inside the downloaded folder:  ./install.sh
set -e
cd "$(dirname "$0")" 2>/dev/null || true

say() { printf "\n\033[1;35m▶ %s\033[0m\n" "$1"; }
ok()  { printf "  \033[1;32m✓\033[0m %s\n" "$1"; }

if [ ! -f "factory/__main__.py" ]; then
  say "Downloading the Content Factory"
  git clone --depth 1 https://github.com/${GVCF_REPO:-priyanshuratnakar/gta-vi-content-factory}.git "$HOME/gta-vi-content-factory"
  cd "$HOME/gta-vi-content-factory"
fi

if [ "$(uname)" != "Darwin" ]; then
  echo "This installer is for macOS. On Linux: install ffmpeg, yt-dlp, cloudflared and Python 3.10+, then run ./start.sh"
  exit 1
fi

say "Checking Homebrew (the Mac app installer for developer tools)"
if ! command -v brew >/dev/null 2>&1; then
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"
  else
    echo "  Homebrew isn't installed. Installing it (it will ask for your Mac password)…"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
  fi
fi
ok "Homebrew"

say "Installing video tools (ffmpeg, yt-dlp, cloudflared, python)"
for pkg in ffmpeg yt-dlp cloudflared python@3.12; do
  if brew list "$pkg" >/dev/null 2>&1; then ok "$pkg already installed"; else brew install "$pkg" && ok "$pkg"; fi
done

say "Setting up the factory's own Python (kept separate from your system)"
PY="$(brew --prefix)/bin/python3.12"
[ -x "$PY" ] || PY="$(command -v python3)"
"$PY" -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
if [ "$(uname -m)" = "arm64" ]; then
  ./.venv/bin/pip install --quiet mlx-whisper && ok "speech-to-text (Apple Silicon)" || echo "  (speech-to-text skipped; hooks still work)"
fi
ok "Python packages"

chmod +x start.command start.sh 2>/dev/null || true

say "Optional: free local AI"
if command -v ollama >/dev/null 2>&1 || [ -d /Applications/Ollama.app ]; then
  ok "Ollama found. If you'll use it, run once:  ollama pull qwen2.5vl:7b"
else
  echo "  Skipped. If you don't want to pay for Claude/OpenAI, install Ollama from https://ollama.com/download later."
fi

say "Done! Starting the Content Factory"
echo "  Next time, just double-click 'start.command' in this folder."
echo "  ★ Free & open source. Star it: https://github.com/priyanshuratnakar/gta-vi-content-factory"
echo "    Follow for updates: https://x.com/0xratnakar"
./start.sh
