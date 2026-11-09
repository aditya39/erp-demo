"""Keuangan: umur piutang dan penerimaan pembayaran."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db, logika
from ..sesi import wajib
from .penjualan import _urut, halaman

router = APIRouter(prefix="/api")

BUCKET = """CASE WHEN hari_lewat_jatuh_tempo = 0 THEN 'b0' WHEN hari_lewat_jatuh_tempo <= 30 THEN 'b1'
                 WHEN hari_lewat_jatuh_tempo <= 60 THEN 'b2' WHEN hari_lewat_jatuh_tempo <= 90 THEN 'b3' ELSE 'b4' END"""


@router.get("/piutang")
def piutang(q: str = "", segmen: str = "", hanya_lewat: bool = False, u: dict = Depends(wajib("piutang"))) -> dict:
    where, p = [], {"q": f"%{q.strip()}%"}
    if q.strip():
        where.append("customer ILIKE %(q)s")
    if segmen:
        where.append("segmen = %(s)s")
        p["s"] = segmen
    w = ("WHERE " + " AND ".join(where)) if where else ""
    per_customer = db.query(f"""
        SELECT customer_id AS id, customer, segmen, kota,
               sum(sisa) AS total,
               coalesce(sum(sisa) FILTER (WHERE {BUCKET} = 'b0'), 0) AS b0,
               coalesce(sum(sisa) FILTER (WHERE {BUCKET} = 'b1'), 0) AS b1,
               coalesce(sum(sisa) FILTER (WHERE {BUCKET} = 'b2'), 0) AS b2,
               coalesce(sum(sisa) FILTER (WHERE {BUCKET} = 'b3'), 0) AS b3,
               coalesce(sum(sisa) FILTER (WHERE {BUCKET} = 'b4'), 0) AS b4,
               count(*) AS faktur, max(hari_lewat_jatuh_tempo) AS hari_maks
        FROM ai.v_piutang {w}
        GROUP BY customer_id, customer, segmen, kota
        {'HAVING max(hari_lewat_jatuh_tempo) > 0' if hanya_lewat else ''}
        ORDER BY total DESC""", p)
    limit = {r["id"]: float(r["limit_kredit"]) for r in db.query("SELECT id, limit_kredit FROM erp.customer")}
    for r in per_customer:
        r["limit_kredit"] = limit.get(r["id"], 0)
        r["tahap"] = logika.tahap_penagihan(r["hari_maks"])
    ringkasan = {k: sum(r[k] for r in per_customer) for k in ("b0", "b1", "b2", "b3", "b4", "total")}
    ringkasan["customer"] = len(per_customer)
    ringkasan["lewat"] = ringkasan["total"] - ringkasan["b0"]
    ringkasan["faktur_lewat"] = db.satu("SELECT count(*) AS n FROM ai.v_piutang WHERE hari_lewat_jatuh_tempo > 0")["n"]
    return {"tanggal": db.tanggal_sistem().isoformat(), "ringkasan": ringkasan, "customer": per_customer}


@router.get("/piutang/terbuka")
def faktur_terbuka(customer_id: int, u: dict = Depends(wajib("piutang", "pembayaran_catat"))) -> dict:
    rows = db.query("""SELECT faktur_id AS id, nomor_faktur AS nomor, tanggal, jatuh_tempo, total, terbayar, sisa,
                              hari_lewat_jatuh_tempo AS hari
                       FROM ai.v_piutang WHERE customer_id = %s ORDER BY jatuh_tempo, tanggal, faktur_id""", (customer_id,))
    return {"data": rows, "total_sisa": sum(r["sisa"] for r in rows)}


@router.get("/pembayaran")
def daftar_pembayaran(q: str = "", metode: str = "", page: int = 1, size: int = 20, sort: str = "-tanggal",
                      u: dict = Depends(wajib("piutang", "pembayaran_catat"))) -> dict:
    where, p = [], {"q": f"%{q.strip()}%"}
    if q.strip():
        where.append("(c.nama ILIKE %(q)s OR f.nomor ILIKE %(q)s OR b.referensi ILIKE %(q)s)")
    if metode:
        where.append("b.metode = %(m)s")
        p["m"] = metode
    sql = f"""SELECT b.id, b.tanggal, b.jumlah, b.metode, b.referensi, b.dibuat_oleh,
                     coalesce(pg.nama, CASE WHEN b.dibuat_oleh = 'migrasi' THEN 'Sari Wulandari' ELSE b.dibuat_oleh END) AS dicatat_oleh,
                     f.id AS faktur_id, f.nomor AS nomor_faktur, c.id AS customer_id, c.nama AS customer
              FROM erp.pembayaran b JOIN erp.faktur f ON f.id = b.faktur_id
              JOIN erp.customer c ON c.id = f.customer_id
              LEFT JOIN erp.pengguna pg ON pg.kode = b.dibuat_oleh
              {'WHERE ' + ' AND '.join(where) if where else ''}"""
    urut = _urut(sort, {"tanggal": "tanggal", "jumlah": "jumlah", "customer": "customer"}, "tanggal DESC, id DESC")
    hasil = halaman(sql, p, page, size, urut)
    awal, akhir = db.periode_berjalan()
    hasil["bulan_ini"] = db.satu("""SELECT coalesce(sum(jumlah), 0) AS jumlah, count(*) AS n FROM erp.pembayaran
                                    WHERE tanggal BETWEEN %s AND %s""", (awal, akhir))
    return hasil


class Pembayaran(BaseModel):
    customer_id: int
    tanggal: dt.date
    jumlah: float
    metode: str
    referensi: str = ""
    faktur_id: int | None = None


@router.post("/pembayaran")
def catat(data: Pembayaran, u: dict = Depends(wajib("pembayaran_catat"))) -> dict:
    try:
        with db.koneksi() as conn:
            return logika.catat_pembayaran(conn, data.model_dump(), u["kode"])
    except logika.AturanBisnis as e:
        raise HTTPException(422, str(e)) from e
