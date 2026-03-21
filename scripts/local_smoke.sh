#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
EMAIL="local-check@example.com"

echo "[1/6] Health check..."
curl -fsS "$BASE_URL/health" >/dev/null

echo "[2/6] Dev login..."
TOKENS=$(curl -fsS -X POST "$BASE_URL/api/v1/auth/dev/login" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\"}")
ACCESS=$(python - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())['access_token'])
PY
<<<"$TOKENS")

TMP_FILE="$(mktemp /tmp/reader-smoke-XXXX.fb2)"
cat > "$TMP_FILE" <<'FB2'
<?xml version='1.0' encoding='utf-8'?>
<FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'>
  <description><title-info><book-title>Smoke Book</book-title></title-info></description>
  <body>
    <section><title><p>One</p></title><p>Hello smoke</p></section>
    <section><title><p>Two</p></title><p>World smoke</p></section>
  </body>
</FictionBook>
FB2

echo "[3/6] Upload via API..."
UPLOAD=$(curl -fsS -X POST "$BASE_URL/api/v1/books/upload" \
  -H "Authorization: Bearer $ACCESS" \
  -F "title=Smoke Book" \
  -F "author=Smoke" \
  -F "visibility=private" \
  -F "file=@$TMP_FILE")
BOOK_ID=$(python - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())['book_id'])
PY
<<<"$UPLOAD")

echo "[4/6] Wait for processing..."
for _ in $(seq 1 25); do
  LIB=$(curl -fsS "$BASE_URL/api/v1/library?page=1&page_size=30" -H "Authorization: Bearer $ACCESS")
  STATUS=$(python - <<'PY'
import json,sys
book_id = sys.argv[1]
items = json.loads(sys.stdin.read()).get('items', [])
for item in items:
    if item.get('id') == book_id:
        print(item.get('status',''))
        raise SystemExit(0)
print('')
PY
"$BOOK_ID" <<<"$LIB")

  if [[ "$STATUS" == "ready" ]]; then
    break
  fi
  if [[ "$STATUS" == "failed" ]]; then
    echo "Processing failed"
    exit 1
  fi
  sleep 1
done

echo "[5/6] Verify processed chapters endpoint..."
CHAPTERS=$(curl -fsS "$BASE_URL/api/v1/books/$BOOK_ID/chapters" -H "Authorization: Bearer $ACCESS")
COUNT=$(python - <<'PY'
import json,sys
print(len(json.loads(sys.stdin.read())))
PY
<<<"$CHAPTERS")

if [[ "$COUNT" -lt 1 ]]; then
  echo "No chapters"
  exit 1
fi

echo "[6/6] Smoke check passed: book=$BOOK_ID chapters=$COUNT"
