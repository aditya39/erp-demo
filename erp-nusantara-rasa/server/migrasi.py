"""
Migrasi & data awal ERP (idempoten). Dijalankan otomatis oleh `python -m server`.

  python -m server.migrasi           # jalankan manual

Mengembalikan data ke kondisi awal (mis. setelah gladi): lihat scripts/reset-data.sh.

Data tambahan yang diisi sekali:
  - pengguna contoh (password demo: demo123)
  - alamat & kontak customer (dummy)
  - riwayat sales order untuk setiap faktur yang sudah ada
  - mutasi stok bulan berjalan, log aktivitas, dan 2 sales order yang menunggu persetujuan
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from . import config, izin, keamanan, logika

JALAN = ["Jl. Raya Industri", "Jl. Gatot Subroto", "Jl. Ahmad Yani", "Jl. Diponegoro", "Jl. Sudirman",
         "Jl. Pahlawan", "Jl. Merdeka", "Jl. Pemuda", "Jl. Veteran", "Jl. Hayam Wuruk", "Jl. Gajah Mada",
         "Jl. Pasar Baru", "Jl. Kenanga", "Jl. Melati", "Jl. Cendana", "Jl. Mangga Dua"]
NAMA_PIC = ["Hendra", "Yuliana", "Rahmat", "Fitriani", "Bambang", "Lina", "Taufik", "Wulan", "Arif", "Ratna",
            "Doni", "Sinta", "Eko", "Nurul", "Fajar", "Indah", "Gilang", "Mega", "Rizky", "Putri"]
KODE_AREA = {"Jakarta": "021", "Bandung": "022", "Surabaya": "031", "Semarang": "024", "Medan": "061",
             "Makassar": "0411", "Denpasar": "0361", "Yogyakarta": "0274"}


def _gudang_untuk(kota: str) -> str:
    return "Gudang Surabaya" if kota in ("Surabaya", "Denpasar", "Makassar") else "Gudang Jakarta"


def _setel_password_app(conn: psycopg.Connection) -> None:
    """
    Password role erp_app mengikuti ERP_DATABASE_URL (ERP_APP_PASSWORD di .env), disetel ulang setiap start.
    Jadi mengganti password cukup: ubah .env lalu `docker compose up -d erp`. Nilai di-quote oleh psycopg.
    """
    info = conninfo_to_dict(config.ERP_DATABASE_URL)
    if info.get("user") == "erp_app" and info.get("password"):
        conn.execute(sql.SQL("ALTER ROLE erp_app PASSWORD {}").format(sql.Literal(info["password"])))


def jalankan(diam: bool = False) -> None:
    log = (lambda *_: None) if diam else print
    with psycopg.connect(config.ERP_DATABASE_URL_ADMIN, row_factory=dict_row, connect_timeout=5) as conn:
        conn.execute(Path(__file__).with_name("migrasi.sql").read_text(encoding="utf-8"))
        _setel_password_app(conn)
        conn.commit()   # role erp_app harus sudah ada sebelum logika bisnis (koneksi erp_app) dipakai

        # --- pengguna -------------------------------------------------------
        for kode, nama, jabatan, divisi, hak in izin.PENGGUNA_AWAL:
            conn.execute(
                """INSERT INTO erp.pengguna (kode, nama, jabatan, divisi, email, password_hash, izin)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (kode) DO NOTHING""",
                (kode, nama, jabatan, divisi, f"{kode}@nusantararasa.local",
                 keamanan.hash_password(izin.PASSWORD_DEMO), list(hak)))

        # --- kontak customer ------------------------------------------------
        rng = random.Random(7)
        for c in conn.execute("SELECT id, kota FROM erp.customer WHERE alamat IS NULL ORDER BY id").fetchall():
            conn.execute(
                "UPDATE erp.customer SET alamat = %s, kontak = %s, telepon = %s WHERE id = %s",
                (f"{rng.choice(JALAN)} No. {rng.randint(1, 180)}, {c['kota']}",
                 f"{rng.choice(NAMA_PIC)} ({rng.choice(['Purchasing', 'Pemilik', 'Manajer Pembelian', 'Admin Gudang'])})",
                 f"({KODE_AREA.get(c['kota'], '021')}) 0000-{rng.randint(1000, 9999)}", c["id"]))

        sudah = conn.execute("SELECT count(*) AS n FROM erp.sales_order").fetchone()["n"]
        if sudah:
            log("Migrasi ERP: struktur diperbarui, data awal sudah ada.")
            conn.commit()
            return

        # --- riwayat SO dari faktur yang ada ----------------------------------
        conn.execute("""UPDATE erp.faktur f SET gudang = CASE WHEN c.kota IN ('Surabaya','Denpasar','Makassar')
                                                      THEN 'Gudang Surabaya' ELSE 'Gudang Jakarta' END,
                                                 so_id = f.id,
                                                 dibuat_oleh = 'migrasi'
                        FROM erp.customer c WHERE c.id = f.customer_id AND f.so_id IS NULL""")
        conn.execute("""INSERT INTO erp.sales_order (id, nomor, tanggal, customer_id, gudang, diskon_tambahan, status,
                                                     total, faktur_id, dibuat_oleh, dibuat_pada)
                        SELECT f.id, 'SO/' || to_char(f.tanggal, 'YYYY/MM') || '/' || lpad(f.id::text, 5, '0'),
                               f.tanggal, f.customer_id, f.gudang, 0, 'Faktur Terbit', f.total, f.id,
                               CASE WHEN f.id % 4 = 0 THEN 'dewi' ELSE 'andi' END,
                               (f.tanggal + time '08:30' + (f.id % 480) * interval '1 minute') AT TIME ZONE 'Asia/Jakarta'
                        FROM erp.faktur f ORDER BY f.id""")
        conn.execute("""INSERT INTO erp.sales_order_detail (so_id, produk_id, qty, harga, diskon_persen, subtotal)
                        SELECT faktur_id, produk_id, qty, harga, diskon_persen, subtotal
                        FROM erp.faktur_detail ORDER BY id""")
        conn.execute("SELECT setval(pg_get_serial_sequence('erp.sales_order', 'id'), (SELECT max(id) FROM erp.sales_order))")
        conn.execute("""UPDATE erp.pembayaran SET metode = CASE WHEN id % 9 = 0 THEN 'Giro' ELSE 'Transfer Bank' END,
                                                  referensi = CASE WHEN id % 9 = 0 THEN 'GR-' ELSE 'TRF-' END
                                                              || to_char(tanggal, 'YYMMDD') || '-' || lpad((id % 997)::text, 3, '0'),
                                                  dibuat_oleh = 'migrasi'
                        WHERE metode IS NULL""")

        # --- mutasi stok bulan berjalan ----------------------------------------
        posisi = conn.execute("SELECT nilai::date AS t FROM erp.parameter WHERE kunci = 'tanggal_posisi'").fetchone()["t"]
        awal = posisi.replace(day=1)
        conn.execute("""INSERT INTO erp.mutasi_stok (tanggal, produk_id, gudang, jenis, qty, referensi, keterangan, pengguna, dibuat_pada)
                        SELECT f.tanggal, d.produk_id, f.gudang, 'Penjualan', -d.qty, f.nomor, c.nama, 'andi',
                               (f.tanggal + time '10:00') AT TIME ZONE 'Asia/Jakarta'
                        FROM erp.faktur_detail d JOIN erp.faktur f ON f.id = d.faktur_id
                        JOIN erp.customer c ON c.id = f.customer_id
                        WHERE f.tanggal >= %s ORDER BY f.tanggal, f.id, d.id""", (awal,))
        for minggu, hari in enumerate((2, 9, 16, 23), start=1):
            conn.execute("""INSERT INTO erp.mutasi_stok (tanggal, produk_id, gudang, jenis, qty, referensi, keterangan, pengguna, dibuat_pada)
                            SELECT %(t)s, b.produk_id, g.gudang, 'Produksi', round(b.unit_diproduksi * g.porsi / 4),
                                   'PRD/' || to_char(%(t)s::date, 'YYYY/MM') || '/' || %(m)s || '-' || p.kode,
                                   'Hasil produksi minggu ke-' || %(m)s, 'agus', (%(t)s::date + time '16:00') AT TIME ZONE 'Asia/Jakarta'
                            FROM erp.biaya_produksi b JOIN erp.produk p ON p.id = b.produk_id
                            CROSS JOIN (VALUES ('Gudang Jakarta', 0.55), ('Gudang Surabaya', 0.45)) g(gudang, porsi)
                            WHERE b.bulan = %(a)s""", {"t": awal.replace(day=hari), "m": minggu, "a": awal})

        # --- log aktivitas dari riwayat bulan berjalan ----------------------------
        conn.execute("""INSERT INTO erp.audit_log (waktu, pengguna, modul, aksi, objek, keterangan)
                        SELECT so.dibuat_pada, so.dibuat_oleh, 'Penjualan', 'Membuat sales order', so.nomor,
                               c.nama || ' · Rp ' || replace(to_char(so.total, 'FM999G999G999G999'), ',', '.')
                        FROM erp.sales_order so JOIN erp.customer c ON c.id = so.customer_id
                        WHERE so.tanggal >= %s""", (awal,))
        conn.execute("""INSERT INTO erp.audit_log (waktu, pengguna, modul, aksi, objek, keterangan)
                        SELECT (p.tanggal + time '14:00' + (p.id %% 120) * interval '1 minute') AT TIME ZONE 'Asia/Jakarta',
                               'sari', 'Keuangan', 'Mencatat pembayaran', c.nama,
                               'Rp ' || replace(to_char(p.jumlah, 'FM999G999G999G999'), ',', '.') || ' · ' || p.metode
                        FROM erp.pembayaran p JOIN erp.faktur f ON f.id = p.faktur_id
                        JOIN erp.customer c ON c.id = f.customer_id
                        WHERE p.tanggal >= %s""", (awal,))

        # --- 2 SO yang menunggu persetujuan (bahan demo) -------------------------
        def produk(kode: str) -> int:
            return conn.execute("SELECT id FROM erp.produk WHERE kode = %s", (kode,)).fetchone()["id"]

        def cust(nama: str) -> dict:
            return conn.execute("SELECT id, kota FROM erp.customer WHERE nama = %s", (nama,)).fetchone()

        laju = cust("CV Laju Makmur Abadi")
        contoh = [
            ("andi", {"customer_id": laju["id"], "gudang": _gudang_untuk(laju["kota"]), "tanggal": posisi,
                      "diskon_tambahan": 0, "catatan": "Order rutin akhir bulan",
                      "item": [{"produk_id": produk("BSK-002"), "qty": 900}, {"produk_id": produk("BSK-003"), "qty": 700},
                               {"produk_id": produk("MNM-001"), "qty": 1600}]}),
        ]
        # customer Retail Modern tanpa tunggakan > 30 hari untuk contoh diskon tambahan 2%
        rm = conn.execute("""SELECT c.id, c.kota FROM erp.customer c
                             WHERE c.segmen = 'Retail Modern' AND c.kota = 'Jakarta'
                               AND NOT EXISTS (SELECT 1 FROM ai.v_piutang p WHERE p.customer_id = c.id
                                               AND p.hari_lewat_jatuh_tempo > 0)
                             ORDER BY c.id LIMIT 1""").fetchone()
        if rm:
            contoh.append(("andi", {"customer_id": rm["id"], "gudang": _gudang_untuk(rm["kota"]), "tanggal": posisi,
                                    "diskon_tambahan": 2.0, "catatan": "Program display akhir bulan (gondola depan kasir)",
                                    "item": [{"produk_id": produk("BSK-001"), "qty": 400},
                                             {"produk_id": produk("BSK-003"), "qty": 300},
                                             {"produk_id": produk("MNM-002"), "qty": 600}]}))
        for oleh, data in contoh:
            try:
                hasil = logika.buat_so(conn, data, oleh)
                log(f"  contoh {hasil['nomor']}: {hasil['status']}")
            except logika.AturanBisnis as e:
                log(f"  contoh SO dilewati: {e}")
        conn.execute("""UPDATE erp.audit_log SET waktu = (%s::date + time '16:45') AT TIME ZONE 'Asia/Jakarta'
                        WHERE waktu > now() - interval '1 minute'""", (posisi,))
        conn.execute("""UPDATE erp.sales_order SET dibuat_pada = (%s::date + time '16:40') AT TIME ZONE 'Asia/Jakarta'
                        WHERE status IN ('Ditahan', 'Menunggu Persetujuan')""", (posisi,))
        conn.commit()
        n = conn.execute("SELECT count(*) AS n FROM erp.sales_order").fetchone()["n"]
        log(f"Migrasi ERP selesai: {n} sales order, {len(izin.PENGGUNA_AWAL)} pengguna (password demo: {izin.PASSWORD_DEMO}).")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    jalankan()
