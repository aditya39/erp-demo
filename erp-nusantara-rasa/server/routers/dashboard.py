"""Dashboard: isi kartu dan grafik mengikuti hak akses user."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends

from .. import db
from ..sesi import pengguna_login, punya

router = APIRouter(prefix="/api")


def tambah_bulan(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def ubah(awal: float, akhir: float) -> float | None:
    return round((akhir - awal) / awal * 100, 1) if awal else None


@router.get("/dashboard")
def dashboard(u: dict = Depends(pengguna_login)) -> dict:
    akhir = db.tanggal_sistem().replace(day=1)
    lalu = tambah_bulan(akhir, -1)
    awal12 = tambah_bulan(akhir, -11)
    hasil: dict = {"bulan": akhir.isoformat(), "bulan_lalu": lalu.isoformat(), "kartu": [], "terkunci": []}

    if punya(u, "penjualan"):
        bulanan = db.query("""SELECT bulan, sum(nilai) AS nilai, sum(qty) AS qty, count(DISTINCT nomor_faktur) AS faktur,
                                     count(DISTINCT customer_id) AS customer
                              FROM ai.v_penjualan WHERE bulan BETWEEN %s AND %s GROUP BY bulan ORDER BY bulan""",
                           (awal12, akhir))
        per = {b["bulan"]: b for b in bulanan}
        kini, sebelum = per.get(akhir.isoformat(), {}), per.get(lalu.isoformat(), {})
        hasil["omzet_bulanan"] = bulanan
        hasil["kartu"] += [
            {"kode": "omzet", "label": "Omzet bulan ini", "nilai": kini.get("nilai", 0), "format": "rupiah",
             "ubah": ubah(sebelum.get("nilai", 0), kini.get("nilai", 0)), "seri": [b["nilai"] for b in bulanan[-6:]]},
            {"kode": "faktur", "label": "Faktur terbit", "nilai": kini.get("faktur", 0), "format": "angka",
             "ubah": ubah(sebelum.get("faktur", 0), kini.get("faktur", 0)), "sub": f"{kini.get('customer', 0)} customer aktif"},
        ]
        hasil["kategori"] = db.query("""SELECT kategori, sum(nilai) AS nilai FROM ai.v_penjualan WHERE bulan = %s
                                        GROUP BY kategori ORDER BY nilai DESC""", (akhir,))
        hasil["produk_teratas"] = db.query(
            """SELECT produk_id AS id, produk, kategori,
                      sum(qty) FILTER (WHERE bulan = %(b)s) AS qty, sum(nilai) FILTER (WHERE bulan = %(b)s) AS nilai,
                      sum(qty) FILTER (WHERE bulan = %(l)s) AS qty_lalu
               FROM ai.v_penjualan WHERE bulan IN (%(b)s, %(l)s)
               GROUP BY produk_id, produk, kategori ORDER BY nilai DESC NULLS LAST LIMIT 6""", {"b": akhir, "l": lalu})
        for p in hasil["produk_teratas"]:
            p["ubah"] = ubah(p["qty_lalu"] or 0, p["qty"] or 0)
        hasil["customer_teratas"] = db.query(
            """SELECT customer_id AS id, customer, segmen, kota, sum(nilai) AS nilai FROM ai.v_penjualan
               WHERE bulan = %s GROUP BY customer_id, customer, segmen, kota ORDER BY nilai DESC LIMIT 5""", (akhir,))
    else:
        hasil["terkunci"] += ["omzet", "faktur"]

    if punya(u, "piutang"):
        aging = db.satu("""SELECT coalesce(sum(sisa) FILTER (WHERE hari_lewat_jatuh_tempo = 0), 0) AS b0,
                                  coalesce(sum(sisa) FILTER (WHERE hari_lewat_jatuh_tempo BETWEEN 1 AND 30), 0) AS b1,
                                  coalesce(sum(sisa) FILTER (WHERE hari_lewat_jatuh_tempo BETWEEN 31 AND 60), 0) AS b2,
                                  coalesce(sum(sisa) FILTER (WHERE hari_lewat_jatuh_tempo BETWEEN 61 AND 90), 0) AS b3,
                                  coalesce(sum(sisa) FILTER (WHERE hari_lewat_jatuh_tempo > 90), 0) AS b4,
                                  coalesce(sum(sisa), 0) AS total,
                                  count(*) FILTER (WHERE hari_lewat_jatuh_tempo > 0) AS faktur_lewat
                           FROM ai.v_piutang""")
        hasil["aging"] = aging
        lewat = aging["b1"] + aging["b2"] + aging["b3"] + aging["b4"]
        hasil["kartu"].append({"kode": "piutang", "label": "Piutang lewat jatuh tempo", "nilai": lewat, "format": "rupiah",
                               "sub": f"{aging['faktur_lewat']} faktur · total piutang", "sub_nilai": aging["total"]})
        hasil["penunggak"] = db.query(
            """SELECT customer_id AS id, customer, segmen, sum(sisa) AS sisa, max(hari_lewat_jatuh_tempo) AS hari
               FROM ai.v_piutang WHERE hari_lewat_jatuh_tempo > 60
               GROUP BY customer_id, customer, segmen ORDER BY sisa DESC LIMIT 5""")
    else:
        hasil["terkunci"].append("piutang")

    if punya(u, "stok"):
        menipis = db.query("""SELECT p.id, p.kode, p.nama, s.gudang, s.qty, s.stok_minimum FROM erp.stok s
                              JOIN erp.produk p ON p.id = s.produk_id WHERE s.qty < s.stok_minimum
                              ORDER BY s.qty::float / nullif(s.stok_minimum, 0)""")
        hasil["stok_menipis"] = menipis
        hasil["kartu"].append({"kode": "stok", "label": "Stok di bawah minimum", "nilai": len(menipis), "format": "angka",
                               "sub": "produk × gudang"})
    else:
        hasil["terkunci"].append("stok")

    if punya(u, "hpp"):
        hpp = db.query("""WITH h AS (SELECT produk_id, produk, bulan, hpp_per_unit,
                                     lag(hpp_per_unit) OVER (PARTITION BY produk_id ORDER BY bulan) AS lalu
                                     FROM ai.v_hpp_bulanan)
                          SELECT produk_id AS id, produk, hpp_per_unit, lalu,
                                 round((hpp_per_unit - lalu) / lalu * 100, 1) AS ubah
                          FROM h WHERE bulan = %s ORDER BY ubah DESC""", (akhir,))
        hasil["hpp_naik"] = [h for h in hpp if (h["ubah"] or 0) > 8]
        if not punya(u, "penjualan"):
            hasil["kartu"].append({"kode": "hpp", "label": "HPP naik > 8%", "nilai": len(hasil["hpp_naik"]),
                                   "format": "angka", "sub": "produk bulan ini"})

    so = db.query("""SELECT so.id, so.nomor, so.status, so.total, so.persetujuan, c.nama AS customer
                     FROM erp.sales_order so JOIN erp.customer c ON c.id = so.customer_id
                     WHERE so.status IN ('Ditahan', 'Menunggu Persetujuan') ORDER BY so.id DESC""")
    hasil["so_menunggu"] = [
        {**{k: v for k, v in r.items() if k != "persetujuan"},
         "perlu": [p for p in r["persetujuan"] if p["status"] == "menunggu"],
         "bisa_saya": any(p["status"] == "menunggu" and p["izin"] in u["izin"] for p in r["persetujuan"])}
        for r in so] if (punya(u, "penjualan") or any(i.startswith("so_setujui") for i in u["izin"])) else []

    filter_aktivitas = "" if punya(u, "pengaturan") or u["divisi"] == "Direksi" else "WHERE a.pengguna = %(k)s"
    hasil["aktivitas"] = db.query(
        f"""SELECT a.waktu, a.pengguna, coalesce(p.nama, a.pengguna) AS nama, a.modul, a.aksi, a.objek, a.keterangan
            FROM erp.audit_log a LEFT JOIN erp.pengguna p ON p.kode = a.pengguna
            {filter_aktivitas} ORDER BY a.waktu DESC, a.id DESC LIMIT 8""", {"k": u["kode"]})
    return hasil
