"""Konfigurasi dibaca dari environment variable atau file .env di root proyek."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(nama: str, default: str = "") -> str:
    return os.getenv(nama, default).strip()


def _suhu(nama: str, default: str = "", cadangan: str = "") -> float | None:
    """
    Suhu (temperature) model. Nilai kosong = None = parameter temperature TIDAK dikirim
    (model Claude terbaru lewat API kompatibel OpenAI menolak nilai di bawah 1).
    """
    teks = os.getenv(nama)
    if teks is None and cadangan:
        teks = os.getenv(cadangan)
    teks = (default if teks is None else teks).strip()
    return float(teks) if teks else None


def _host_anthropic(url: str) -> bool:
    """True bila endpoint model adalah API Anthropic (mis. https://api.anthropic.com/v1/)."""
    return (urlparse(url).hostname or "").lower().endswith("anthropic.com")


def _suhu_lokal(base_url: str) -> float | None:
    """
    Suhu model "lokal". Default 0.2 untuk Ollama; untuk API Anthropic (profil c) default-nya None (tidak dikirim),
    karena model Claude terbaru menolak temperature di bawah 1. Nilai yang diisi sendiri (LOKAL_SUHU, atau
    SUHU = nama lama) tetap dipakai apa adanya; scripts/cek_setup.py memberi tanda ✗ bila nilainya di bawah 1.
    """
    return _suhu("LOKAL_SUHU", "" if _host_anthropic(base_url) else "0.2", cadangan="SUHU")


# Koneksi asisten AI: role read-only yang hanya bisa membaca schema "ai" dan "rag".
DATABASE_URL = _env("DATABASE_URL", "postgresql://erp_ai_readonly:baca_saja@localhost:5433/erp")
# Koneksi admin: hanya untuk skrip ingest dokumen (RAG), BUKAN untuk agent.
DATABASE_URL_ADMIN = _env("DATABASE_URL_ADMIN", "postgresql://erp_admin:admin_workshop@localhost:5433/erp")


@dataclass(frozen=True)
class ModelConfig:
    mode: str               # "lokal" atau "cloud"
    base_url: str           # endpoint yang kompatibel dengan OpenAI Chat Completions
    api_key: str
    model: str
    reasoning_effort: str   # "" = tidak dikirim; "none" = matikan mode berpikir (Ollama)
    penyedia: str = "api"   # "api" (endpoint OpenAI-compatible) atau "claude-code" (langganan Claude)
    suhu: float | None = None   # temperature; None = tidak dikirim ke endpoint

    @property
    def aktif(self) -> bool:
        if self.penyedia == "claude-code":
            return shutil.which(CLAUDE_BIN) is not None
        return bool(self.base_url and self.model)

    @property
    def label(self) -> str:
        return f"Claude Code · {self.model or 'default'}" if self.penyedia == "claude-code" else self.model or "-"


_LOKAL_BASE_URL = _env("LOKAL_BASE_URL", "http://localhost:11434/v1")

LOKAL = ModelConfig(
    mode="lokal",
    base_url=_LOKAL_BASE_URL,
    api_key=_env("LOKAL_API_KEY", "ollama"),
    model=_env("LOKAL_MODEL", "qwen3:8b"),
    reasoning_effort=_env("LOKAL_REASONING_EFFORT", "none"),
    suhu=_suhu_lokal(_LOKAL_BASE_URL),
)

# Cloud: "claude-code" memakai Claude Code yang sudah login dengan langganan Claude (tanpa API key),
# "api" memakai endpoint OpenAI-compatible + API key (lihat .env.example).
CLOUD_PENYEDIA = _env("CLOUD_PENYEDIA", "claude-code")
CLAUDE_BIN = _env("CLAUDE_BIN", "claude")

CLOUD = ModelConfig(
    mode="cloud",
    base_url=_env("CLOUD_BASE_URL"),
    api_key=_env("CLOUD_API_KEY"),
    model=_env("CLOUD_MODEL", "sonnet" if CLOUD_PENYEDIA == "claude-code" else ""),
    reasoning_effort=_env("CLOUD_REASONING_EFFORT"),
    penyedia=CLOUD_PENYEDIA,
    suhu=_suhu("CLOUD_SUHU"),
)

# Embedding untuk RAG selalu lokal: isi dokumen tidak keluar dari jaringan.
EMBED_BASE_URL = _env("EMBED_BASE_URL", LOKAL.base_url)
EMBED_MODEL = _env("EMBED_MODEL", "bge-m3")
# Kunci endpoint embedding. Default "ollama": API key model cloud (LOKAL_API_KEY) tidak ikut dikirim ke Ollama.
EMBED_API_KEY = _env("EMBED_API_KEY", "ollama")

# Aplikasi ERP (dipakai Latihan 7: simulasi & simpan sales order lewat API ERP dengan sesi user).
ERP_URL = _env("ERP_URL", "http://localhost:8080").rstrip("/")
ERP_PASSWORD = _env("ERP_PASSWORD", "demo123")

MAKS_LANGKAH = int(_env("MAKS_LANGKAH", "6"))
# Batas tunggu satu jawaban model (detik) dan jumlah coba ulang otomatis. Di server bersama, coba ulang
# menambah antrean untuk semua peserta, jadi default-nya hanya sekali.
MODEL_TIMEOUT = float(_env("MODEL_TIMEOUT", "300"))
MODEL_COBA_ULANG = int(_env("MODEL_COBA_ULANG", "1"))
SUHU = LOKAL.suhu   # nama lama (kompatibilitas); pakai ModelConfig.suhu
REKAM = _env("REKAM", "1") == "1"
FOLDER_REKAMAN = ROOT / "rekaman"
FOLDER_DOKUMEN = ROOT / "dokumen"


def model_untuk(mode: str) -> ModelConfig:
    return CLOUD if mode == "cloud" else LOKAL
