-- =====================================================================
-- Lapisan akses untuk asisten AI
--
-- Prinsip:
--   1. Asisten AI TIDAK membaca tabel erp.* secara langsung, hanya view
--      di schema "ai" yang sudah dipilih kolomnya.
--   2. Asisten AI memakai role database terpisah yang hanya bisa SELECT
--      (read-only) dan punya batas waktu query.
--   3. Data sensitif (mis. erp.gaji_karyawan) tidak punya view sama sekali.
-- =====================================================================

-- ---------------------------------------------------------------------
-- View
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW ai.v_info AS
SELECT
    (SELECT nilai FROM erp.parameter WHERE kunci = 'nama_perusahaan')      AS nama_perusahaan,
    (SELECT nilai::date FROM erp.parameter WHERE kunci = 'tanggal_posisi') AS tanggal_posisi;

CREATE OR REPLACE VIEW ai.v_produk AS
SELECT p.id, p.kode, p.nama, k.nama AS kategori, p.satuan, p.harga_jual
FROM erp.produk p
JOIN erp.kategori k ON k.id = p.kategori_id
WHERE p.aktif;

CREATE OR REPLACE VIEW ai.v_customer AS
SELECT id, kode, nama, kota, segmen, termin_hari
FROM erp.customer;

CREATE OR REPLACE VIEW ai.v_penjualan AS
SELECT f.tanggal,
       date_trunc('month', f.tanggal)::date AS bulan,
       f.nomor        AS nomor_faktur,
       c.id           AS customer_id,
       c.nama         AS customer,
       c.kota,
       c.segmen,
       p.id           AS produk_id,
       p.kode         AS kode_produk,
       p.nama         AS produk,
       k.nama         AS kategori,
       d.qty,
       d.harga,
       d.diskon_persen,
       d.subtotal     AS nilai
FROM erp.faktur_detail d
JOIN erp.faktur f    ON f.id = d.faktur_id
JOIN erp.customer c  ON c.id = f.customer_id
JOIN erp.produk p    ON p.id = d.produk_id
JOIN erp.kategori k  ON k.id = p.kategori_id;

CREATE OR REPLACE VIEW ai.v_harga_bahan AS
SELECT hb.bulan, b.id AS bahan_id, b.kode, b.nama AS bahan, b.satuan, hb.harga
FROM erp.harga_bahan hb
JOIN erp.bahan_baku b ON b.id = hb.bahan_id;

-- Rincian biaya bahan per unit produk per bulan
CREATE OR REPLACE VIEW ai.v_hpp_komponen AS
SELECT bp.bulan,
       p.id   AS produk_id,
       p.nama AS produk,
       b.id   AS bahan_id,
       b.nama AS bahan,
       b.satuan,
       r.qty_per_unit,
       hb.harga                         AS harga_bahan,
       round(r.qty_per_unit * hb.harga, 2) AS biaya_per_unit
FROM erp.biaya_produksi bp
JOIN erp.produk p       ON p.id = bp.produk_id
JOIN erp.resep r        ON r.produk_id = p.id
JOIN erp.bahan_baku b   ON b.id = r.bahan_id
JOIN erp.harga_bahan hb ON hb.bahan_id = b.id AND hb.bulan = bp.bulan;

-- HPP per unit = bahan baku + tenaga kerja + overhead
CREATE OR REPLACE VIEW ai.v_hpp_bulanan AS
SELECT bp.bulan,
       p.id   AS produk_id,
       p.kode AS kode_produk,
       p.nama AS produk,
       bp.unit_diproduksi,
       k.bahan_baku_per_unit,
       bp.tenaga_kerja_per_unit,
       bp.overhead_per_unit,
       round(k.bahan_baku_per_unit + bp.tenaga_kerja_per_unit + bp.overhead_per_unit, 2) AS hpp_per_unit
FROM erp.biaya_produksi bp
JOIN erp.produk p ON p.id = bp.produk_id
JOIN (
    SELECT produk_id, bulan, sum(biaya_per_unit) AS bahan_baku_per_unit
    FROM ai.v_hpp_komponen
    GROUP BY produk_id, bulan
) k ON k.produk_id = bp.produk_id AND k.bulan = bp.bulan;

-- Faktur yang belum lunas per tanggal posisi data
CREATE OR REPLACE VIEW ai.v_piutang AS
WITH bayar AS (
    SELECT faktur_id, sum(jumlah) AS terbayar
    FROM erp.pembayaran
    GROUP BY faktur_id
), posisi AS (
    SELECT nilai::date AS tgl FROM erp.parameter WHERE kunci = 'tanggal_posisi'
)
SELECT f.id     AS faktur_id,
       f.nomor  AS nomor_faktur,
       f.tanggal,
       f.jatuh_tempo,
       c.id     AS customer_id,
       c.nama   AS customer,
       c.kota,
       c.segmen,
       f.total,
       coalesce(b.terbayar, 0)            AS terbayar,
       f.total - coalesce(b.terbayar, 0)  AS sisa,
       greatest(posisi.tgl - f.jatuh_tempo, 0) AS hari_lewat_jatuh_tempo
FROM erp.faktur f
JOIN erp.customer c ON c.id = f.customer_id
LEFT JOIN bayar b   ON b.faktur_id = f.id
CROSS JOIN posisi
WHERE f.total - coalesce(b.terbayar, 0) > 0
  AND f.tanggal <= posisi.tgl;

CREATE OR REPLACE VIEW ai.v_stok AS
SELECT p.id   AS produk_id,
       p.kode AS kode_produk,
       p.nama AS produk,
       s.gudang,
       s.qty,
       s.stok_minimum,
       (s.qty < s.stok_minimum) AS di_bawah_minimum
FROM erp.stok s
JOIN erp.produk p ON p.id = s.produk_id;

-- ---------------------------------------------------------------------
-- Role khusus asisten AI: hanya baca, hanya schema ai & rag
-- (password ini hanya untuk workshop; ganti untuk lingkungan lain)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly') THEN
        CREATE ROLE erp_ai_readonly LOGIN PASSWORD 'baca_saja';
    END IF;
END
$$;

-- Dua setelan ini hanya NILAI AWAL sesi: klien bisa mengubahnya sendiri
-- (SET default_transaction_read_only = off, SET statement_timeout = 0).
-- Pengaman yang tidak bisa diubah klien adalah hak akses (GRANT) di bawah.
ALTER ROLE erp_ai_readonly SET default_transaction_read_only = on;
ALTER ROLE erp_ai_readonly SET statement_timeout = '5s';

GRANT USAGE ON SCHEMA ai, rag TO erp_ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA ai TO erp_ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag GRANT SELECT ON TABLES TO erp_ai_readonly;
-- Catatan: role ini sengaja TIDAK diberi USAGE pada schema erp,
-- sehingga "SELECT * FROM erp.gaji_karyawan" akan ditolak database.

-- Tabel sementara (CREATE TEMP TABLE) secara default boleh dibuat semua role (PUBLIC).
-- ERP dan kit tidak memakainya, jadi hak itu dicabut. Superuser (erp_admin) tidak terpengaruh.
-- 04_latihan.sql menerapkan ulang baris ini untuk database yang sudah ada.
REVOKE TEMPORARY ON DATABASE erp FROM PUBLIC;
