#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PASS=0
FAIL=0

run_test() {
    local name="$1"
    shift
    if "$@" &>/dev/null; then
        echo "[PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== SCImago Scraper Tests ==="

# 1. Dosyalar var mı?
run_test "journals.txt exists" test -f journals.txt
run_test "scrape_uc.py exists" test -f scrape_uc.py
run_test "convert_to_csv.py exists" test -f convert_to_csv.py
run_test "script.sh exists" test -f script.sh
run_test "setup.sh exists" test -f setup.sh
run_test "requirements.txt exists" test -f requirements.txt

# 2. Python sözdizimi kontrolü
run_test "scrape_uc.py syntax" python3 -m py_compile scrape_uc.py
run_test "convert_to_csv.py syntax" python3 -m py_compile convert_to_csv.py

# 3. venv var mı?
run_test "venv exists" test -d venv

# 4. convert_to_csv.py birim testi: dummy JSON → CSV
cat > /tmp/test_scrape.json <<'EOF'
[
  {"query":"Test Journal","sid":"12345","ok":true,"journal_url":"http://example.com","rows":[{"category":"Bio","year":"2024","quartile":"Q1"}],"error":null,"timestamp":"2026-05-19T00:00:00"}
]
EOF
source venv/bin/activate
run_test "convert_to_csv produces CSV" python3 convert_to_csv.py /tmp/test_scrape.json /tmp/test_output.csv
run_test "convert_to_csv CSV has header" grep -q '"query","sid","category","year","quartile","timestamp"' /tmp/test_output.csv
run_test "convert_to_csv CSV has data" grep -q 'Test Journal' /tmp/test_output.csv

# 5. parse_journal_line birim testi (scrape_uc.py içinden)
python3 -c "
import sys
sys.path.insert(0, '.')
from scrape_uc import parse_journal_line
assert parse_journal_line('Nature | 12345') == {'name': 'Nature', 'sid': '12345'}
assert parse_journal_line('Nature') == {'name': 'Nature', 'sid': None}
assert parse_journal_line('# comment') == {'name': '# comment', 'sid': None}
" && run_test "parse_journal_line unit" true || run_test "parse_journal_line unit" false

echo ""
echo "Results: $PASS passed, $FAIL failed"

rm -f /tmp/test_scrape.json /tmp/test_output.csv

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
