#!/usr/bin/env bash
# Membersihkan sisa gladi Demo A dan Demo B di GitHub:
#   - issue bug-dari-qa (agent QA, Demo A)
#   - issue dari-tiket-support (agent tiket support n8n, Demo B), KECUALI issue contoh
#     "Export CSV faktur…" dari seed-issue-lama.sh yang dirujuk tiket 2
#   - pull request terbuka dari branch claude/, branch claude/* dan qa/bukti
# Issue dihapus, bukan ditutup. Agent tiket support juga membaca issue yang sudah ditutup dan
# menganggapnya "bug lama", jadi issue gladi yang hanya ditutup akan mengubah jalannya Demo B.
# Menampilkan dulu apa yang akan dihapus, lalu minta konfirmasi.
#   ./scripts/reset-demo.sh            # tampilkan, lalu minta ketik HAPUS
#   ./scripts/reset-demo.sh --lihat    # hanya tampilkan, tidak mengubah apa pun
# Menghapus issue butuh hak admin di repo. Halaman Notion Bugs tidak ikut terhapus (lihat pesan akhir).
set -euo pipefail
cd "$(dirname "$0")/.."

lihat=0
case "${1:-}" in
  "") ;;
  --lihat|--dry-run) lihat=1 ;;
  *) echo "Pakai: $0 [--lihat]" >&2; exit 2 ;;
esac

# Penanda di isi issue contoh dari aset/hari-1/n8n-tiket-support/scripts/seed-issue-lama.sh.
# Issue buatan agent tidak punya penanda ini, termasuk kalau judulnya mirip.
PENANDA_CONTOH='_Issue contoh untuk demo workshop._'

repo="${GH_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "Repo: $repo"
echo

issue="$(gh issue list -R "$repo" --label bug-dari-qa --state all --limit 200 --json number,state,title \
  -q '.[] | "\(.number)\t\(.state)\t\(.title)"')"
dari_tiket="$(gh issue list -R "$repo" --label dari-tiket-support --state all --limit 200 \
  --json number,state,title,body)"
tiket="$(jq -r --arg p "$PENANDA_CONTOH" \
  '.[] | select((.body // "") | contains($p) | not) | "\(.number)\t\(.state)\t\(.title)"' <<< "$dari_tiket")"
contoh="$(jq -r --arg p "$PENANDA_CONTOH" \
  '.[] | select((.body // "") | contains($p)) | "\(.number)\t\(.state)\t\(.title)"' <<< "$dari_tiket")"
pr="$(gh pr list -R "$repo" --state open --limit 100 --json number,title,headRefName \
  -q '.[] | select(.headRefName | startswith("claude/")) | "\(.number)\t\(.headRefName)\t\(.title)"')"
cabang="$(gh api --paginate "repos/$repo/git/matching-refs/heads/claude/" -q '.[].ref' | sed 's#^refs/heads/##')"
if gh api "repos/$repo/git/ref/heads/qa/bukti" >/dev/null 2>&1; then
  cabang="$(printf '%s\nqa/bukti' "$cabang" | sed '/^$/d')"
fi

echo "Issue berlabel bug-dari-qa, terbuka maupun tertutup (akan DIHAPUS):"
echo "${issue:-  (tidak ada)}"
echo
echo "Issue berlabel dari-tiket-support dari gladi Demo B, terbuka maupun tertutup (akan DIHAPUS):"
echo "${tiket:-  (tidak ada)}"
echo
echo "Issue contoh dari seed-issue-lama.sh (TETAP, dirujuk tiket 2):"
if [ -n "$contoh" ]; then
  echo "$contoh"
else
  echo "  PERHATIAN: tidak ditemukan. Jalankan lagi aset/hari-1/n8n-tiket-support/scripts/seed-issue-lama.sh"
fi
echo
echo "Pull request terbuka dari branch claude/ (akan DITUTUP):"
echo "${pr:-  (tidak ada)}"
echo
echo "Branch (akan DIHAPUS):"
echo "${cabang:-  (tidak ada)}"
echo

langkah_lanjut() {
  echo "Langkah berikutnya (tidak dikerjakan skrip ini):"
  echo "  1. Reset data ERP: docker compose down -v && docker compose up -d --build"
  echo "  2. Pastikan bug Demo A masih tertanam: ./scripts/cek-bug.sh"
  echo "  3. Notion, database Bugs: hapus halaman Proyek erp-demo dari tiket gladi (dibuat workflow 01"
  echo "     untuk tiket bug baru), lalu kosongkan Trash. Hapus juga pesannya di #agent-bugs kalau ada."
}

if [ "$lihat" = 1 ]; then
  echo "Mode --lihat: tidak ada yang diubah."
  echo
  langkah_lanjut
  exit 0
fi
if [ -z "$issue$tiket$pr$cabang" ]; then
  echo "Tidak ada yang perlu dibersihkan di GitHub."
  echo
  langkah_lanjut
  exit 0
fi

read -r -p "Ketik HAPUS untuk melanjutkan: " jawab
[ "$jawab" = "HAPUS" ] || { echo "Dibatalkan."; exit 1; }

while IFS=$'\t' read -r nomor _; do
  [ -n "$nomor" ] && gh pr close "$nomor" -R "$repo" --comment "Ditutup: reset setelah gladi."
done <<< "$pr"
# Issue yang punya kedua label cukup dihapus sekali.
printf '%s\n%s\n' "$issue" "$tiket" | cut -f1 | sed '/^$/d' | sort -un |
  while read -r nomor; do
    gh issue delete "$nomor" -R "$repo" --yes
  done
while read -r b; do
  [ -n "$b" ] && gh api -X DELETE "repos/$repo/git/refs/heads/$b" && echo "Branch $b dihapus"
done <<< "$cabang"

# Hasil QA lokal (issue dry-run, screenshot, log, snapshot Playwright).
find qa-hasil -mindepth 1 ! -name .gitkeep -exec rm -rf {} + 2>/dev/null || true
echo
echo "Selesai di GitHub."
langkah_lanjut
