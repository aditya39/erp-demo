-- =====================================================================
-- Migrasi ERP Nusantara Rasa (idempoten, dijalankan otomatis saat server start)
-- Menambah tabel yang dibutuhkan aplikasi ERP di atas database contoh kit.
-- Tidak mengubah view schema "ai" yang dibaca asisten AI.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_app') THEN
        CREATE ROLE erp_app LOGIN PASSWORD 'aplikasi_erp';
    END IF;
END
$$;
ALTER ROLE erp_app SET statement_timeout = '15s';

-- ---------------------------------------------------------------------
-- Pengguna & hak akses (di ERP sungguhan: modul user management)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.pengguna (
    kode            TEXT PRIMARY KEY,
    nama            TEXT NOT NULL,
    jabatan         TEXT NOT NULL,
    divisi          TEXT NOT NULL,
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    izin            TEXT[] NOT NULL DEFAULT '{}',
    aktif           BOOLEAN NOT NULL DEFAULT TRUE,
    login_terakhir  TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- Sales order -> (persetujuan) -> faktur
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.sales_order (
    id               SERIAL PRIMARY KEY,
    nomor            TEXT NOT NULL UNIQUE,
    tanggal          DATE NOT NULL,
    customer_id      INT  NOT NULL REFERENCES erp.customer(id),
    gudang           TEXT NOT NULL,
    diskon_tambahan  NUMERIC(5,2) NOT NULL DEFAULT 0,
    catatan          TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL CHECK (status IN ('Menunggu Persetujuan','Ditahan','Faktur Terbit','Ditolak','Dibatalkan')),
    persetujuan      JSONB NOT NULL DEFAULT '[]',
    total            NUMERIC(16,2) NOT NULL,
    faktur_id        INT REFERENCES erp.faktur(id),
    dibuat_oleh      TEXT NOT NULL,
    dibuat_pada      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS erp.sales_order_detail (
    id             SERIAL PRIMARY KEY,
    so_id          INT NOT NULL REFERENCES erp.sales_order(id),
    produk_id      INT NOT NULL REFERENCES erp.produk(id),
    qty            INT NOT NULL CHECK (qty > 0),
    harga          NUMERIC(14,2) NOT NULL,
    diskon_persen  NUMERIC(5,2) NOT NULL,
    subtotal       NUMERIC(16,2) NOT NULL
);

-- ---------------------------------------------------------------------
-- Persediaan & jejak audit
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.mutasi_stok (
    id           SERIAL PRIMARY KEY,
    tanggal      DATE NOT NULL,
    produk_id    INT  NOT NULL REFERENCES erp.produk(id),
    gudang       TEXT NOT NULL,
    jenis        TEXT NOT NULL,          -- Penjualan, Produksi, Penyesuaian
    qty          INT  NOT NULL,          -- + masuk, - keluar
    saldo        INT,                    -- saldo setelah mutasi (bila tercatat)
    referensi    TEXT NOT NULL DEFAULT '',
    keterangan   TEXT NOT NULL DEFAULT '',
    pengguna     TEXT NOT NULL DEFAULT 'sistem',
    dibuat_pada  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS erp.audit_log (
    id          BIGSERIAL PRIMARY KEY,
    waktu       TIMESTAMPTZ NOT NULL DEFAULT now(),
    pengguna    TEXT NOT NULL,
    modul       TEXT NOT NULL,
    aksi        TEXT NOT NULL,
    objek       TEXT NOT NULL DEFAULT '',
    keterangan  TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------
-- Kolom tambahan pada tabel kit (tidak dipakai view ai.*)
-- ---------------------------------------------------------------------
ALTER TABLE erp.customer   ADD COLUMN IF NOT EXISTS alamat   TEXT;
ALTER TABLE erp.customer   ADD COLUMN IF NOT EXISTS kontak   TEXT;
ALTER TABLE erp.customer   ADD COLUMN IF NOT EXISTS telepon  TEXT;
ALTER TABLE erp.customer   ADD COLUMN IF NOT EXISTS aktif    BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE erp.faktur     ADD COLUMN IF NOT EXISTS gudang       TEXT;
ALTER TABLE erp.faktur     ADD COLUMN IF NOT EXISTS so_id        INT;
ALTER TABLE erp.faktur     ADD COLUMN IF NOT EXISTS dibuat_oleh  TEXT;
ALTER TABLE erp.pembayaran ADD COLUMN IF NOT EXISTS metode       TEXT;
ALTER TABLE erp.pembayaran ADD COLUMN IF NOT EXISTS referensi    TEXT;
ALTER TABLE erp.pembayaran ADD COLUMN IF NOT EXISTS dibuat_oleh  TEXT;

-- Asal sales order: 'manual' (form) atau 'asisten_ai' (draft disiapkan Asisten AI, disimpan oleh user sendiri)
ALTER TABLE erp.sales_order ADD COLUMN IF NOT EXISTS sumber TEXT NOT NULL DEFAULT 'manual';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sales_order_sumber_check'
                   AND conrelid = 'erp.sales_order'::regclass) THEN
        ALTER TABLE erp.sales_order ADD CONSTRAINT sales_order_sumber_check CHECK (sumber IN ('manual', 'asisten_ai'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS sales_order_tanggal_idx  ON erp.sales_order (tanggal);
CREATE INDEX IF NOT EXISTS sales_order_status_idx   ON erp.sales_order (status);
CREATE INDEX IF NOT EXISTS so_detail_so_idx         ON erp.sales_order_detail (so_id);
CREATE INDEX IF NOT EXISTS mutasi_stok_tanggal_idx  ON erp.mutasi_stok (tanggal);
CREATE INDEX IF NOT EXISTS audit_log_waktu_idx      ON erp.audit_log (waktu);

-- ---------------------------------------------------------------------
-- Hak role aplikasi: baca-tulis transaksi, TANPA hapus, TANPA data gaji.
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA erp, ai TO erp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA erp TO erp_app;
REVOKE ALL ON erp.gaji_karyawan FROM erp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA erp TO erp_app;
GRANT SELECT ON ALL TABLES IN SCHEMA ai TO erp_app;   -- view laporan (HPP, piutang) dipakai ulang
