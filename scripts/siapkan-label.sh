#!/usr/bin/env bash
# Membuat (atau memperbarui) label yang dipakai rantai QA → perbaikan. Aman dijalankan berulang.
#   ./scripts/siapkan-label.sh            # repo dari folder saat ini
#   GH_REPO=owner/erp-demo ./scripts/siapkan-label.sh
set -euo pipefail
gh label create bug-dari-qa --force --color D93F0B \
  --description "Bug yang dilaporkan agent QA, menunggu dibaca developer"
gh label create siap-dikerjakan --force --color 0E8A16 \
  --description "Disetujui developer: agent perbaikan boleh mulai bekerja"
# dipakai agent tiket support di Demo B (aset/hari-1/n8n-tiket-support)
gh label create dari-tiket-support --force --color 1D76DB \
  --description "Dibuat agent tiket support (n8n) dari tiket klien"
gh label list --search "bug-dari-qa siap-dikerjakan dari-tiket-support" 2>/dev/null || gh label list
