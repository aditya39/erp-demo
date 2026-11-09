"""Produk, bahan baku, resep, dan analisis HPP."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..sesi import punya, wajib
from .dashboard import tambah_bulan, ubah

router = APIRouter(prefix="/api")


def _bulan_akhir():
    return db.tanggal_sistem().replace(day=1)


@router.get("/produk")
def daftar_produk(q: str = "", kategori: str = "", u: dict = Depends(wajib("produk"))) -> dict:
    akhir = _bulan_akhir()
    lalu = tambah_bulan(akhir, -1)
    lihat_hpp, lihat_jual, lihat_stok = punya(u, "hpp"), punya(u, "penjualan"), punya(u, "stok")
    rows = db.query(f"""
        SELECT p.id, p.kode, p.nama, k.nama AS kategori, p.satuan, p.harga_jual, p.aktif,
               {'h.hpp_per_unit' if lihat_hpp else 'NULL::numeric'} AS hpp,
               {'round((p.harga_jual - h.hpp_per_unit) / p.harga_jual * 100, 1)' if lihat_hpp else 'NULL::numeric'} AS margin,
               {'j.qty' if lihat_jual else 'NULL::bigint'} AS qty_bulan_ini,
               {'j.qty_lalu' if lihat_jual else 'NULL::bigint'} AS qty_bulan_lalu,
               {'j.nilai' if lihat_jual else 'NULL::numeric'} AS nilai_bulan_ini,
               {'s.qty' if lihat_stok else 'NULL::bigint'} AS stok,
               {'s.menipis' if lihat_stok else 'NULL::bigint'} AS gudang_menipis
        FROM erp.produk p JOIN erp.kategori k ON k.id = p.kategori_id
        LEFT JOIN ai.v_hpp_bulanan h ON h.produk_id = p.id AND h.bulan = %(b)s
        LEFT JOIN (SELECT produk_id, sum(qty) FILTER (WHERE bulan = %(b)s) AS qty,
                          sum(qty) FILTER (WHERE bulan = %(l)s) AS qty_lalu,
                          sum(nilai) FILTER (WHERE bulan = %(b)s) AS nilai
                   FROM ai.v_penjualan WHERE bulan IN (%(b)s, %(l)s) GROUP BY produk_id) j ON j.produk_id = p.id
        LEFT JOIN (SELECT produk_id, sum(qty) AS qty, count(*) FILTER (WHERE qty < stok_minimum) AS menipis
                   FROM erp.stok GROUP BY produk_id) s ON s.produk_id = p.id
        WHERE (p.nama ILIKE %(q)s OR p.kode ILIKE %(q)s) {'AND k.nama = %(k)s' if kategori else ''}
        ORDER BY p.kode""", {"b": akhir, "l": lalu, "q": f"%{q.strip()}%", "k": kategori})
    for r in rows:
        r["ubah_qty"] = ubah(r["qty_bulan_lalu"] or 0, r["qty_bulan_ini"] or 0) if lihat_jual else None
    return {"data": rows, "bulan": akhir.isoformat(), "kolom": {"hpp": lihat_hpp, "penjualan": lihat_jual, "stok": lihat_stok}}


@router.get("/produk/{produk_id}")
def detail_produk(produk_id: int, u: dict = Depends(wajib("produk"))) -> dict:
    p = db.satu("""SELECT p.id, p.kode, p.nama, k.nama AS kategori, p.satuan, p.harga_jual, p.aktif
                   FROM erp.produk p JOIN erp.kategori k ON k.id = p.kategori_id WHERE p.id = %s""", (produk_id,))
    if not p:
        raise HTTPException(404, "Produk tidak ditemukan.")
    akhir = _bulan_akhir()
    awal = tambah_bulan(akhir, -11)
    if punya(u, "hpp"):
        p["hpp_bulanan"] = db.query("""SELECT bulan, unit_diproduksi, bahan_baku_per_unit, tenaga_kerja_per_unit,
                                              overhead_per_unit, hpp_per_unit
                                       FROM ai.v_hpp_bulanan WHERE produk_id = %s AND bulan BETWEEN %s AND %s
                                       ORDER BY bulan""", (produk_id, awal, akhir))
        lalu = tambah_bulan(akhir, -1)
        p["resep"] = db.query("""SELECT k.bahan_id, b.kode, k.bahan, k.satuan, k.qty_per_unit, k.harga_bahan,
                                        k.biaya_per_unit, kl.biaya_per_unit AS biaya_per_unit_lalu
                                 FROM ai.v_hpp_komponen k JOIN erp.bahan_baku b ON b.id = k.bahan_id
                                 LEFT JOIN ai.v_hpp_komponen kl ON kl.produk_id = k.produk_id AND kl.bahan_id = k.bahan_id
                                                                AND kl.bulan = %s
                                 WHERE k.produk_id = %s AND k.bulan = %s ORDER BY k.biaya_per_unit DESC""",
                              (lalu, produk_id, akhir))
        for r in p["resep"]:
            r["ubah"] = ubah(r["biaya_per_unit_lalu"] or 0, r["biaya_per_unit"])
    if punya(u, "penjualan"):
        p["penjualan_bulanan"] = db.query("""SELECT bulan, sum(qty) AS qty, sum(nilai) AS nilai FROM ai.v_penjualan
                                             WHERE produk_id = %s AND bulan BETWEEN %s AND %s GROUP BY bulan ORDER BY bulan""",
                                          (produk_id, awal, akhir))
        p["per_segmen"] = db.query("""SELECT segmen, sum(qty) AS qty, sum(nilai) AS nilai FROM ai.v_penjualan
                                      WHERE produk_id = %s AND bulan BETWEEN %s AND %s GROUP BY segmen ORDER BY nilai DESC""",
                                   (produk_id, tambah_bulan(akhir, -2), akhir))
        p["customer_teratas"] = db.query("""SELECT customer_id AS id, customer, segmen, sum(qty) AS qty, sum(nilai) AS nilai
                                            FROM ai.v_penjualan WHERE produk_id = %s AND bulan BETWEEN %s AND %s
                                            GROUP BY customer_id, customer, segmen ORDER BY nilai DESC LIMIT 5""",
                                         (produk_id, tambah_bulan(akhir, -2), akhir))
    if punya(u, "stok"):
        p["stok"] = db.query("""SELECT gudang, qty, stok_minimum, qty < stok_minimum AS menipis FROM erp.stok
                                WHERE produk_id = %s ORDER BY gudang""", (produk_id,))
    return p


class Harga(BaseModel):
    harga_jual: float = Field(gt=0)


@router.put("/produk/{produk_id}/harga")
def ubah_harga(produk_id: int, data: Harga, u: dict = Depends(wajib("produk_kelola"))) -> dict:
    lama = db.satu("SELECT kode, nama, harga_jual FROM erp.produk WHERE id = %s", (produk_id,))
    if not lama:
        raise HTTPException(404, "Produk tidak ditemukan.")
    with db.koneksi() as conn:
        conn.execute("UPDATE erp.produk SET harga_jual = %s WHERE id = %s", (round(data.harga_jual, -1), produk_id))
        db.catat_audit(conn, u["kode"], "Produksi", "Mengubah harga jual", f"{lama['kode']} {lama['nama']}",
                       f"Rp {lama['harga_jual']:,.0f} → Rp {round(data.harga_jual, -1):,.0f}".replace(",", "."))
    return {"ok": True}


@router.get("/bahan-baku")
def daftar_bahan(q: str = "", u: dict = Depends(wajib("hpp"))) -> dict:
    akhir = _bulan_akhir()
    rows = db.query("""
        SELECT b.id, b.kode, b.nama, b.satuan, h.harga, hl.harga AS harga_lalu, h12.harga AS harga_12_bulan,
               (SELECT count(*) FROM erp.resep r WHERE r.bahan_id = b.id) AS dipakai_produk
        FROM erp.bahan_baku b
        LEFT JOIN erp.harga_bahan h   ON h.bahan_id = b.id AND h.bulan = %(b)s
        LEFT JOIN erp.harga_bahan hl  ON hl.bahan_id = b.id AND hl.bulan = %(l)s
        LEFT JOIN erp.harga_bahan h12 ON h12.bahan_id = b.id AND h12.bulan = %(t)s
        WHERE b.nama ILIKE %(q)s OR b.kode ILIKE %(q)s ORDER BY b.kode""",
                    {"b": akhir, "l": tambah_bulan(akhir, -1), "t": tambah_bulan(akhir, -12), "q": f"%{q.strip()}%"})
    for r in rows:
        r["ubah"] = ubah(r["harga_lalu"] or 0, r["harga"] or 0)
        r["ubah_12"] = ubah(r["harga_12_bulan"] or 0, r["harga"] or 0)
    return {"data": rows, "bulan": akhir.isoformat()}


@router.get("/bahan-baku/{bahan_id}")
def detail_bahan(bahan_id: int, u: dict = Depends(wajib("hpp"))) -> dict:
    b = db.satu("SELECT id, kode, nama, satuan FROM erp.bahan_baku WHERE id = %s", (bahan_id,))
    if not b:
        raise HTTPException(404, "Bahan baku tidak ditemukan.")
    akhir = _bulan_akhir()
    b["harga_bulanan"] = db.query("SELECT bulan, harga FROM erp.harga_bahan WHERE bahan_id = %s ORDER BY bulan", (bahan_id,))
    b["produk"] = db.query("""SELECT k.produk_id AS id, k.produk, k.qty_per_unit, k.biaya_per_unit, h.hpp_per_unit,
                                     round(k.biaya_per_unit / h.hpp_per_unit * 100, 1) AS porsi_hpp
                              FROM ai.v_hpp_komponen k
                              JOIN ai.v_hpp_bulanan h ON h.produk_id = k.produk_id AND h.bulan = k.bulan
                              WHERE k.bahan_id = %s AND k.bulan = %s ORDER BY porsi_hpp DESC""", (bahan_id, akhir))
    return b


@router.get("/hpp")
def laporan_hpp(u: dict = Depends(wajib("hpp"))) -> dict:
    akhir = _bulan_akhir()
    lalu = tambah_bulan(akhir, -1)
    rows = db.query("""
        SELECT h.produk_id AS id, h.kode_produk AS kode, h.produk, h.unit_diproduksi, h.bahan_baku_per_unit,
               h.tenaga_kerja_per_unit, h.overhead_per_unit, h.hpp_per_unit, hl.hpp_per_unit AS hpp_lalu,
               p.harga_jual, round((p.harga_jual - h.hpp_per_unit) / p.harga_jual * 100, 1) AS margin,
               round((p.harga_jual - hl.hpp_per_unit) / p.harga_jual * 100, 1) AS margin_lalu
        FROM ai.v_hpp_bulanan h JOIN erp.produk p ON p.id = h.produk_id
        LEFT JOIN ai.v_hpp_bulanan hl ON hl.produk_id = h.produk_id AND hl.bulan = %s
        WHERE h.bulan = %s ORDER BY h.kode_produk""", (lalu, akhir))
    for r in rows:
        r["ubah"] = ubah(r["hpp_lalu"] or 0, r["hpp_per_unit"])
        r["perlu_kajian"] = (r["ubah"] or 0) > 8
    tren = db.query("""SELECT bulan, round(avg(hpp_per_unit), 2) AS rata_hpp FROM ai.v_hpp_bulanan
                       WHERE bulan BETWEEN %s AND %s GROUP BY bulan ORDER BY bulan""", (tambah_bulan(akhir, -11), akhir))
    return {"bulan": akhir.isoformat(), "bulan_lalu": lalu.isoformat(), "data": rows, "tren": tren}
