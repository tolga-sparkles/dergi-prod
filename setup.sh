#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== SCImago Quartiles Scraper Setup ==="

# Python kontrolü
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed."
    exit 1
fi

# Google Chrome / Chromium kontrolü
if command -v google-chrome &>/dev/null; then
    echo "Found: $(google-chrome --version)"
elif command -v chromium &>/dev/null; then
    echo "Found: $(chromium --version)"
elif command -v chromium-browser &>/dev/null; then
    echo "Found: $(chromium-browser --version)"
else
    echo "WARNING: Google Chrome or Chromium not found."
    echo "Please install Chrome before running the scraper."
fi

# xvfb kontrolü
if command -v xvfb-run &>/dev/null; then
    echo "Found: xvfb-run (for headless server environments)"
else
    echo "WARNING: xvfb-run not found. On a server without display, install xvfb."
fi

# venv oluştur (proje içinde)
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment in $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing Python dependencies ..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete. Activate the environment with:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Run the scraper:"
echo "  bash script.sh"
