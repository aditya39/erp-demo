"""Klien model bahasa. Lokal (Ollama) dan cloud memakai API yang sama: OpenAI Chat Completions."""
from __future__ import annotations

from openai import OpenAI

from . import config
from .config import ModelConfig


def buat_klien(cfg: ModelConfig) -> OpenAI:
    if not cfg.aktif:
        raise RuntimeError(f"Model {cfg.mode} belum dikonfigurasi (lihat .env.example).")
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key or "kosong",
                  timeout=config.MODEL_TIMEOUT, max_retries=config.MODEL_COBA_ULANG)


def opsi_tambahan(cfg: ModelConfig) -> dict:
    """Parameter khusus penyedia. reasoning_effort='none' mematikan mode berpikir Qwen3 di Ollama."""
    return {"reasoning_effort": cfg.reasoning_effort} if cfg.reasoning_effort else {}
