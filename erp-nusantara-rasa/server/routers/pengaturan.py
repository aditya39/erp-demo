"""Dokumen perusahaan, pengguna & hak akses, log aktivitas."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import config, db
from ..izin import KODE_IZIN, LABEL_IZIN
from ..sesi import wajib
from .penjualan import _urut, halaman

router = APIRouter(prefix="/api")

FOLDER_DOKUMEN = config.ASISTEN_PATH / "dokumen"   # sumber yang sama dengan RAG asisten AI


def _meta_dokumen(path) -> dict:
    teks = path.read_text(encoding="utf-8")
    judul = next((b[2:].strip() for b in teks.splitlines() if b.startswith("# ")), path.stem)
    meta = re.search(r"Nomor dokumen:\s*([^·\n]+)·\s*([^·\n]+)·\s*Pemilik:\s*([^\n]+)", teks)
    return {"slug": path.stem, "judul": judul,
            "nomor": meta.group(1).strip() if meta else "", "berlaku": meta.group(2).strip() if meta else "",
            "pemilik": meta.group(3).strip() if meta else "",
            "bagian": len(re.findall(r"^## ", teks, flags=re.M)), "kata": len(teks.split())}


@router.get("/dokumen")
def daftar_dokumen(u: dict = Depends(wajib("dokumen"))) -> dict:
    return {"data": [_meta_dokumen(p) for p in sorted(FOLDER_DOKUMEN.glob("*.md"))]}


@router.get("/dokumen/{slug}")
def baca_dokumen(slug: str, u: dict = Depends(wajib("dokumen"))) -> dict:
    path = (FOLDER_DOKUMEN / f"{slug}.md").resolve()
    if path.parent != FOLDER_DOKUMEN.resolve() or not path.exists():
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    return {**_meta_dokumen(path), "isi": path.read_text(encoding="utf-8")}


@router.get("/pengguna")
def daftar_pengguna(u: dict = Depends(wajib("pengaturan"))) -> dict:
    rows = db.query("""SELECT kode, nama, jabatan, divisi, email, izin, aktif, login_terakhir
                       FROM erp.pengguna ORDER BY array_length(izin, 1) DESC, kode""")
    return {"data": rows}


class Izin(BaseModel):
    izin: list[str]


@router.put("/pengguna/{kode}/izin")
def ubah_izin(kode: str, data: Izin, u: dict = Depends(wajib("pengaturan"))) -> dict:
    lama = db.satu("SELECT izin FROM erp.pengguna WHERE kode = %s", (kode,))
    if not lama:
        raise HTTPException(404, "Pengguna tidak ditemukan.")
    baru = [i for i in KODE_IZIN if i in set(data.izin)]
    if kode == u["kode"] and "pengaturan" not in baru:
        raise HTTPException(422, "Anda tidak dapat mencabut izin pengaturan milik sendiri.")
    tambah = [LABEL_IZIN[i] for i in baru if i not in lama["izin"]]
    cabut = [LABEL_IZIN[i] for i in lama["izin"] if i not in baru and i in LABEL_IZIN]
    with db.koneksi() as conn:
        conn.execute("UPDATE erp.pengguna SET izin = %s WHERE kode = %s", (baru, kode))
        ket = "; ".join(x for x in (f"+ {', '.join(tambah)}" if tambah else "", f"− {', '.join(cabut)}" if cabut else "") if x)
        db.catat_audit(conn, u["kode"], "Pengaturan", "Mengubah hak akses", kode, ket or "tanpa perubahan")
    return {"ok": True, "izin": baru}


@router.get("/audit")
def audit(q: str = "", modul: str = "", pengguna: str = "", page: int = 1, size: int = 30,
          u: dict = Depends(wajib("pengaturan"))) -> dict:
    where, p = [], {"q": f"%{q.strip()}%"}
    if q.strip():
        where.append("(a.aksi ILIKE %(q)s OR a.objek ILIKE %(q)s OR a.keterangan ILIKE %(q)s)")
    if modul:
        where.append("a.modul = %(m)s")
        p["m"] = modul
    if pengguna:
        where.append("a.pengguna = %(u)s")
        p["u"] = pengguna
    sql = f"""SELECT a.id, a.waktu, a.pengguna, coalesce(pg.nama, a.pengguna) AS nama, a.modul, a.aksi, a.objek, a.keterangan
              FROM erp.audit_log a LEFT JOIN erp.pengguna pg ON pg.kode = a.pengguna
              {'WHERE ' + ' AND '.join(where) if where else ''}"""
    hasil = halaman(sql, p, page, size, _urut("", {}, "waktu DESC, id DESC"))
    hasil["modul"] = [r["modul"] for r in db.query("SELECT DISTINCT modul FROM erp.audit_log ORDER BY modul")]
    return hasil
