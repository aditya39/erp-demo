#!/usr/bin/env bash
# Cadangan Demo A: menjalankan agent perbaikan di laptop (bukan routine cloud), untuk issue
# berlabel siap-dikerjakan. Prompt sama dengan routine: scripts/prompt-perbaikan-bug.txt.
#   ./scripts/perbaikan-lokal.sh            # issue terbuka terbaru berlabel siap-dikerjakan
#   ./scripts/perbaikan-lokal.sh 12         # issue tertentu
set -euo pipefail
cd "$(dirname "$0")/.."

nomor="${1:-$(gh issue list --label siap-dikerjakan --state open --limit 1 --json number -q '.[0].number')}"
if [ -z "$nomor" ]; then
  echo "Tidak ada issue terbuka berlabel siap-dikerjakan." >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree belum bersih. Commit atau stash dulu." >&2
  exit 1
fi
git switch -q main && git pull -q --ff-only

# Agent bekerja di branch claude/perbaikan-issue-<nomor>. Setelah selesai (atau gagal), kembali ke
# main supaya ERP yang dibangun ulang dari folder ini tetap berbug (cek: ./scripts/cek-bug.sh).
kembali_ke_main() {
  [ "$(git branch --show-current)" = main ] && return 0
  # Perubahan yang belum di-commit (mis. perbaikan logika.py) akan ikut pindah ke main. Jangan pindah.
  if [ -n "$(git status --porcelain)" ]; then
    echo "PERHATIAN: masih di branch $(git branch --show-current) dengan perubahan yang belum di-commit." >&2
    echo "  Cek git status, buang atau simpan perubahannya, lalu git switch main dan ./scripts/cek-bug.sh" >&2
    return 0
  fi
  if git switch -q main 2>/dev/null; then
    echo "Kembali ke branch main."
  else
    echo "PERHATIAN: belum bisa kembali ke main (ada perubahan yang belum di-commit?). Cek git status." >&2
  fi
}
trap kembali_ke_main EXIT

# Lingkungan test lokal (sekali saja).
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
fi
export PATH="$PWD/.venv/bin:$PATH"

payload="$(gh issue view "$nomor" --json number,title,body,url \
  -q '"Issue #\(.number): \(.title)\nURL: \(.url)\n\n--- Isi issue ---\n\(.body)"')"
prompt="$(cat scripts/prompt-perbaikan-bug.txt)

<routine-fire-payload>
Repo: $(gh repo view --json nameWithOwner -q .nameWithOwner)
$payload
</routine-fire-payload>"

mkdir -p qa-hasil
log="qa-hasil/log-perbaikan-$nomor-$(date +%Y%m%d-%H%M%S).jsonl"
echo "Agent perbaikan mulai untuk issue #$nomor. Log lengkap: $log"
claude -p "$prompt" \
  --model "${PERBAIKAN_MODEL:-sonnet}" \
  --permission-mode acceptEdits \
  --allowedTools "Bash(pip install:*)" "Bash(python -m pytest:*)" "Bash(python3 -m pytest:*)" \
    "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git blame:*)" "Bash(git show:*)" \
    "Bash(git switch:*)" "Bash(git checkout -b:*)" "Bash(git add:*)" "Bash(git commit:*)" \
    "Bash(git push -u origin claude/*)" "Bash(git push origin claude/*)" \
    "Bash(gh issue view:*)" "Bash(gh pr create:*)" \
  --output-format stream-json --verbose \
  | tee "$log" \
  | jq -r --unbuffered -f scripts/tampilkan-langkah.jq
echo
gh pr list --head "claude/perbaikan-issue-$nomor" --json url,isDraft -q '.[] | "PR: \(.url) (draft: \(.isDraft))"' || true
