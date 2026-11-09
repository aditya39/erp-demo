"""Persediaan: posisi stok per gudang, mutasi, penyesuaian (stock opname)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db, logika
from ..sesi import punya, wajib
from .penjualan import _urut, halaman

router = APIRouter(prefix="/api")


@router.get("/stok")
def stok(q: str = "", gudang: str = "", status: str = "", u: dict = Depends(wajib("stok"))) -> dict:
    where, p = [], {"q": f"%{q.strip()}%"}
    if q.strip():
        where.append("(p.nama ILIKE %(q)s OR p.kode ILIKE %(q)s)")
    if gudang:
        where.append("s.gudang = %(g)s")
        p["g"] = gudang
    if status == "menipis":
        where.append("s.qty < s.stok_minimum")
    lihat_hpp = punya(u, "hpp")
    rows = db.query(f"""
        SELECT p.id AS produk_id, p.kode, p.nama, k.nama AS kategori, p.satuan, s.gudang, s.qty, s.stok_minimum,
               CASE WHEN s.qty = 0 THEN 'Habis' WHEN s.qty < s.stok_minimum THEN 'Menipis' ELSE 'Aman' END AS status,
               {'round(s.qty * h.hpp_per_unit)' if lihat_hpp else 'NULL::numeric'} AS nilai_stok,
               coalesce(j.rata_harian, 0) AS rata_jual_harian,
               CASE WHEN coalesce(j.rata_harian, 0) > 0 THEN round(s.qty / j.rata_harian, 1) END AS hari_cukup,
               m.terakhir AS mutasi_terakhir
        FROM erp.stok s JOIN erp.produk p ON p.id = s.produk_id JOIN erp.kategori k ON k.id = p.kategori_id
        LEFT JOIN ai.v_hpp_bulanan h ON h.produk_id = p.id AND h.bulan = (SELECT max(bulan) FROM ai.v_hpp_bulanan)
        LEFT JOIN (SELECT d.produk_id, f.gudang, sum(d.qty) / 30.0 AS rata_harian
                   FROM erp.faktur_detail d JOIN erp.faktur f ON f.id = d.faktur_id
                   WHERE f.tanggal > %(t)s::date - 30 GROUP BY d.produk_id, f.gudang) j
               ON j.produk_id = p.id AND j.gudang = s.gudang
        LEFT JOIN (SELECT produk_id, gudang, max(tanggal) AS terakhir FROM erp.mutasi_stok GROUP BY produk_id, gudang) m
               ON m.produk_id = p.id AND m.gudang = s.gudang
        {'WHERE ' + ' AND '.join(where) if where else ''}
        ORDER BY (s.qty >= s.stok_minimum), p.kode, s.gudang""", {**p, "t": db.tanggal_sistem()})
    ringkasan = {"baris": len(rows), "menipis": sum(r["status"] != "Aman" for r in rows),
                 "nilai": sum(r["nilai_stok"] or 0 for r in rows) if lihat_hpp else None,
                 "qty": sum(r["qty"] for r in rows)}
    return {"data": rows, "ringkasan": ringkasan}


@router.get("/mutasi-stok")
def mutasi(q: str = "", gudang: str = "", jenis: str = "", page: int = 1, size: int = 25, sort: str = "-tanggal",
           u: dict = Depends(wajib("stok"))) -> dict:
    where, p = [], {"q": f"%{q.strip()}%"}
    if q.strip():
        where.append("(p.nama ILIKE %(q)s OR p.kode ILIKE %(q)s OR m.referensi ILIKE %(q)s)")
    if gudang:
        where.append("m.gudang = %(g)s")
        p["g"] = gudang
    if jenis:
        where.append("m.jenis = %(j)s")
        p["j"] = jenis
    sql = f"""SELECT m.id, m.tanggal, m.gudang, m.jenis, m.qty, m.saldo, m.referensi, m.keterangan, m.dibuat_pada,
                     coalesce(pg.nama, m.pengguna) AS pengguna, p.id AS produk_id, p.kode, p.nama, p.satuan
              FROM erp.mutasi_stok m JOIN erp.produk p ON p.id = m.produk_id
              LEFT JOIN erp.pengguna pg ON pg.kode = m.pengguna
              {'WHERE ' + ' AND '.join(where) if where else ''}"""
    urut = _urut(sort, {"tanggal": "tanggal", "qty": "qty", "nama": "nama"}, "tanggal DESC, id DESC")
    return halaman(sql, p, page, size, urut)


class Penyesuaian(BaseModel):
    produk_id: int
    gudang: str
    tanggal: dt.date
    qty_fisik: int
    alasan: str
    stok_minimum: int | None = None


@router.post("/stok/penyesuaian")
def penyesuaian(data: Penyesuaian, u: dict = Depends(wajib("stok_sesuaikan"))) -> dict:
    try:
        with db.koneksi() as conn:
            return logika.sesuaikan_stok(conn, data.model_dump(), u["kode"])
    except logika.AturanBisnis as e:
        raise HTTPException(422, str(e)) from e
