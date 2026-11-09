#!/usr/bin/env bash
# Memastikan bug Demo A masih tertanam di tiga tempat: checkout lokal, main di GitHub, dan container
# ERP yang sedang jalan. Bug bisa hilang tanpa terasa setelah gladi, misalnya karena checkout masih
# di branch claude/..., PR perbaikan sempat di-merge, atau image dibangun dari branch lain.
#   ./scripts/cek-bug.sh
# Hasil yang benar: semua baris OK. Pola 'if d > BATAS_DISKON_MAKS' muncul 2 kali di logika.py:
# satu validasi diskon maksimum yang memang ada, satu lagi bug yang ditanam rakit.sh.
# Hanya membaca (git fetch, grep, docker compose exec). Tidak mengubah apa pun.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

LOGIKA=erp-nusantara-rasa/server/logika.py
POLA='if d > BATAS_DISKON_MAKS'
HARUS=2
gagal=0
ok()    { echo "OK     $*"; }
salah() { echo "GAGAL  $*"; gagal=1; }
lewat() { echo "LEWAT  $*"; }

cabang="$(git branch --show-current 2>/dev/null || true)"
if [ "$cabang" = main ]; then
  ok "branch lokal: main"
else
  salah "branch lokal: ${cabang:-(tidak di branch mana pun)}, harusnya main → git switch main"
fi

n="$(grep -c -F "$POLA" "$LOGIKA" 2>/dev/null || true)"
if [ "$n" = "$HARUS" ]; then ok "lokal $LOGIKA: $n"; else salah "lokal $LOGIKA: ${n:-file tidak ada}, harusnya $HARUS"; fi

if git remote get-url origin >/dev/null 2>&1 && git fetch -q origin main 2>/dev/null; then
  n="$(git show "origin/main:$LOGIKA" 2>/dev/null | grep -c -F "$POLA" || true)"
  if [ "$n" = "$HARUS" ]; then
    ok "GitHub origin/main: $n"
  else
    salah "GitHub origin/main: $n, harusnya $HARUS (PR perbaikan ter-merge saat gladi?)"
  fi
else
  lewat "GitHub origin/main: belum ada remote origin, atau git fetch gagal (offline?)"
fi

if docker compose ps --status running --services 2>/dev/null | grep -qx erp; then
  n="$(docker compose exec -T erp grep -c -F "$POLA" "/app/$LOGIKA" 2>/dev/null || true)"
  if [ "$n" = "$HARUS" ]; then
    ok "container erp (/app/$LOGIKA): $n"
  else
    salah "container erp (/app/$LOGIKA): ${n:-tidak terbaca}, harusnya $HARUS"
  fi
else
  salah "container erp tidak jalan → docker compose up -d --build"
fi

echo
if [ "$gagal" = 0 ]; then
  echo "Bug Demo A tertanam di semua tempat."
  exit 0
fi
cat <<'EOF'
Bug Demo A TIDAK lengkap. Perbaiki sebelum demo:
  - branch lokal salah   : git switch main && git pull --ff-only, lalu docker compose up -d --build
  - lokal 1, GitHub 2    : ada perubahan lokal di logika.py. Cek git status dan git log
  - GitHub 1             : PR perbaikan sudah di-merge. Revert merge itu lewat PR baru (main dilindungi),
                           atau rakit ulang repo dengan rakit.sh
  - container berbeda    : docker compose up -d --build dari branch main
EOF
exit 1
