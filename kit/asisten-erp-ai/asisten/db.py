"""Akses database untuk tools. Semua query memakai parameter, bukan string gabungan."""
from __future__ import annotations

import contextvars
import datetime as dt
from contextlib import contextmanager
from decimal import Decimal
from functools import lru_cache
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from . import config


def _rapikan(nilai: Any) -> Any:
    if isinstance(nilai, Decimal):
        return int(nilai) if nilai == nilai.to_integral_value() else float(nilai)
    if isinstance(nilai, (dt.date, dt.datetime)):
        return nilai.isoformat()
    return nilai


# Pencatat SQL: agent.eksekusi_tool membuka pencatat selama satu tool berjalan, sehingga layar
# bisa menampilkan query yang benar-benar dijalankan tool. Catatan ini tidak dikirim ke model.
_PENCATAT: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("pencatat_query", default=None)


@contextmanager
def catat_query() -> Iterator[list[dict]]:
    """Kumpulkan {"sql", "params"} setiap query yang dijalankan di dalam blok ini."""
    daftar: list[dict] = []
    token = _PENCATAT.set(daftar)
    try:
        yield daftar
    finally:
        _PENCATAT.reset(token)


def _ringkas_param(nilai: Any) -> Any:
    """Parameter untuk ditampilkan: vektor embedding dan teks panjang dipersingkat."""
    if isinstance(nilai, dict):
        return {k: _ringkas_param(v) for k, v in nilai.items()}
    if isinstance(nilai, (list, tuple)):
        return [_ringkas_param(v) for v in nilai] if len(nilai) <= 20 else f"[…{len(nilai)} nilai]"
    if isinstance(nilai, str) and len(nilai) > 200:
        if nilai.startswith("[") and nilai.endswith("]"):
            return f"[…{nilai.count(',') + 1} dimensi]"
        return nilai[:200] + "…"
    return _rapikan(nilai)


def query(sql: str, params: dict | tuple | list | None = None, admin: bool = False) -> list[dict]:
    """Jalankan SELECT dan kembalikan list of dict yang siap di-JSON-kan."""
    pencatat = _PENCATAT.get()
    if pencatat is not None:  # dicatat sebelum dijalankan, agar query yang gagal tetap terlihat
        pencatat.append({"sql": " ".join(sql.split()), "params": _ringkas_param(params)})
    url = config.DATABASE_URL_ADMIN if admin else config.DATABASE_URL
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=5) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{k: _rapikan(v) for k, v in r.items()} for r in rows]


@lru_cache(maxsize=1)
def info() -> dict:
    """Nama perusahaan dan tanggal posisi data (tanggal terakhir data ERP)."""
    baris = query("SELECT nama_perusahaan, tanggal_posisi FROM ai.v_info")[0]
    pertama = query("SELECT min(bulan) AS bulan FROM ai.v_hpp_bulanan")[0]["bulan"]
    posisi = dt.date.fromisoformat(baris["tanggal_posisi"])
    return {
        "nama_perusahaan": baris["nama_perusahaan"],
        "tanggal_posisi": posisi,
        "bulan_pertama": dt.date.fromisoformat(pertama),
        "bulan_terakhir": posisi.replace(day=1),
    }
