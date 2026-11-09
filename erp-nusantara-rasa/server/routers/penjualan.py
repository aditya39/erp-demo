"""Penjualan: sales order, faktur, customer, laporan penjualan."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, logika, riwayat
from ..sesi import punya, wajib
from .dashboard import tambah_bulan

router = APIRouter(prefix="/api")


def halaman(sql: str, params: dict, page: int, size: int, urut: str) -> dict:
    """Paginasi: `urut` diterapkan di query terluar supaya urutan pasti."""
    size = max(5, min(size, 5000))   # 5000 dipakai untuk ekspor CSV
    page = max(1, page)
    rows = db.query(f"SELECT *, count(*) OVER () AS _total FROM ({sql}) x ORDER BY {urut} "
                    f"LIMIT {size} OFFSET {(page - 1) * size}", params)
    total = rows[0]["_total"] if rows else 0
    for r in rows:
        r.pop("_total", None)
    return {"data": rows, "total": total, "page": page, "size": size}


def _urut(sort: str, kolom: dict[str, str], default: str) -> str:
    desc = sort.startswith("-")
    k = kolom.get(sort.lstrip("-"))
    return f"{k} {'DESC' if desc else 'ASC'}, id DESC" if k else default


SQL_FAKTUR = """
    SELECT f.id, f.nomor, f.tanggal, f.jatuh_tempo, f.total, f.gudang, f.so_id,
           c.id AS customer_id, c.nama AS customer, c.kota, c.segmen,
           coalesce(b.terbayar, 0) AS terbayar, f.total - coalesce(b.terbayar, 0) AS sisa,
           CASE WHEN f.total - coalesce(b.terbayar, 0) <= 0.5 THEN 'Lunas'
                WHEN f.jatuh_tempo < %(tgl)s THEN 'Jatuh Tempo'
                WHEN coalesce(b.terbayar, 0) > 0 THEN 'Sebagian'
                ELSE 'Belum Lunas' END AS status,
           CASE WHEN f.total - coalesce(b.terbayar, 0) <= 0.5 THEN 0
                ELSE greatest(%(tgl)s - f.jatuh_tempo, 0) END AS hari_lewat
    FROM erp.faktur f
    JOIN erp.customer c ON c.id = f.customer_id
    LEFT JOIN (SELECT faktur_id, sum(jumlah) AS terbayar FROM erp.pembayaran GROUP BY faktur_id) b ON b.faktur_id = f.id
"""


# ---------------------------------------------------------------------------
# Faktur
# ---------------------------------------------------------------------------
@router.get("/faktur")
def daftar_faktur(q: str = "", status: str = "", customer_id: int | None = None, dari: dt.date | None = None,
                  sampai: dt.date | None = None, page: int = 1, size: int = 20, sort: str = "-tanggal",
                  u: dict = Depends(wajib("penjualan"))) -> dict:
    where, p = [], {"tgl": db.tanggal_sistem(), "q": f"%{q.strip()}%"}
    if q.strip():
        where.append("(nomor ILIKE %(q)s OR customer ILIKE %(q)s)")
    if status:
        where.append("status = %(status)s")
        p["status"] = status
    if customer_id:
        where.append("customer_id = %(c)s")
        p["c"] = customer_id
    if dari:
        where.append("tanggal >= %(dari)s")
        p["dari"] = dari
    if sampai:
        where.append("tanggal <= %(sampai)s")
        p["sampai"] = sampai
    urut = _urut(sort, {"tanggal": "tanggal", "nomor": "nomor", "customer": "customer", "total": "total",
                        "sisa": "sisa", "jatuh_tempo": "jatuh_tempo"}, "tanggal DESC, id DESC")
    sql = f"SELECT * FROM ({SQL_FAKTUR}) f {'WHERE ' + ' AND '.join(where) if where else ''}"
    hasil = halaman(sql, p, page, size, urut)
    hasil["ringkasan"] = db.satu(f"""SELECT count(*) AS jumlah, coalesce(sum(total), 0) AS total, coalesce(sum(sisa), 0) AS sisa
                                     FROM ({SQL_FAKTUR}) f {'WHERE ' + ' AND '.join(where) if where else ''}""", p)
    return hasil


@router.get("/faktur/{faktur_id}")
def detail_faktur(faktur_id: int, u: dict = Depends(wajib("penjualan"))) -> dict:
    f = db.satu(f"SELECT * FROM ({SQL_FAKTUR}) f WHERE id = %(id)s", {"tgl": db.tanggal_sistem(), "id": faktur_id})
    if not f:
        raise HTTPException(404, "Faktur tidak ditemukan.")
    f["customer_info"] = db.satu("SELECT kode, nama, alamat, kontak, telepon, segmen, termin_hari FROM erp.customer WHERE id = %s",
                                 (f["customer_id"],))
    f["item"] = db.query("""SELECT d.id, p.id AS produk_id, p.kode, p.nama, p.satuan, d.qty, d.harga, d.diskon_persen, d.subtotal
                            FROM erp.faktur_detail d JOIN erp.produk p ON p.id = d.produk_id
                            WHERE d.faktur_id = %s ORDER BY d.id""", (faktur_id,))
    f["bruto"] = sum(i["qty"] * i["harga"] for i in f["item"])
    f["pembayaran"] = (db.query("""SELECT id, tanggal, jumlah, metode, referensi, dibuat_oleh FROM erp.pembayaran
                                   WHERE faktur_id = %s ORDER BY tanggal, id""", (faktur_id,))
                       if punya(u, "piutang") else None)
    f["so"] = db.satu("SELECT id, nomor, dibuat_oleh, tanggal FROM erp.sales_order WHERE id = %s", (f["so_id"],)) if f["so_id"] else None
    f["tahap"] = logika.tahap_penagihan(f["hari_lewat"])
    f["riwayat"] = riwayat.riwayat_faktur(f)
    if not punya(u, "piutang"):
        f["riwayat"] = [e for e in f["riwayat"] if e["jenis"] != "bayar"]
    return f


# ---------------------------------------------------------------------------
# Sales order
# ---------------------------------------------------------------------------
@router.get("/sales-order")
def daftar_so(q: str = "", status: str = "", page: int = 1, size: int = 20, sort: str = "-tanggal",
              u: dict = Depends(wajib("penjualan", "so_buat", "so_setujui_kredit", "so_setujui_diskon", "so_setujui_direksi"))) -> dict:
    where, p = [], {"q": f"%{q.strip()}%"}
    if q.strip():
        where.append("(so.nomor ILIKE %(q)s OR c.nama ILIKE %(q)s)")
    if status == "menunggu":
        where.append("so.status IN ('Ditahan', 'Menunggu Persetujuan')")
    elif status:
        where.append("so.status = %(s)s")
        p["s"] = status
    urut = _urut(sort, {"tanggal": "tanggal", "nomor": "nomor", "customer": "customer", "total": "total"},
                 "tanggal DESC, id DESC")
    sql = f"""SELECT so.id, so.nomor, so.tanggal, so.status, so.total, so.gudang, so.diskon_tambahan, so.persetujuan,
                     so.dibuat_oleh, coalesce(pg.nama, so.dibuat_oleh) AS dibuat_oleh_nama, so.faktur_id, so.sumber,
                     f.nomor AS nomor_faktur, c.id AS customer_id, c.nama AS customer, c.segmen
              FROM erp.sales_order so JOIN erp.customer c ON c.id = so.customer_id
              LEFT JOIN erp.faktur f ON f.id = so.faktur_id
              LEFT JOIN erp.pengguna pg ON pg.kode = so.dibuat_oleh
              {'WHERE ' + ' AND '.join(where) if where else ''}"""
    hasil = halaman(sql, p, page, size, urut)
    hasil["hitung_status"] = db.query("SELECT status, count(*) AS n FROM erp.sales_order GROUP BY status")
    return hasil


@router.get("/sales-order/{so_id}")
def detail_so(so_id: int, u: dict = Depends(wajib("penjualan", "so_buat", "so_setujui_kredit", "so_setujui_diskon",
                                                  "so_setujui_direksi"))) -> dict:
    so = db.satu("""SELECT so.*, coalesce(pg.nama, so.dibuat_oleh) AS dibuat_oleh_nama, f.nomor AS nomor_faktur,
                           c.nama AS customer, c.kode AS kode_customer, c.segmen, c.kota, c.alamat, c.termin_hari
                    FROM erp.sales_order so JOIN erp.customer c ON c.id = so.customer_id
                    LEFT JOIN erp.faktur f ON f.id = so.faktur_id
                    LEFT JOIN erp.pengguna pg ON pg.kode = so.dibuat_oleh WHERE so.id = %s""", (so_id,))
    if not so:
        raise HTTPException(404, "Sales order tidak ditemukan.")
    so["item"] = db.query("""SELECT d.id, p.id AS produk_id, p.kode, p.nama, p.satuan, d.qty, d.harga, d.diskon_persen, d.subtotal,
                                    coalesce(s.qty, 0) AS stok_gudang
                             FROM erp.sales_order_detail d JOIN erp.produk p ON p.id = d.produk_id
                             LEFT JOIN erp.stok s ON s.produk_id = d.produk_id AND s.gudang = %s
                             WHERE d.so_id = %s ORDER BY d.id""", (so["gudang"], so_id))
    so["diskon_standar"] = logika.DISKON_SEGMEN[so["segmen"]]
    with db.koneksi() as conn:
        so["kredit"] = logika.kondisi_kredit(conn, so["customer_id"])
    for p in so["persetujuan"]:
        p["bisa_saya"] = p["status"] == "menunggu" and p["izin"] in u["izin"] and so["status"] in ("Ditahan", "Menunggu Persetujuan")
    so["bisa_batal"] = so["status"] in ("Ditahan", "Menunggu Persetujuan") and (so["dibuat_oleh"] == u["kode"] or punya(u, "so_setujui_diskon"))
    so["riwayat"] = riwayat.riwayat_so(so)
    so["faktur"] = None
    if so["faktur_id"]:
        so["faktur"] = db.satu(f"SELECT id, nomor, tanggal, jatuh_tempo, total, terbayar, sisa, status FROM ({SQL_FAKTUR}) f WHERE id = %(id)s",
                               {"tgl": db.tanggal_sistem(), "id": so["faktur_id"]})
        if not punya(u, "piutang"):
            so["riwayat"] = [e for e in so["riwayat"] if e["jenis"] != "bayar"]
    return so


class ItemSO(BaseModel):
    produk_id: int
    qty: int = Field(gt=0)


class SOBaru(BaseModel):
    customer_id: int
    tanggal: dt.date
    gudang: str
    diskon_tambahan: float = 0
    catatan: str = ""
    item: list[ItemSO]
    # "asisten_ai": draft disiapkan Asisten AI, user memeriksa lalu menekan Simpan sendiri (sesi & izin user)
    sumber: Literal["manual", "asisten_ai"] = "manual"


@router.post("/sales-order/simulasi")
def simulasi_so(data: SOBaru, u: dict = Depends(wajib("so_buat"))) -> dict:
    """Pratinjau harga, diskon, kondisi kredit, dan persetujuan yang dibutuhkan, tanpa menyimpan."""
    with db.koneksi() as conn:
        kredit = logika.kondisi_kredit(conn, data.customer_id)
        try:
            hitungan = logika.hitung_so(conn, data.customer_id, [i.model_dump() for i in data.item], data.diskon_tambahan) \
                if data.item else None
            status, perlu, peringatan = logika.evaluasi_so(conn, data.customer_id, hitungan) if hitungan else ("", [], [])
            galat = None
            if hitungan:
                try:
                    logika.cek_stok(conn, data.gudang, hitungan["item"])
                except logika.AturanBisnis as e:
                    galat = str(e)
        except logika.AturanBisnis as e:
            hitungan, status, perlu, peringatan, galat = None, "", [], [], str(e)
        stok = {r["produk_id"]: r["qty"] for r in conn.execute(
            "SELECT produk_id, qty FROM erp.stok WHERE gudang = %s", (data.gudang,)).fetchall()}
    return {"kredit": kredit, "hitungan": hitungan, "status": status, "persetujuan": perlu,
            "peringatan": peringatan, "galat": galat, "stok": stok}


@router.post("/sales-order")
def buat_so(data: SOBaru, u: dict = Depends(wajib("so_buat"))) -> dict:
    try:
        with db.koneksi() as conn:
            return logika.buat_so(conn, {**data.model_dump(), "item": [i.model_dump() for i in data.item]}, u["kode"])
    except logika.AturanBisnis as e:
        raise HTTPException(422, str(e)) from e


class Keputusan(BaseModel):
    jenis: str
    setuju: bool
    catatan: str = ""


@router.post("/sales-order/{so_id}/keputusan")
def putuskan(so_id: int, data: Keputusan,
             u: dict = Depends(wajib("so_setujui_kredit", "so_setujui_diskon", "so_setujui_direksi"))) -> dict:
    try:
        with db.koneksi() as conn:
            return logika.putuskan_so(conn, so_id, data.jenis, data.setuju, data.catatan, u)
    except logika.AturanBisnis as e:
        raise HTTPException(422, str(e)) from e


class Batal(BaseModel):
    alasan: str


@router.post("/sales-order/{so_id}/batal")
def batal(so_id: int, data: Batal, u: dict = Depends(wajib("so_buat", "so_setujui_diskon"))) -> dict:
    try:
        with db.koneksi() as conn:
            logika.batalkan_so(conn, so_id, data.alasan, u)
    except logika.AturanBisnis as e:
        raise HTTPException(422, str(e)) from e
    return {"ok": True}


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
@router.get("/customer")
def daftar_customer(q: str = "", segmen: str = "", kota: str = "", page: int = 1, size: int = 20, sort: str = "nama",
                    u: dict = Depends(wajib("penjualan", "so_buat"))) -> dict:
    akhir = db.tanggal_sistem().replace(day=1)
    where, p = [], {"q": f"%{q.strip()}%", "awal": tambah_bulan(akhir, -11), "akhir": akhir}
    if q.strip():
        where.append("(c.nama ILIKE %(q)s OR c.kode ILIKE %(q)s)")
    if segmen:
        where.append("c.segmen = %(segmen)s")
        p["segmen"] = segmen
    if kota:
        where.append("c.kota = %(kota)s")
        p["kota"] = kota
    lihat_piutang = punya(u, "piutang")
    sql = f"""SELECT c.id, c.kode, c.nama, c.kota, c.segmen, c.termin_hari, c.limit_kredit, c.kontak, c.aktif,
                     coalesce(j.omzet, 0) AS omzet_12_bulan, j.faktur_terakhir,
                     {'coalesce(pi.piutang, 0)' if lihat_piutang else 'NULL::numeric'} AS piutang,
                     {'coalesce(pi.hari, 0)' if lihat_piutang else 'NULL::int'} AS hari_lewat
              FROM erp.customer c
              LEFT JOIN (SELECT customer_id, sum(nilai) AS omzet, max(tanggal) AS faktur_terakhir FROM ai.v_penjualan
                         WHERE bulan BETWEEN %(awal)s AND %(akhir)s GROUP BY customer_id) j ON j.customer_id = c.id
              LEFT JOIN (SELECT customer_id, sum(sisa) AS piutang, max(hari_lewat_jatuh_tempo) AS hari FROM ai.v_piutang
                         GROUP BY customer_id) pi ON pi.customer_id = c.id
              {'WHERE ' + ' AND '.join(where) if where else ''}"""
    urut = _urut(sort, {"nama": "nama", "kode": "kode", "omzet": "omzet_12_bulan", "piutang": "piutang",
                        "kota": "kota", "segmen": "segmen"}, "nama ASC")
    return halaman(sql, p, page, size, urut)


@router.get("/customer/{customer_id}")
def detail_customer(customer_id: int, u: dict = Depends(wajib("penjualan", "so_buat"))) -> dict:
    c = db.satu("SELECT * FROM erp.customer WHERE id = %s", (customer_id,))
    if not c:
        raise HTTPException(404, "Customer tidak ditemukan.")
    akhir = db.tanggal_sistem().replace(day=1)
    awal = tambah_bulan(akhir, -11)
    c["omzet_bulanan"] = db.query("""SELECT bulan, sum(nilai) AS nilai, sum(qty) AS qty FROM ai.v_penjualan
                                     WHERE customer_id = %s AND bulan BETWEEN %s AND %s GROUP BY bulan ORDER BY bulan""",
                                  (customer_id, awal, akhir))
    c["produk_favorit"] = db.query("""SELECT produk_id AS id, produk, kategori, sum(qty) AS qty, sum(nilai) AS nilai
                                      FROM ai.v_penjualan WHERE customer_id = %s AND bulan BETWEEN %s AND %s
                                      GROUP BY produk_id, produk, kategori ORDER BY nilai DESC LIMIT 6""",
                                   (customer_id, awal, akhir))
    c["faktur_terakhir"] = db.query(f"SELECT * FROM ({SQL_FAKTUR}) f WHERE customer_id = %(c)s ORDER BY tanggal DESC, id DESC LIMIT 10",
                                    {"tgl": db.tanggal_sistem(), "c": customer_id})
    if punya(u, "piutang"):
        with db.koneksi() as conn:
            c["kredit"] = logika.kondisi_kredit(conn, customer_id)
        c["faktur_terbuka"] = db.query("""SELECT faktur_id AS id, nomor_faktur AS nomor, tanggal, jatuh_tempo, total, sisa,
                                                 hari_lewat_jatuh_tempo AS hari FROM ai.v_piutang
                                          WHERE customer_id = %s ORDER BY jatuh_tempo""", (customer_id,))
    else:
        c["kredit"] = None
        c["faktur_terbuka"] = None
    c["so_menunggu"] = db.query("""SELECT id, nomor, tanggal, status, total FROM erp.sales_order
                                   WHERE customer_id = %s AND status IN ('Ditahan', 'Menunggu Persetujuan') ORDER BY id DESC""",
                                (customer_id,))
    c["diskon_standar"] = logika.DISKON_SEGMEN[c["segmen"]]
    return c


class CustomerData(BaseModel):
    nama: str = Field(min_length=3)
    kota: str
    segmen: str
    alamat: str = ""
    kontak: str = ""
    telepon: str = ""
    limit_kredit: float | None = None
    aktif: bool = True


@router.post("/customer")
def tambah_customer(data: CustomerData, u: dict = Depends(wajib("customer_kelola"))) -> dict:
    if data.segmen not in logika.DISKON_SEGMEN:
        raise HTTPException(422, "Segmen tidak dikenal.")
    limit = logika.LIMIT_SEGMEN[data.segmen]
    if data.limit_kredit is not None and data.limit_kredit != limit and not punya(u, "limit_kredit"):
        raise HTTPException(403, "Limit kredit awal mengikuti segmen. Perubahan limit disetujui Divisi Finance.")
    with db.koneksi() as conn:
        nid = conn.execute("SELECT nextval(pg_get_serial_sequence('erp.customer', 'id')) AS id").fetchone()["id"]
        kode = f"CUS-{nid:03d}"
        conn.execute("""INSERT INTO erp.customer (id, kode, nama, kota, segmen, termin_hari, limit_kredit, alamat, kontak, telepon, aktif)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                     (nid, kode, data.nama.strip(), data.kota, data.segmen, logika.TERMIN_SEGMEN[data.segmen],
                      data.limit_kredit if data.limit_kredit is not None else limit, data.alamat, data.kontak,
                      data.telepon, data.aktif))
        db.catat_audit(conn, u["kode"], "Penjualan", "Menambah customer", kode, data.nama.strip())
    return {"id": nid, "kode": kode}


@router.put("/customer/{customer_id}")
def ubah_customer(customer_id: int, data: CustomerData, u: dict = Depends(wajib("customer_kelola", "limit_kredit"))) -> dict:
    lama = db.satu("SELECT * FROM erp.customer WHERE id = %s", (customer_id,))
    if not lama:
        raise HTTPException(404, "Customer tidak ditemukan.")
    if data.segmen not in logika.DISKON_SEGMEN:
        raise HTTPException(422, "Segmen tidak dikenal.")
    limit = float(lama["limit_kredit"]) if data.limit_kredit is None else data.limit_kredit
    if limit != float(lama["limit_kredit"]) and not punya(u, "limit_kredit"):
        raise HTTPException(403, "Perubahan limit kredit hanya dapat dilakukan Divisi Finance.")
    profil_berubah = data.aktif != lama["aktif"] or any(
        (getattr(data, k) or "") != (lama[k] or "") for k in ("nama", "kota", "segmen", "alamat", "kontak", "telepon"))
    if profil_berubah and not punya(u, "customer_kelola"):
        raise HTTPException(403, "Anda hanya dapat mengubah limit kredit.")
    termin = logika.TERMIN_SEGMEN[data.segmen] if data.segmen != lama["segmen"] else lama["termin_hari"]
    with db.koneksi() as conn:
        conn.execute("""UPDATE erp.customer SET nama = %s, kota = %s, segmen = %s, termin_hari = %s, limit_kredit = %s,
                               alamat = %s, kontak = %s, telepon = %s, aktif = %s WHERE id = %s""",
                     (data.nama.strip(), data.kota, data.segmen, termin, limit, data.alamat, data.kontak, data.telepon,
                      data.aktif, customer_id))
        ket = []
        if limit != float(lama["limit_kredit"]):
            ket.append(f"limit {logika.rp(float(lama['limit_kredit']))} → {logika.rp(limit)}")
        if data.segmen != lama["segmen"]:
            ket.append(f"segmen {lama['segmen']} → {data.segmen}")
        db.catat_audit(conn, u["kode"], "Penjualan", "Mengubah customer", lama["kode"], "; ".join(ket) or "profil")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Laporan penjualan
# ---------------------------------------------------------------------------
DIMENSI = {"produk": "produk", "customer": "customer", "kota": "kota", "segmen": "segmen", "kategori": "kategori"}


@router.get("/laporan/penjualan")
def laporan_penjualan(dimensi: str = "produk", bulan: int = 6, u: dict = Depends(wajib("penjualan"))) -> dict:
    kol = DIMENSI.get(dimensi)
    if not kol:
        raise HTTPException(422, "Dimensi tidak dikenal.")
    bulan = max(1, min(bulan, 18))
    akhir = db.tanggal_sistem().replace(day=1)
    awal = tambah_bulan(akhir, -(bulan - 1))
    tengah = tambah_bulan(akhir, -(bulan // 2 - 1)) if bulan > 1 else akhir  # awal paruh kedua
    baris = db.query(f"""SELECT {kol} AS nama, sum(qty) AS qty, sum(nilai) AS nilai, count(DISTINCT nomor_faktur) AS faktur,
                                sum(nilai) FILTER (WHERE bulan < %(t)s) AS nilai_awal,
                                sum(nilai) FILTER (WHERE bulan >= %(t)s) AS nilai_akhir
                         FROM ai.v_penjualan WHERE bulan BETWEEN %(a)s AND %(b)s
                         GROUP BY {kol} ORDER BY nilai DESC""", {"a": awal, "b": akhir, "t": tengah})
    total = sum(b["nilai"] for b in baris) or 1
    n_akhir = bulan // 2
    n_awal = bulan - n_akhir
    for b in baris:
        b["porsi"] = round(b["nilai"] / total * 100, 1)
        # rata-rata per bulan tiap paruh periode, supaya paruh yang jumlah bulannya beda tetap sebanding
        b["nilai_awal"] = (b["nilai_awal"] or 0) / n_awal if n_akhir else None
        b["nilai_akhir"] = (b["nilai_akhir"] or 0) / n_akhir if n_akhir else None
    seri = db.query(f"""SELECT bulan, {kol} AS nama, sum(nilai) AS nilai FROM ai.v_penjualan
                        WHERE bulan BETWEEN %s AND %s AND {kol} = ANY(%s) GROUP BY bulan, {kol} ORDER BY bulan""",
                    (awal, akhir, [b["nama"] for b in baris[:5]]))
    return {"awal": awal.isoformat(), "akhir": akhir.isoformat(), "dimensi": dimensi, "baris": baris, "seri": seri,
            "total": total}
