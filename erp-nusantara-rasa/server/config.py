"""
Konfigurasi ERP. Dibaca dari environment variable atau file .env di root folder ini.

Catatan keamanan:
- ERP memakai role database `erp_app` (boleh baca-tulis tabel erp.*).
- Asisten AI TIDAK memakai koneksi ini. Asisten memakai paket `asisten` dari kit
  dengan role `erp_ai_readonly` (hanya baca view schema ai). Karena itu nama
  variabelnya sengaja dibedakan (ERP_DATABASE_URL vs DATABASE_URL milik kit).
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(nama: str, default: str = "") -> str:
    return os.getenv(nama, default).strip()


# Password default sudah dipublikasikan di kit: ganti lewat ERP_APP_PASSWORD / DB_ADMIN_PASSWORD (.env)
# sebelum database dibuka di jaringan (server LAN bersama). Pakai huruf, angka, - atau _ (masuk ke URL).
ERP_DATABASE_URL = _env("ERP_DATABASE_URL", f"postgresql://erp_app:{_env('ERP_APP_PASSWORD', 'aplikasi_erp')}@localhost:5433/erp")
# Hanya untuk migrasi saat server start (membuat role erp_app & menyetel password-nya, tabel tambahan ERP).
ERP_DATABASE_URL_ADMIN = _env("ERP_DATABASE_URL_ADMIN",
                              f"postgresql://erp_admin:{_env('DB_ADMIN_PASSWORD', 'admin_workshop')}@localhost:5433/erp")

HOST = _env("ERP_HOST", "127.0.0.1")
PORT = int(_env("ERP_PORT", "8080"))

# Paket agent AI (asisten) diambil dari kit workshop, supaya demo ERP dan hands-on
# memakai "otak" AI yang sama (tools, RAG, pengaman).
ASISTEN_PATH = Path(_env("ASISTEN_PATH", str(ROOT.parent / "kit" / "asisten-erp-ai"))).resolve()
if str(ASISTEN_PATH) not in sys.path:
    sys.path.insert(0, str(ASISTEN_PATH))

FOLDER_REKAMAN = ROOT / "rekaman"
FOLDER_FRONTEND = ROOT / "frontend" / "dist" / "frontend" / "browser"


def _kunci_sesi() -> str:
    """Kunci penanda tangan cookie sesi. Dibuat sekali lalu disimpan di .kunci-sesi (tidak di-commit)."""
    dari_env = _env("ERP_SESSION_SECRET")
    if dari_env:
        return dari_env
    f = ROOT / ".kunci-sesi"
    if not f.exists():
        f.write_text(secrets.token_hex(32), encoding="utf-8")
    return f.read_text(encoding="utf-8").strip()


SESSION_SECRET = _kunci_sesi()
SESSION_JAM = 12
