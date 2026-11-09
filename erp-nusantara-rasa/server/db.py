"""Akses database ERP (role erp_app). Semua query memakai parameter, bukan string gabungan."""
from __future__ import annotations

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
    if isinstance(nilai, dt.datetime):
        return nilai.isoformat(timespec="seconds")
    if isinstance(nilai, dt.date):
        return nilai.isoformat()
    return nilai


def rapikan(baris: dict) -> dict:
    return {k: _rapikan(v) for k, v in baris.items()}


@contextmanager
def koneksi() -> Iterator[psycopg.Connection]:
    with psycopg.connect(config.ERP_DATABASE_URL, row_factory=dict_row, connect_timeout=5) as conn:
        yield conn


def query(sql: str, params: dict | tuple | list | None = None) -> list[dict]:
    with koneksi() as conn:
        return [rapikan(r) for r in conn.execute(sql, params).fetchall()]


def satu(sql: str, params: dict | tuple | list | None = None) -> dict | None:
    hasil = query(sql, params)
    return hasil[0] if hasil else None


@lru_cache(maxsize=1)
def tanggal_sistem() -> dt.date:
    """Tanggal sistem ERP = tanggal posisi data (akhir periode berjalan)."""
    with koneksi() as conn:
        r = conn.execute("SELECT nilai::date AS t FROM erp.parameter WHERE kunci = 'tanggal_posisi'").fetchone()
    return r["t"]


def periode_berjalan() -> tuple[dt.date, dt.date]:
    akhir = tanggal_sistem()
    return akhir.replace(day=1), akhir


def catat_audit(conn: psycopg.Connection, pengguna: str, modul: str, aksi: str, objek: str = "", keterangan: str = "") -> None:
    conn.execute(
        """INSERT INTO erp.audit_log (pengguna, modul, aksi, objek, keterangan)
           VALUES (%s, %s, %s, %s, %s)""",
        (pengguna, modul, aksi, objek, keterangan))
