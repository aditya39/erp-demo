#!/usr/bin/env python3
"""
Cek kesiapan laptop untuk workshop. Jalankan dari folder utama proyek:

    python scripts/cek_setup.py

Semua baris harus ✓ sebelum workshop dimulai. Baris • hanya informasi (tidak wajib).
Baris pertama setelah paket menunjukkan mode praktik yang terbaca dari .env:
laptop sendiri, server bersama, atau cadangan cloud (lihat profil di .env.example).
"""
from __future__ import annotations

import importlib
import ipaddress
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OK, GAGAL, INFO = "✓", "✗", "•"
masalah = 0


def lapor(status: str, teks: str, saran: str = "") -> None:
    global masalah
    if status == GAGAL:
        masalah += 1
    print(f" {status} {teks}" + (f"\n     → {saran}" if saran else ""))


def lokasi(url: str) -> str:
    """'lokal' (laptop ini), 'lan' (server bersama di jaringan kelas), atau 'cloud'."""
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "host.docker.internal"):
        return "lokal"
    try:
        ip = ipaddress.ip_address(host)
        return "lan" if ip.is_private or ip.is_link_local else "cloud"
    except ValueError:
        return "lan" if host.endswith((".local", ".lan")) or "." not in host else "cloud"


def host(url: str) -> str:
    return urlparse(url).hostname or url


def anthropic(url: str) -> bool:
    return host(url).endswith("anthropic.com")


def cek_suhu(nama: str, cfg) -> None:
    """Claude 4.7 ke atas lewat endpoint kompatibel OpenAI menolak temperature di bawah 1 (error 400)."""
    suhu = getattr(cfg, "suhu", None)
    if anthropic(cfg.base_url) and suhu is not None and suhu < 1:
        # LOKAL_SUHU yang tidak diisi bisa terisi dari nama lamanya, SUHU.
        if nama == "LOKAL_SUHU" and os.getenv("LOKAL_SUHU") is None and os.getenv("SUHU") is not None:
            nama, saran = "SUHU", "Hapus baris SUHU (nama lama) dari .env, atau isi LOKAL_SUHU= (kosong)"
        else:
            saran = f"Kosongkan {nama} di .env (temperature tidak dikirim)"
        lapor(GAGAL, f"{nama}={suhu:g}: model Claude terbaru menolak temperature di bawah 1", saran)


def pesan(e: Exception) -> str:
    return str(e).splitlines()[0][:110] if str(e) else type(e).__name__


def pesan_lengkap(e: Exception) -> str:
    """Pesan error utuh dalam satu baris (error koneksi database sering lebih dari satu baris)."""
    return " ".join(str(e).split()) or type(e).__name__


KONTEKS_MINIMAL = 8192


def konteks_ollama(base_url: str, model: str) -> tuple[int | None, str]:
    """
    Panjang konteks model chat yang sedang dimuat Ollama, dibaca dari /api/ps.
    Hasil (angka, "") bila terbaca; (None, alasan) bila tidak bisa ditentukan (bukan Ollama, model belum
    dimuat, atau Ollama versi lama). Tidak pernah melempar error: cek ini hanya pelengkap.
    """
    import json
    import urllib.request

    akar = base_url.rstrip("/")
    if akar.endswith("/v1"):
        akar = akar[:-3]
    try:
        with urllib.request.urlopen(f"{akar}/api/ps", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None, "endpoint /api/ps tidak tersedia (bukan Ollama?)"
    nama = {model, f"{model}:latest"}
    for m in data.get("models") or []:
        if m.get("name") in nama or m.get("model") in nama:
            n = m.get("context_length")
            return (int(n), "") if isinstance(n, int) and n > 0 else (None, "Ollama tidak melaporkan context_length (versi lama?)")
    return None, f"model {model} tidak sedang dimuat"


print("Cek setup workshop Asisten AI ERP\n")

# 1. Python
v = sys.version_info
lapor(OK if v >= (3, 10) else GAGAL, f"Python {v.major}.{v.minor}.{v.micro}",
      "" if v >= (3, 10) else "Instal Python 3.10 atau lebih baru")

# 2. Paket
for paket in ("openai", "psycopg", "fastapi", "uvicorn", "dotenv", "mcp"):
    try:
        importlib.import_module(paket)
        lapor(OK, f"Paket {paket}")
    except ImportError:
        lapor(GAGAL, f"Paket {paket} belum terpasang", "pip install -r requirements.txt")
if masalah:
    sys.exit(1)

from openai import OpenAI  # noqa: E402

from asisten import config, db, llm, rag  # noqa: E402
from asisten import format as fmt  # noqa: E402

lapor(INFO, f"File .env {'ditemukan' if (config.ROOT / '.env').exists() else 'tidak ada (memakai nilai default)'}")

# Mode praktik, disimpulkan dari alamat di .env
model_di, db_di = lokasi(config.LOKAL.base_url), lokasi(config.DATABASE_URL)
CLOUD = model_di == "cloud"
if CLOUD:
    mode = f"cadangan cloud · model {config.LOKAL.model} di {host(config.LOKAL.base_url)}, database di {host(config.DATABASE_URL)}"
elif "lan" in (model_di, db_di):
    mode = f"server bersama · model di {host(config.LOKAL.base_url)}, database di {host(config.DATABASE_URL)}"
else:
    mode = "laptop sendiri · database Docker dan Ollama di laptop ini"
lapor(INFO, f"Mode praktik: {mode}")
if CLOUD:
    lapor(INFO, "Mode cloud: pertanyaan dan hasil query dikirim ke penyedia model (di kit ini data dummy)")

# 3. Database
dimensi_indeks = None
try:
    n = db.query("SELECT count(*) AS n FROM ai.v_penjualan")[0]["n"]
    info = db.info()
    lapor(OK, f"Database terhubung · {n:,} baris penjualan · posisi data {info['tanggal_posisi']}")
except Exception as e:  # noqa: BLE001
    lapor(GAGAL, f"Database tidak dapat dihubungi ({pesan_lengkap(e)})",
          "Jalankan 'docker compose up -d' atau periksa DATABASE_URL di .env (IP server mentor)")

try:
    baris = db.query("SELECT count(*) AS n, max(vector_dims(embedding)) AS d FROM rag.dokumen_chunk")[0]
    dimensi_indeks = baris["d"]
    lama = "" if rag.punya_metadata("rag", "dokumen_chunk") else " (versi lama tanpa nomor dokumen: ingest ulang)"
    lapor(OK, f"Dokumen RAG tersedia · {baris['n']} potongan{lama}")
except Exception:  # noqa: BLE001
    lapor(GAGAL, "Tabel dokumen RAG belum ada", "Jalankan 'python -m asisten.rag ingest' (atau minta mentor)")

# Koleksi peserta (Sesi 2.4)
peserta_url = os.getenv("DATABASE_URL_PESERTA", "").strip()
if peserta_url:
    import psycopg  # noqa: E402

    try:
        with psycopg.connect(peserta_url, connect_timeout=5) as conn:
            boleh = conn.execute("SELECT has_schema_privilege('latihan', 'CREATE')").fetchone()[0]
        lapor(OK if boleh else GAGAL, f"Koneksi peserta (DATABASE_URL_PESERTA) {'bisa' if boleh else 'TIDAK bisa'} "
              "membuat koleksi di schema latihan", "" if boleh else "Minta mentor menjalankan scripts/server_bersama.sh")
    except Exception as e:  # noqa: BLE001
        lapor(GAGAL, f"Koneksi peserta (DATABASE_URL_PESERTA) gagal ({pesan_lengkap(e)})",
              "Periksa IP dan password di DATABASE_URL_PESERTA, atau minta mentor menjalankan scripts/server_bersama.sh")
try:
    koleksi = rag.koleksi_aktif()
    if koleksi:
        if rag.koleksi_ada(koleksi):
            n = db.query(f'SELECT count(*) AS n FROM "latihan"."dokumen_{koleksi}"')[0]["n"]
            lapor(OK, f"Koleksi RAG_KOLEKSI={koleksi} · {n} potongan di latihan.dokumen_{koleksi} (ikut dicari asisten)")
        else:
            lapor(INFO, f"RAG_KOLEKSI={koleksi} diisi, tetapi koleksinya belum ada (asisten memakai indeks bersama saja)",
                  f"python -m asisten.rag ingest --koleksi {koleksi}")
except ValueError as e:
    lapor(GAGAL, str(e), "Perbaiki RAG_KOLEKSI di .env")
except Exception as e:  # noqa: BLE001
    lapor(INFO, f"Koleksi RAG_KOLEKSI tidak dapat diperiksa ({pesan(e)[:90]})")

# 4. Model chat
klien = OpenAI(base_url=config.LOKAL.base_url, api_key=config.LOKAL.api_key or "kosong", timeout=300, max_retries=0)
siap_uji = False
if CLOUD:
    kunci = config.LOKAL.api_key
    if not kunci or kunci == "ollama" or kunci.startswith("<"):
        lapor(GAGAL, "LOKAL_API_KEY belum diisi untuk mode cloud", "Isi dengan API key kelompok dari mentor")
    else:
        siap_uji = True
    cek_suhu("LOKAL_SUHU", config.LOKAL)
else:
    try:
        tersedia = {m.id for m in klien.models.list().data}
        lapor(OK, f"Model chat (Ollama) terhubung di {config.LOKAL.base_url}")
        ada = config.LOKAL.model in tersedia or f"{config.LOKAL.model}:latest" in tersedia
        lapor(OK if ada else GAGAL, f"Model {config.LOKAL.model}", "" if ada else f"ollama pull {config.LOKAL.model}")
        siap_uji = ada
    except Exception:  # noqa: BLE001
        lapor(GAGAL, f"Ollama tidak dapat dihubungi di {config.LOKAL.base_url}",
              "Pastikan aplikasi Ollama berjalan, atau isi LOKAL_BASE_URL dengan alamat server mentor")

if siap_uji:
    t0 = time.perf_counter()
    try:
        r = klien.chat.completions.create(
            model=config.LOKAL.model, messages=[{"role": "user", "content": "Jawab satu kata: ibu kota Indonesia?"}],
            **llm.opsi_tambahan(config.LOKAL))
        dt = time.perf_counter() - t0
        lapor(OK if dt < 60 else INFO, f"Uji jawab model: '{(r.choices[0].message.content or '').strip()[:30]}' "
              f"dalam {dt:.1f} dtk (termasuk memuat model)",
              "" if dt < 60 else "Lambat: pertimbangkan server mentor atau cadangan cloud")
    except Exception as e:  # noqa: BLE001
        lapor(GAGAL, f"Uji jawab model gagal: {pesan(e)}",
              "Mode cloud: periksa API key dan LOKAL_MODEL. Ollama: bila error terkait reasoning_effort, "
              "kosongkan LOKAL_REASONING_EFFORT di .env")

# Panjang konteks Ollama: default 4096 token terlalu pendek. System prompt + skema tool saja sudah ±4.800 token,
# jadi Ollama diam-diam memotong prompt (aturan, tool, atau hasil RAG hilang) tanpa pesan error.
if not CLOUD and siap_uji:
    konteks, alasan = konteks_ollama(config.LOKAL.base_url, config.LOKAL.model)
    if konteks is None:
        lapor(INFO, f"Panjang konteks model tidak dapat diperiksa ({alasan})",
              f"Bila memakai Ollama, pastikan OLLAMA_CONTEXT_LENGTH minimal {KONTEKS_MINIMAL}")
    elif konteks >= KONTEKS_MINIMAL:
        lapor(OK, f"Panjang konteks {config.LOKAL.model}: {fmt.angka(konteks)} token")
    else:
        saran = (f"Minta mentor mengatur OLLAMA_CONTEXT_LENGTH={KONTEKS_MINIMAL} di server bersama (scripts/server_bersama.sh)"
                 if model_di == "lan" else
                 f"macOS: launchctl setenv OLLAMA_CONTEXT_LENGTH {KONTEKS_MINIMAL}, lalu Quit Ollama (ikon menu bar) dan "
                 f"buka lagi (ulangi setelah Mac restart). Windows: setx OLLAMA_CONTEXT_LENGTH {KONTEKS_MINIMAL}, lalu "
                 "tutup dan buka lagi Ollama. Ulangi cek ini setelahnya")
        lapor(GAGAL, f"Panjang konteks {config.LOKAL.model} hanya {fmt.angka(konteks)} token (minimal "
              f"{fmt.angka(KONTEKS_MINIMAL)}): prompt agent dan RAG terpotong tanpa pesan error", saran)

# 5. Model embedding (RAG), diperiksa terpisah dari model chat
if CLOUD and config.EMBED_BASE_URL == config.LOKAL.base_url:
    lapor(GAGAL, "EMBED_BASE_URL belum diisi: Anthropic tidak menyediakan endpoint embedding",
          "Isi EMBED_BASE_URL=http://<IP server mentor>:11434/v1 (atau http://localhost:11434/v1 bila bge-m3 ada di laptop)")
else:
    t0 = time.perf_counter()
    try:
        vektor = rag.embed(["uji embedding"])[0]
        cocok = dimensi_indeks in (None, len(vektor))
        lapor(OK if cocok else GAGAL,
              f"Embedding {config.EMBED_MODEL} di {config.EMBED_BASE_URL} · dimensi {len(vektor)} · {time.perf_counter() - t0:.1f} dtk",
              "" if cocok else f"Dimensi berbeda dengan indeks bersama ({dimensi_indeks}): pakai EMBED_MODEL yang sama dengan mentor")
    except Exception as e:  # noqa: BLE001
        lapor(GAGAL, f"Embedding gagal di {config.EMBED_BASE_URL} ({pesan(e)[:80]})",
              f"Pastikan Ollama berjalan di alamat itu dan model sudah diunduh: ollama pull {config.EMBED_MODEL}")

# 6. Aplikasi ERP (dibutuhkan Latihan 7 dan panel AI di ERP; tidak wajib untuk latihan lain)
try:
    from asisten import erp_api  # noqa: E402

    profil = erp_api.SesiERP(timeout=5).login("andi")
    lapor(OK, f"ERP terhubung di {config.ERP_URL} · login andi berhasil"
              + (" · boleh membuat SO" if "so_buat" in profil.get("izin", []) else ""))
except Exception as e:  # noqa: BLE001
    lapor(INFO, f"ERP belum bisa dipakai ({pesan(e)})",
          "Hanya dibutuhkan Latihan 7: periksa ERP_URL dan ERP_PASSWORD di .env")

# 7. Model cloud (opsional: hanya untuk tombol Cloud / perbandingan)
if config.CLOUD.penyedia == "api":
    kosong = [n for n, v in (("CLOUD_BASE_URL", config.CLOUD.base_url), ("CLOUD_MODEL", config.CLOUD.model),
                             ("CLOUD_API_KEY", config.CLOUD.api_key)) if not v]
    if kosong:
        lapor(GAGAL, f"CLOUD_PENYEDIA=api, tetapi {', '.join(kosong)} belum diisi",
              "Isi di .env (lihat contoh di .env.example), atau kembalikan CLOUD_PENYEDIA=claude-code")
    else:
        lapor(OK, f"Model cloud lewat API: {config.CLOUD.model} di {host(config.CLOUD.base_url)} (tidak diuji, agar tidak memakai kuota)")
    cek_suhu("CLOUD_SUHU", config.CLOUD)
elif config.CLOUD.penyedia == "claude-code":
    import json  # noqa: E402
    import shutil  # noqa: E402
    import subprocess  # noqa: E402

    if not shutil.which(config.CLAUDE_BIN):
        lapor(INFO, "Claude Code tidak terpasang (opsional, hanya untuk mode Cloud)")
    else:
        try:
            r = subprocess.run([config.CLAUDE_BIN, "auth", "status", "--json"],
                               capture_output=True, text=True, timeout=30)
            status = json.loads(r.stdout or "{}")
        except (OSError, subprocess.TimeoutExpired, ValueError):
            status = {}
        if status.get("loggedIn"):
            lapor(OK, f"Claude Code sudah login ({status.get('subscriptionType') or status.get('authMethod')}) "
                      f"· mode Cloud memakai {config.CLOUD.label}")
        else:
            lapor(INFO, "Claude Code terpasang tetapi belum login (opsional, hanya untuk mode Cloud)",
                  "Jalankan 'claude' di terminal lalu /login dengan akun Claude")

print("\n" + ("Siap untuk workshop." if not masalah else f"Ada {masalah} hal yang perlu dibereskan."))
sys.exit(1 if masalah else 0)
