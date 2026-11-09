#!/usr/bin/env bash
# Mengunggah screenshot bukti QA ke branch qa/bukti lewat GitHub API, tanpa mengubah working tree.
# `gh issue create` tidak bisa melampirkan gambar, jadi issue menautkan gambar dari branch ini.
#
#   ./scripts/unggah-bukti.sh qa-hasil/skenario-2.png
#   → mencetak baris Markdown gambar untuk ditempel di isi issue
set -euo pipefail

file="${1:-}"
if [ -z "$file" ] || [ ! -f "$file" ]; then
  echo "Pakai: $0 <file-gambar>" >&2
  exit 2
fi
case "$file" in
  *.png|*.jpg|*.jpeg|*.webp) ;;
  *) echo "Hanya gambar (.png, .jpg, .jpeg, .webp)." >&2; exit 2 ;;
esac
if [ "$(wc -c < "$file")" -gt 5000000 ]; then
  echo "Gambar lebih dari 5 MB. Ambil screenshot ulang tanpa fullPage." >&2
  exit 2
fi

repo="${GH_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
cabang="qa/bukti"

# Buat branch qa/bukti dari branch default bila belum ada.
if ! gh api "repos/$repo/git/ref/heads/$cabang" >/dev/null 2>&1; then
  utama="$(gh api "repos/$repo" -q .default_branch)"
  sha="$(gh api "repos/$repo/git/ref/heads/$utama" -q .object.sha)"
  gh api -X POST "repos/$repo/git/refs" -f ref="refs/heads/$cabang" -f sha="$sha" >/dev/null
fi

nama="$(date +%Y%m%d-%H%M%S)-$(basename "$file")"
jalur="qa-bukti/$nama"
sementara="$(mktemp)"
trap 'rm -f "$sementara"' EXIT
base64 < "$file" | tr -d '\n' | jq -Rs --arg pesan "Bukti QA: $nama" --arg cabang "$cabang" \
  '{message: $pesan, branch: $cabang, content: .}' > "$sementara"
gh api -X PUT "repos/$repo/contents/$jalur" --input "$sementara" >/dev/null

echo "![${nama}](https://github.com/$repo/blob/$cabang/$jalur?raw=true)"
