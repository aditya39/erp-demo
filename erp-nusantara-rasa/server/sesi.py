"""Dependency FastAPI: user yang login (dari cookie sesi) dan pengecekan hak akses."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from . import db, keamanan
from .izin import LABEL_IZIN

COOKIE = "erp_sesi"


def ambil_pengguna(kode: str) -> dict | None:
    return db.satu("""SELECT kode, nama, jabatan, divisi, email, izin, aktif, login_terakhir
                      FROM erp.pengguna WHERE kode = %s""", (kode,))


def pengguna_login(request: Request) -> dict:
    kode = keamanan.baca_token(request.cookies.get(COOKIE))
    u = ambil_pengguna(kode) if kode else None
    if not u or not u["aktif"]:
        raise HTTPException(401, "Sesi berakhir. Silakan masuk kembali.")
    return u


def wajib(*izin: str):
    """Izinkan request bila user memiliki SALAH SATU izin yang disebut."""
    def cek(u: dict = Depends(pengguna_login)) -> dict:
        if not any(i in u["izin"] for i in izin):
            raise HTTPException(403, "Anda tidak memiliki hak akses: " + " / ".join(LABEL_IZIN.get(i, i) for i in izin))
        return u
    return cek


def punya(u: dict, izin: str) -> bool:
    return izin in u["izin"]
