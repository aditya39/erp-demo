#!/usr/bin/env bash
# Menyiapkan laptop mentor (macOS, Apple Silicon) sebagai SERVER BERSAMA untuk praktik Hari 2:
#   PostgreSQL :5433 dan ERP :8080 (Docker), Ollama native :11434 (memakai GPU).
# Peserta cukup Python + kit ini, lalu menempel blok .env yang dicetak di akhir.
#
#   scripts/server_bersama.sh                     # cek, jalankan, siapkan role peserta, cetak blok .env
#   scripts/server_bersama.sh --dry-run           # hanya cek; perintah yang mengubah sesuatu ditampilkan saja
#   scripts/server_bersama.sh --ip 192.168.1.20   # bila IP Wi-Fi tidak terdeteksi dengan benar
#   scripts/server_bersama.sh --build             # build ulang image ERP (setelah kode ERP berubah)
#   scripts/server_bersama.sh --ollama-docker     # terima Ollama di Docker (CPU saja; hanya untuk uji)
#
# Aman dijalankan berulang. Tanpa sudo dan tidak menghapus data. Pengaturan Ollama, firewall, dan
# container lain hanya DITAMPILKAN sebagai perintah untuk dijalankan sendiri.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERP="$(cd "$KIT/../../erp-nusantara-rasa" 2>/dev/null && pwd || true)"
ERP_ENV="$ERP/.env"
KIT_ENV="$KIT/.env"
DB=erp-ai-db
OLLAMA=http://127.0.0.1:11434
MODEL_CHAT=qwen3:8b
MODEL_EMBED=bge-m3
KONTEKS_MINIMAL=8192

DRY=0
IP=""
BUILD=""
OLLAMA_DOCKER=0
masalah=0

ok()    { printf ' ✓ %s\n' "$*"; }
info()  { printf ' • %s\n' "$*"; }
gagal() { printf ' ✗ %s\n' "$*"; masalah=$((masalah + 1)); }
saran() { printf '     → %s\n' "$*"; }
lanjut() { printf '   %s\n' "$*"; }
baris() { printf '         %s\n' "$*"; }
judul() { printf '\n== %s\n' "$*"; }

# Perintah yang mengubah sesuatu: dengan --dry-run hanya ditampilkan.
jalankan() {
  if [ "$DRY" = 1 ]; then printf '     [dry-run] %s\n' "$*"; else "$@"; fi
}
di_erp() {
  if [ "$DRY" = 1 ]; then printf '     [dry-run] (cd %s && %s)\n' "$ERP" "$*"; else (cd "$ERP" && "$@"); fi
}

# nilai_env FILE KUNCI -> nilai baris KUNCI=... terakhir (tanpa tanda kutip); kosong bila tidak ada.
nilai_env() {
  [ -f "$1" ] || return 0
  { grep -E "^[[:space:]]*$2=" "$1" || true; } | tail -n 1 | sed -E "s/^[[:space:]]*$2=//; s/^[\"']//; s/[\"']$//"
}

# atur_env FILE KUNCI NILAI -> ganti baris KUNCI=... atau tambahkan di akhir; baris lain tidak diubah.
atur_env() {
  local file=$1 kunci=$2 nilai=$3 tmp
  if [ -f "$file" ] && grep -qE "^[[:space:]]*$kunci=" "$file"; then
    tmp="$(mktemp)"
    awk -v k="$kunci" -v v="$nilai" '$0 ~ ("^[[:space:]]*" k "=") { print k "=" v; next } { print }' "$file" > "$tmp"
    cat "$tmp" > "$file"
    rm -f "$tmp"
  else
    if [ -s "$file" ] && [ -n "$(tail -c 1 "$file")" ]; then printf '\n' >> "$file"; fi
    printf '%s=%s\n' "$kunci" "$nilai" >> "$file"
  fi
  chmod 600 "$file"
}

# 32 karakter heksadesimal: kuat dan aman dipakai di URL koneksi PostgreSQL.
acak() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 16; else od -An -tx1 -N16 /dev/urandom | tr -d ' \n'; fi
}

psql_db() {
  # Socket lokal di dalam container tidak memerlukan password.
  docker exec -i -e PGOPTIONS=--client-min-messages=warning "$DB" psql -U erp_admin -d erp -v ON_ERROR_STOP=1 -q
}

db_sehat() { [ "$(docker inspect -f '{{.State.Health.Status}}' "$DB" 2>/dev/null || true)" = healthy ]; }

tunggu() {   # tunggu DETIK PERINTAH...
  local batas=$1; shift
  local i=0
  while [ "$i" -lt "$batas" ]; do
    if "$@"; then return 0; fi
    sleep 2
    i=$((i + 2))
  done
  return 1
}

erp_container() { docker ps -q --filter name='^erp-nusantara-rasa$' --filter status=running | grep -q .; }
erp_http() { [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8080/api/auth/akun-demo || true)" = 200 ]; }
# Siap = container ERP workshop berjalan DAN port 8080 menjawab (bukan aplikasi lain yang kebetulan memakai 8080).
erp_siap() { erp_container && erp_http; }

# konteks_model JSON_API_PS -> context_length milik $MODEL_CHAT di /api/ps (kosong bila tidak dimuat/tidak dilaporkan).
# Model embedding juga ada di /api/ps, jadi nilainya dipilih per nama model, bukan baris pertama.
konteks_model() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$1" | python3 -c '
import json, sys
m = sys.argv[1]
try:
    data = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for x in data.get("models") or []:
    if {x.get("name"), x.get("model")} & {m, m + ":latest"}:
        n = x.get("context_length")
        print(n if isinstance(n, int) else "")
        break
' "$MODEL_CHAT" 2>/dev/null || true
  else
    printf '%s' "$1" | grep -oE '"context_length":[0-9]+' | head -n 1 | cut -d: -f2 || true
  fi
}

ram_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 17179869184) / 1073741824 ))
if [ "$ram_gb" -ge 24 ]; then PARALEL=4; else PARALEL=2; fi

cetak_env_ollama() {
  saran "Atur sekali (berlaku sampai Mac di-restart), lalu keluar dari Ollama (ikon menu bar › Quit Ollama) dan buka lagi:"
  baris "launchctl setenv OLLAMA_HOST 0.0.0.0:11434"
  baris "launchctl setenv OLLAMA_CONTEXT_LENGTH 8192"
  baris "launchctl setenv OLLAMA_NUM_PARALLEL $PARALEL      # $PARALEL permintaan sekaligus (RAM ${ram_gb} GB)"
  baris "launchctl setenv OLLAMA_KEEP_ALIVE 2h              # model tetap dimuat selama sesi"
  baris "open -a Ollama"
  saran "Atau tanpa aplikasi, di terminal terpisah (tutup aplikasi Ollama dulu):"
  baris "OLLAMA_HOST=0.0.0.0:11434 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=$PARALEL OLLAMA_KEEP_ALIVE=2h ollama serve"
}

# Bisa di-source untuk menguji fungsi di atas tanpa menjalankan langkah apa pun.
if [ "${BASH_SOURCE[0]}" != "$0" ]; then return 0; fi

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --ip) IP="${2:?--ip memerlukan alamat, mis. --ip 192.168.1.20}"; shift ;;
    --build) BUILD=1 ;;
    --ollama-docker) OLLAMA_DOCKER=1 ;;
    -h|--help) sed -n '2,13p' "$0" | sed -E 's/^# ?//'; exit 0 ;;
    *) echo "Opsi tidak dikenal: $1 (lihat --help)"; exit 2 ;;
  esac
  shift
done

printf 'Server bersama — Asisten AI ERP, praktik Hari 2%s\n' "$([ "$DRY" = 1 ] && echo '   [DRY-RUN: tidak ada yang diubah]')"

# ---------------------------------------------------------------------------
judul "1. Docker"
[ "$(uname -s)" = Darwin ] || info "Bukan macOS: langkah Ollama dan firewall ditulis untuk Mac, sesuaikan perintahnya."
if [ -z "$ERP" ] || [ ! -f "$ERP/docker-compose.yml" ]; then
  gagal "Folder ERP tidak ditemukan (diharapkan di $KIT/../../erp-nusantara-rasa)"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  gagal "Docker belum berjalan"
  saran "Buka Docker Desktop, tunggu sampai statusnya 'Engine running', lalu jalankan ulang skrip ini"
  exit 1
fi
ok "Docker berjalan"

proyek_h1="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep -E '^h1-' | sort -u || true)"
for p in $proyek_h1; do
  gagal "Demo Hari 1 masih berjalan: proyek $p ($(docker ps --filter "label=com.docker.compose.project=$p" --format '{{.Names}} {{.Ports}}' | tr '\n' ' '))"
  saran "ERP demo Hari 1 sengaja berisi bug diskon; hentikan agar peserta tidak membuka ERP yang salah (data tetap ada):"
  baris "docker stop \$(docker ps -q --filter label=com.docker.compose.project=$p)"
  saran "Menyalakan lagi nanti: docker start \$(docker ps -aq --filter label=com.docker.compose.project=$p)"
done
[ -n "$proyek_h1" ] || ok "Tidak ada container demo Hari 1 (h1-*) yang berjalan"

# Container lain (proyek di luar workshop) ikut memakai RAM yang dibutuhkan Ollama.
lain="$(docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}}' \
  | awk '$1 != "erp-ai-db" && $1 != "erp-nusantara-rasa" && $1 != "erp-ai-ollama" && $2 !~ /^h1-/ { print $1 }' | tr '\n' ' ' || true)"
if [ -n "${lain// /}" ]; then
  info "Container di luar workshop masih berjalan: ${lain% }"
  saran "Hentikan selama hari workshop agar RAM cukup untuk Ollama (data tetap ada): docker stop ${lain% }"
fi
mem_docker=$(( $(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0) / 1073741824 ))
if [ "$mem_docker" -gt 9 ]; then
  info "Docker Desktop boleh memakai memori sampai ±${mem_docker} GB. Rencana server: ±8 GB, sisanya untuk Ollama."
  saran "Docker Desktop › Settings › Resources › Memory limit 8 GB › Apply & restart, lalu cek: docker info --format '{{.MemTotal}}'"
fi

# ---------------------------------------------------------------------------
judul "2. Ollama (model AI)"
MODE_OLLAMA=""
pendengar=""
if command -v lsof >/dev/null 2>&1; then
  pendengar="$(lsof -nP -iTCP:11434 -sTCP:LISTEN 2>/dev/null | awk 'NR > 1 { print $1, $9 }' | head -n 1 || true)"
fi
ollama_docker="$(docker ps -q --filter name='^erp-ai-ollama$')"
punya_native=0
if command -v ollama >/dev/null 2>&1 || [ -d /Applications/Ollama.app ]; then punya_native=1; fi

if [ -n "$ollama_docker" ]; then
  MODE_OLLAMA=docker
  info "Ollama berjalan di Docker (container erp-ai-ollama): CPU saja, satu jawaban 30 dtk–2 mnt."
  if [ "$OLLAMA_DOCKER" = 1 ]; then
    info "Diterima karena --ollama-docker (hanya untuk uji, tidak untuk kelas)."
  else
    gagal "Untuk kelas, gunakan Ollama native (GPU) di Mac ini"
  fi
  if [ "$punya_native" = 1 ]; then
    saran "Ollama native sudah terpasang. Hentikan container (docker stop erp-ai-ollama), beri tanda # pada baris"
    saran "COMPOSE_PROFILES dan OLLAMA_URL di $ERP_ENV, jalankan Ollama native (perintah di bawah), lalu ulangi skrip ini."
    cetak_env_ollama
  else
    saran "Instal Ollama native: https://ollama.com/download (atau: brew install --cask ollama), lalu ulangi skrip ini."
  fi
elif [ "${pendengar%% *}" = ollama ] || [ "${pendengar%% *}" = Ollama ]; then
  MODE_OLLAMA=native
  alamat="${pendengar#* }"
  case "$alamat" in
    \*:11434|0.0.0.0:11434|\[::\]:11434) ok "Ollama native menerima koneksi jaringan ($alamat)" ;;
    *) gagal "Ollama native hanya menerima koneksi dari laptop ini ($alamat)"; cetak_env_ollama ;;
  esac
  beda=0
  for pasangan in OLLAMA_HOST=0.0.0.0:11434 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=$PARALEL OLLAMA_KEEP_ALIVE=2h; do
    kunci=${pasangan%%=*}; saranan=${pasangan#*=}
    sekarang="$(launchctl getenv "$kunci" 2>/dev/null || true)"
    if [ "$sekarang" != "$saranan" ]; then
      info "$kunci untuk aplikasi Ollama: '${sekarang:-belum diatur}' (disarankan $saranan)"
      beda=1
    fi
  done
  if [ "$beda" = 1 ]; then
    info "Abaikan bila Ollama dijalankan dengan 'ollama serve' beserta variabel di atas."
    cetak_env_ollama
  fi
elif [ "$punya_native" = 1 ]; then
  gagal "Ollama terpasang tetapi belum berjalan"
  cetak_env_ollama
else
  gagal "Ollama native belum terpasang dan tidak ada yang melayani port 11434"
  saran "Instal: https://ollama.com/download (atau: brew install --cask ollama), lalu ulangi skrip ini."
fi

if [ -n "$MODE_OLLAMA" ]; then
  tags="$(curl -s --max-time 5 "$OLLAMA/api/tags" || true)"
  pull="ollama pull"
  if [ "$MODE_OLLAMA" = docker ]; then pull="docker exec erp-ai-ollama ollama pull"; fi
  model_lengkap=1
  for m in "$MODEL_CHAT" "$MODEL_EMBED"; do
    if printf '%s' "$tags" | grep -qE "\"name\":\"$m(:latest)?\""; then
      ok "Model $m tersedia"
    else
      gagal "Model $m belum diunduh"; saran "$pull $m"; model_lengkap=0
    fi
  done
  if [ "$MODE_OLLAMA" = native ] && [ "$model_lengkap" = 1 ]; then
    info "Memanaskan model agar jawaban pertama peserta tidak lambat…"
    jalankan curl -s -o /dev/null --max-time 180 "$OLLAMA/api/generate" -d "{\"model\":\"$MODEL_CHAT\",\"keep_alive\":\"2h\"}"
    jalankan curl -s -o /dev/null --max-time 60 "$OLLAMA/api/embed" -d "{\"model\":\"$MODEL_EMBED\",\"input\":\"uji\",\"keep_alive\":\"2h\"}"
  fi
  # Konteks dicek SETELAH pemanasan: /api/ps hanya melaporkan model yang sedang dimuat. Setelah Mac restart,
  # nilai launchctl hilang dan Ollama kembali ke konteks bawaan yang terlalu pendek, tanpa pesan error.
  konteks="$(konteks_model "$(curl -s --max-time 5 "$OLLAMA/api/ps" || true)")"
  konteks_lc="$(launchctl getenv OLLAMA_CONTEXT_LENGTH 2>/dev/null || true)"
  if [ -n "$konteks" ]; then
    if [ "$konteks" -ge "$KONTEKS_MINIMAL" ]; then
      ok "Konteks $MODEL_CHAT yang sedang dimuat: $konteks token"
    else
      gagal "Konteks $MODEL_CHAT yang sedang dimuat hanya $konteks token (minimal $KONTEKS_MINIMAL): prompt agent dan RAG terpotong tanpa pesan error"
      cetak_env_ollama
    fi
  elif [ "$MODE_OLLAMA" = native ] && [ "$konteks_lc" != "$KONTEKS_MINIMAL" ]; then
    gagal "Konteks $MODEL_CHAT belum terbaca dan OLLAMA_CONTEXT_LENGTH untuk aplikasi Ollama '${konteks_lc:-belum diatur}' (harus $KONTEKS_MINIMAL)"
    cetak_env_ollama
  else
    info "Konteks $MODEL_CHAT belum bisa dicek: model belum dimuat$([ "$DRY" = 1 ] && echo ' (tanpa --dry-run skrip memanaskan model dulu)')."
  fi
fi

# ---------------------------------------------------------------------------
judul "3. Password admin database & aplikasi ERP"
info "Password bawaan (admin_workshop, aplikasi_erp) tertulis di kit; di jaringan kelas keduanya diganti acak."
PW_ADMIN=""; PW_APP=""; PW_BARU=0; PW_TERPASANG=0
for pasangan in DB_ADMIN_PASSWORD:admin_workshop ERP_APP_PASSWORD:aplikasi_erp; do
  kunci=${pasangan%%:*}; bawaan=${pasangan#*:}
  nilai="$(nilai_env "$ERP_ENV" "$kunci")"
  if [ -z "$nilai" ]; then
    nilai="$(acak)"; PW_BARU=1
    if [ "$DRY" = 1 ]; then
      printf '     [dry-run] tulis %s=<acak 32 karakter> ke %s\n' "$kunci" "$ERP_ENV"
    else
      atur_env "$ERP_ENV" "$kunci" "$nilai"
      ok "$kunci dibuat acak dan disimpan di $ERP_ENV"
    fi
  elif [ "$nilai" = "$bawaan" ]; then
    gagal "$kunci di $ERP_ENV masih password bawaan kit (diketahui peserta)"
    saran "Hapus baris $kunci dari $ERP_ENV lalu ulangi skrip ini agar dibuat acak"
  elif ! printf '%s' "$nilai" | grep -qE '^[A-Za-z0-9._~-]+$'; then
    gagal "$kunci di $ERP_ENV memakai karakter yang tidak aman untuk URL koneksi"
    saran "Gunakan huruf, angka, atau . _ ~ - saja (atau hapus barisnya agar dibuat acak)"
    nilai=""
  else
    ok "$kunci sudah diatur di $ERP_ENV (tidak ditampilkan)"
  fi
  if [ "$kunci" = DB_ADMIN_PASSWORD ]; then PW_ADMIN=$nilai; else PW_APP=$nilai; fi
done

# ---------------------------------------------------------------------------
judul "4. Database & role peserta"
if ! db_sehat; then
  di_erp docker compose up -d db
  if [ "$DRY" = 0 ] && ! tunggu 120 db_sehat; then
    gagal "Database $DB belum sehat setelah 2 menit"; saran "Lihat log: (cd $ERP && docker compose logs db)"
  fi
fi
if db_sehat; then
  ok "Database $DB berjalan di port 5433"
  if [ -n "$PW_ADMIN" ] && [ -n "$PW_APP" ]; then
    if [ "$DRY" = 1 ]; then
      printf "     [dry-run] docker exec -i %s psql … <<< ALTER ROLE erp_admin PASSWORD '***'; ALTER ROLE erp_app PASSWORD '***' (bila role ada)\n" "$DB"
      PW_TERPASANG=1
    else
      psql_db <<SQL
ALTER ROLE erp_admin PASSWORD '$PW_ADMIN';
DO \$\$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_app') THEN ALTER ROLE erp_app PASSWORD '$PW_APP'; END IF;
END \$\$;
SQL
      ok "Password role erp_admin & erp_app di database disamakan dengan $ERP_ENV"
      PW_TERPASANG=1
    fi
  fi
  if [ "$DRY" = 1 ]; then
    printf '     [dry-run] docker exec -i %s psql -U erp_admin -d erp < %s\n' "$DB" "db/init/04_latihan.sql"
    status="$(docker exec "$DB" psql -U erp_admin -d erp -tAc "SELECT CASE WHEN to_regnamespace('latihan') IS NULL THEN 'belum ada' WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_peserta') THEN 'sudah ada' ELSE 'belum lengkap' END" 2>/dev/null || true)"
    info "Schema latihan & role erp_peserta saat ini: ${status:-tidak diketahui}"
  else
    psql_db < "$KIT/db/init/04_latihan.sql"
    ok "Schema latihan & role erp_peserta siap (Sesi 2.4: koleksi RAG milik peserta)"
  fi
  n_latihan="$(docker exec "$DB" psql -U erp_admin -d erp -tAc "SELECT count(*) FROM pg_tables WHERE schemaname = 'latihan'" 2>/dev/null || echo 0)"
  [ "${n_latihan:-0}" = 0 ] || info "Koleksi peserta yang sudah ada: $n_latihan tabel di schema latihan (tidak diubah)"
elif [ "$DRY" = 1 ]; then
  info "Database belum berjalan; dengan --dry-run langkah database dilewati."
fi

# ---------------------------------------------------------------------------
judul "5. Aplikasi ERP & indeks dokumen"
profil_erp="$(nilai_env "$ERP_ENV" COMPOSE_PROFILES)"
erp_dijalankan=0
if [ "$MODE_OLLAMA" = native ] && printf '%s' "$profil_erp" | grep -q ollama; then
  gagal "$ERP_ENV masih memakai Ollama Docker (COMPOSE_PROFILES=$profil_erp), bentrok dengan Ollama native di port 11434"
  saran "Beri tanda # pada baris COMPOSE_PROFILES dan OLLAMA_URL di $ERP_ENV, lalu ulangi skrip ini"
else
  # Port database & ERP default hanya 127.0.0.1 (docker-compose). Dibuka ke jaringan HANYA setelah password diganti.
  if [ "$PW_TERPASANG" = 1 ]; then
    kunci_bind="DB_BIND ERP_BIND"
    if [ "$MODE_OLLAMA" = docker ]; then kunci_bind="$kunci_bind OLLAMA_BIND"; fi
    for kunci in $kunci_bind; do
      if [ "$(nilai_env "$ERP_ENV" "$kunci")" != 0.0.0.0 ]; then
        if [ "$DRY" = 1 ]; then printf '     [dry-run] tulis %s=0.0.0.0 ke %s\n' "$kunci" "$ERP_ENV"; else atur_env "$ERP_ENV" "$kunci" 0.0.0.0; fi
      fi
    done
    if [ "$DRY" = 1 ]; then info "Port akan dibuka ke jaringan kelas ($kunci_bind=0.0.0.0)"; else
      ok "Port dibuka ke jaringan kelas: $kunci_bind=0.0.0.0 di $ERP_ENV (container dibuat ulang oleh compose)"; fi
  else
    gagal "Port database dan ERP tetap hanya untuk laptop ini (127.0.0.1): password admin belum diganti"
    saran "Bereskan langkah 3 dan 4 lalu ulangi skrip ini; peserta belum bisa terhubung"
  fi
  if [ -n "$BUILD" ]; then di_erp docker compose up -d --build; else di_erp docker compose up -d; fi
  erp_dijalankan=1
  if [ "$PW_BARU" = 1 ] && docker ps -q --filter name='^erp-nusantara-rasa$' | grep -q .; then
    di_erp docker compose restart erp   # koneksi ERP memakai password baru
  fi
fi
if [ "$DRY" = 0 ] && [ "$erp_dijalankan" = 1 ]; then
  if tunggu 180 erp_siap; then ok "ERP (container erp-nusantara-rasa) menjawab di http://127.0.0.1:8080"; else
    gagal "ERP belum menjawab setelah 3 menit"; saran "Lihat log: (cd $ERP && docker compose logs -f erp)"; fi
elif erp_siap; then
  ok "ERP (container erp-nusantara-rasa) menjawab di http://127.0.0.1:8080"
else
  info "ERP belum berjalan."
fi
if ! erp_container && erp_http; then
  gagal "Port 8080 dijawab aplikasi lain, bukan container erp-nusantara-rasa (mis. ERP tanpa Docker atau salinan lama)"
  saran "Cek pemiliknya: lsof -nP -iTCP:8080 -sTCP:LISTEN, hentikan, lalu ulangi skrip ini"
fi

# .env kit di laptop ini: blok CLOUD_* dipakai tombol Cloud ERP (Demo 3). Model lokal ERP dikunci di docker-compose.yml,
# tetapi cek_setup, evaluasi, dan uji_beban di laptop ini tetap membaca LOKAL_* dari .env kit.
kit_lokal="$(nilai_env "$KIT_ENV" LOKAL_BASE_URL)"; kit_model="$(nilai_env "$KIT_ENV" LOKAL_MODEL)"
case "$kit_lokal" in *anthropic.com*|https://*) kit_lain=1 ;; *) kit_lain=0 ;; esac
if [ -n "$kit_model" ] && [ "$kit_model" != "$MODEL_CHAT" ]; then kit_lain=1; fi
if [ "$kit_lain" = 1 ]; then
  gagal "$KIT_ENV memakai model lain untuk mode lokal (LOKAL_BASE_URL=${kit_lokal:-bawaan}, LOKAL_MODEL=${kit_model:-bawaan})"
  saran "ERP tidak terpengaruh, tetapi cek_setup, evaluasi, dan uji_beban di laptop ini tidak lagi menguji $MODEL_CHAT."
  saran "Kembalikan blok LOKAL_* ke profil (a). Profil (c) diuji dari laptop peserta, bukan dari .env server."
fi
cloud_penyedia="$(nilai_env "$KIT_ENV" CLOUD_PENYEDIA)"
if [ "$cloud_penyedia" = api ]; then
  cloud_model="$(nilai_env "$KIT_ENV" CLOUD_MODEL)"; cloud_suhu="$(nilai_env "$KIT_ENV" CLOUD_SUHU)"
  if [ -z "$(nilai_env "$KIT_ENV" CLOUD_BASE_URL)" ] || [ -z "$cloud_model" ] || [ -z "$(nilai_env "$KIT_ENV" CLOUD_API_KEY)" ]; then
    gagal "Demo 3: CLOUD_PENYEDIA=api, tetapi CLOUD_BASE_URL, CLOUD_MODEL, atau CLOUD_API_KEY di $KIT_ENV masih kosong"
  else
    ok "Demo 3: tombol Cloud ERP memakai $cloud_model lewat API (key terisi, tidak ditampilkan)"
    [ "$cloud_model" = claude-haiku-5-5 ] || info "Rencana Demo 3 memakai claude-haiku-5-5 (02-skrip-demo.md)"
  fi
  if [ -n "$cloud_suhu" ] && awk -v s="$cloud_suhu" 'BEGIN { exit !(s + 0 < 1) }'; then
    gagal "CLOUD_SUHU=$cloud_suhu di $KIT_ENV: kosongkan, model Claude menolak temperature di bawah 1"
  fi
else
  info "Demo 3: CLOUD_PENYEDIA=${cloud_penyedia:-claude-code (bawaan)}, jadi tombol Cloud di ERP Docker tidak aktif."
  saran "Isi CLOUD_PENYEDIA=api, CLOUD_BASE_URL, CLOUD_MODEL=claude-haiku-5-5, CLOUD_API_KEY di $KIT_ENV, lalu ulangi skrip ini"
fi

if db_sehat; then
  n_rag="$(docker exec "$DB" psql -U erp_admin -d erp -tAc "SELECT count(*) FROM rag.dokumen_chunk" 2>/dev/null || true)"
  ada_nomor="$(docker exec "$DB" psql -U erp_admin -d erp -tAc "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'rag' AND table_name = 'dokumen_chunk' AND column_name = 'nomor'" 2>/dev/null || echo 0)"
  if [ -z "$n_rag" ] || [ "$n_rag" = 0 ]; then
    info "Indeks dokumen bersama masih kosong: ERP mengisinya otomatis saat start (lihat: docker compose logs erp)."
  elif [ "$ada_nomor" = 0 ]; then
    info "Indeks dokumen bersama ($n_rag potongan) dibuat versi lama, tanpa nomor dokumen. Mengisi ulang…"
    jalankan docker exec -w /app/kit/asisten-erp-ai erp-nusantara-rasa python -m asisten.rag ingest
  else
    ok "Indeks dokumen bersama: $n_rag potongan (rag.dokumen_chunk, lengkap dengan nomor dokumen)"
  fi
fi

# ---------------------------------------------------------------------------
judul "6. Jaringan"
antarmuka=""
if [ -z "$IP" ]; then
  antarmuka="$(route -n get default 2>/dev/null | awk '/interface:/ { print $2 }' || true)"
  IP="$(ipconfig getifaddr "${antarmuka:-en0}" 2>/dev/null || true)"
  [ -n "$IP" ] || IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
  [ -n "$IP" ] || IP="$(hostname -I 2>/dev/null | awk '{ print $1 }' || true)"
fi
if [ -z "$IP" ]; then
  gagal "IP jaringan (LAN) tidak terdeteksi"; saran "Hubungkan ke Wi-Fi kelas, atau jalankan dengan --ip <alamat>"
  IP="IP-MENTOR"
else
  ok "IP jaringan: $IP${antarmuka:+ (antarmuka $antarmuka)}"
  for port in 5433 8080 11434; do
    if nc -z -w 2 "$IP" "$port" >/dev/null 2>&1; then ok "Port $port terbuka di $IP"; else gagal "Port $port tidak menjawab di $IP"; fi
  done
  info "Uji di atas berjalan dari laptop ini; firewall baru teruji dari laptop peserta (python scripts/cek_setup.py)."
fi
fw="$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null || true)"
blokir="$(/usr/libexec/ApplicationFirewall/socketfilterfw --getblockall 2>/dev/null || true)"
case "$blokir" in *enabled*|*ENABLED*) gagal "Firewall macOS memblokir SEMUA koneksi masuk"
  saran "System Settings › Network › Firewall › Options: matikan 'Block all incoming connections'" ;; esac
case "$fw" in *enabled*|*State\ =\ 1*|*State\ =\ 2*)
  info "Firewall macOS aktif: saat muncul dialog 'Allow incoming network connections' untuk Ollama atau Docker, pilih Allow"
  saran "Atau: System Settings › Network › Firewall › Options, izinkan Ollama dan Docker" ;; esac
info "Mentor dan semua peserta harus di Wi-Fi yang sama. Wi-Fi tamu sering mengisolasi antar-perangkat"
lanjut "(client isolation): pakai Wi-Fi kantor atau router/hotspot milik sendiri."
info "Cegah Mac tidur selama kelas: jalankan 'caffeinate -dis' di terminal terpisah dan pasang charger."

# ---------------------------------------------------------------------------
judul "7. Untuk peserta"
cat <<BLOK
Tempel di .env peserta (profil b, server bersama):

  DATABASE_URL=postgresql://erp_ai_readonly:baca_saja@$IP:5433/erp
  DATABASE_URL_PESERTA=postgresql://erp_peserta:latihan_rag@$IP:5433/erp
  LOKAL_BASE_URL=http://$IP:11434/v1
  EMBED_BASE_URL=http://$IP:11434/v1
  ERP_URL=http://$IP:8080
  RAG_KOLEKSI=

Cadangan cloud (profil c) bila server lambat: tambahkan di bawah blok di atas, dengan API key kelompok:

  LOKAL_BASE_URL=https://api.anthropic.com/v1/
  LOKAL_MODEL=claude-haiku-5-5
  LOKAL_API_KEY=<API key kelompok>
  LOKAL_REASONING_EFFORT=
  LOKAL_SUHU=

ERP di browser peserta: http://$IP:8080 (akun demo, password demo123).
BLOK
info "Peserta hanya mendapat role erp_ai_readonly (baca view ai, rag, latihan) dan erp_peserta (membuat tabel"
lanjut "di schema latihan). Password erp_admin dan erp_app ada di $ERP_ENV: jangan dibagikan."
info "Perintah admin dari laptop ini (mis. python -m asisten.rag ingest): isi DATABASE_URL_ADMIN di $KIT/.env"
lanjut "dengan password DB_ADMIN_PASSWORD dari $ERP_ENV."
info "Uji kapasitas dari laptop lain: python scripts/uji_beban.py --peserta <jumlah pasangan> --model $MODEL_CHAT --base-url http://$IP:11434/v1"

printf '\n%s\n' "$([ "$masalah" = 0 ] && echo 'Server bersama siap.' || echo "Ada $masalah hal yang perlu dibereskan (lihat tanda ✗ di atas).")"
exit $(( masalah > 0 ? 1 : 0 ))
