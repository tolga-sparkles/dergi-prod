#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Ortam kontrolleri
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: '$1' is not installed. $2"
        exit 1
    fi
}

check_cmd python3 "Please install Python 3."
check_cmd xvfb-run "Please install xvfb (e.g. apt-get install xvfb)."

if command -v google-chrome &>/dev/null; then
    echo "Chrome: $(google-chrome --version)"
elif command -v chromium &>/dev/null; then
    echo "Chromium: $(chromium --version)"
elif command -v chromium-browser &>/dev/null; then
    echo "Chromium: $(chromium-browser --version)"
else
    echo "ERROR: Google Chrome or Chromium not found."
    exit 1
fi

# Proje içindeki venv'i kullan
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found at $VENV_DIR"
    echo "Run setup first: bash setup.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"

mkdir -p outputs

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT_JSON="outputs/result_${TIMESTAMP}.json"
OUT_CSV="outputs/result_${TIMESTAMP}.csv"
LOG_FILE="outputs/scrape.log"

# Son state dosyasını bul (resume desteği)
LATEST_JSON=$(ls -1t outputs/result_*.json 2>/dev/null | head -n 1 || true)
STATE_ARG=""
MODE="full"
if [ -n "$LATEST_JSON" ]; then
    echo "Resuming from previous state: $LATEST_JSON"
    STATE_ARG="--state $LATEST_JSON"
    MODE="incremental"
fi

# Chrome versiyonu tespit et
CHROME_VER="unknown"
if command -v google-chrome &>/dev/null; then
    CHROME_VER=$(google-chrome --version 2>/dev/null | grep -oP '\d+' | head -1 || echo "unknown")
elif command -v chromium &>/dev/null; then
    CHROME_VER=$(chromium --version 2>/dev/null | grep -oP '\d+' | head -1 || echo "unknown")
fi

START_TIME=$SECONDS

echo "[1/2] Scraping quartiles (undetected Chrome)..."
xvfb-run --auto-servernum python3 scrape_uc.py journals.txt "$OUT_JSON" $STATE_ARG

echo "[2/2] Converting JSON to CSV..."
python3 convert_to_csv.py "$OUT_JSON" "$OUT_CSV"

DURATION=$((SECONDS - START_TIME))
DURATION_FMT="${DURATION}s"
if [ $DURATION -ge 60 ]; then
    DURATION_FMT="$((DURATION / 60))m$((DURATION % 60))s"
fi

echo "Done."
echo "JSON: $(pwd)/$OUT_JSON"
echo "CSV : $(pwd)/$OUT_CSV"

# Özet log yaz
python3 -c "
import json, sys
from pathlib import Path
from datetime import datetime

f = Path('$OUT_JSON')
if not f.exists():
    sys.exit(0)

data = json.loads(f.read_text(encoding='utf-8'))
total = len(data)
ok = sum(1 for d in data if d.get('ok'))
err = total - ok
rows = sum(len(d.get('rows', [])) for d in data)
errors = [d['query'] for d in data if not d.get('ok')]
error_str = ', '.join(errors) if errors else 'none'
if len(error_str) > 100:
    error_str = error_str[:97] + '...'

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
log_line = (
    f'[{now}] {total} total | {ok} OK | {err} ERR | {rows} rows | '
    f'duration=${DURATION_FMT} | mode=${MODE} | chrome=${CHROME_VER} | '
    f'errors=[{error_str}] | file={f.name}'
)
with open('$LOG_FILE', 'a', encoding='utf-8') as lf:
    lf.write(log_line + '\n')
print(f'Log: {log_line}')
"
