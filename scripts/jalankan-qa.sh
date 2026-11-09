#!/usr/bin/env bash
# Menjalankan agent QA (skill qa-erp) tanpa interaksi, dengan langkah-langkahnya tampil di terminal.
#   ./scripts/jalankan-qa.sh                         # demo live: 3 skenario, issue ke GitHub
#   ./scripts/jalankan-qa.sh dry-run                 # gladi: tanpa GitHub, laporan ke qa-hasil/
#   ./scripts/jalankan-qa.sh dry-run lengkap url=http://localhost:18080
# Model bisa diganti: QA_MODEL=opus ./scripts/jalankan-qa.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p qa-hasil
log="qa-hasil/log-$(date +%Y%m%d-%H%M%S).jsonl"
echo "Agent QA mulai. Log lengkap: $log"
claude -p "/qa-erp $*" \
  --model "${QA_MODEL:-sonnet}" \
  --output-format stream-json --verbose \
  | tee "$log" \
  | jq -r --unbuffered -f scripts/tampilkan-langkah.jq
echo
echo "Ringkasan: qa-hasil/ringkasan.md"
