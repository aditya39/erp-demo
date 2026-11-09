-- =====================================================================
-- Database ERP contoh untuk workshop "Asisten AI untuk Aplikasi ERP"
-- Perusahaan fiktif: PT Nusantara Rasa (produsen makanan & minuman).
-- Seluruh data di database ini adalah DATA DUMMY hasil generator.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS erp;   -- tabel transaksi (sumber kebenaran)
CREATE SCHEMA IF NOT EXISTS ai;    -- view yang boleh dibaca asisten AI
CREATE SCHEMA IF NOT EXISTS rag;   -- potongan dokumen + embedding (diisi skrip ingest)

-- ---------------------------------------------------------------------
-- Master data
-- ---------------------------------------------------------------------
CREATE TABLE erp.parameter (
    kunci   TEXT PRIMARY KEY,
    nilai   TEXT NOT NULL
);

CREATE TABLE erp.kategori (
    id      SERIAL PRIMARY KEY,
    nama    TEXT NOT NULL UNIQUE
);

CREATE TABLE erp.produk (
    id           SERIAL PRIMARY KEY,
    kode         TEXT NOT NULL UNIQUE,
    nama         TEXT NOT NULL,
    kategori_id  INT NOT NULL REFERENCES erp.kategori(id),
    satuan       TEXT NOT NULL,
    harga_jual   NUMERIC(14,2) NOT NULL,   -- harga daftar saat ini
    aktif        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE erp.customer (
    id            SERIAL PRIMARY KEY,
    kode          TEXT NOT NULL UNIQUE,
    nama          TEXT NOT NULL,
    kota          TEXT NOT NULL,
    segmen        TEXT NOT NULL CHECK (segmen IN ('Distributor','Retail Modern','Toko')),
    termin_hari   INT NOT NULL,
    limit_kredit  NUMERIC(16,2) NOT NULL
);

CREATE TABLE erp.bahan_baku (
    id      SERIAL PRIMARY KEY,
    kode    TEXT NOT NULL UNIQUE,
    nama    TEXT NOT NULL,
    satuan  TEXT NOT NULL
);

-- Resep / bill of materials: kebutuhan bahan per 1 unit produk
CREATE TABLE erp.resep (
    produk_id     INT NOT NULL REFERENCES erp.produk(id),
    bahan_id      INT NOT NULL REFERENCES erp.bahan_baku(id),
    qty_per_unit  NUMERIC(12,5) NOT NULL,
    PRIMARY KEY (produk_id, bahan_id)
);

-- ---------------------------------------------------------------------
-- Biaya & harga per bulan
-- ---------------------------------------------------------------------
CREATE TABLE erp.harga_bahan (
    bahan_id   INT  NOT NULL REFERENCES erp.bahan_baku(id),
    bulan      DATE NOT NULL,                -- tanggal 1 tiap bulan
    harga      NUMERIC(14,2) NOT NULL,       -- harga rata-rata pembelian per satuan
    PRIMARY KEY (bahan_id, bulan)
);

CREATE TABLE erp.biaya_produksi (
    produk_id               INT  NOT NULL REFERENCES erp.produk(id),
    bulan                   DATE NOT NULL,
    unit_diproduksi         INT  NOT NULL,
    tenaga_kerja_per_unit   NUMERIC(12,2) NOT NULL,
    overhead_per_unit       NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (produk_id, bulan)
);

-- ---------------------------------------------------------------------
-- Transaksi penjualan & piutang
-- ---------------------------------------------------------------------
CREATE TABLE erp.faktur (
    id            SERIAL PRIMARY KEY,
    nomor         TEXT NOT NULL UNIQUE,
    tanggal       DATE NOT NULL,
    customer_id   INT  NOT NULL REFERENCES erp.customer(id),
    jatuh_tempo   DATE NOT NULL,
    total         NUMERIC(16,2) NOT NULL
);

CREATE TABLE erp.faktur_detail (
    id             SERIAL PRIMARY KEY,
    faktur_id      INT NOT NULL REFERENCES erp.faktur(id),
    produk_id      INT NOT NULL REFERENCES erp.produk(id),
    qty            INT NOT NULL,
    harga          NUMERIC(14,2) NOT NULL,
    diskon_persen  NUMERIC(5,2) NOT NULL DEFAULT 0,
    subtotal       NUMERIC(16,2) NOT NULL
);

CREATE TABLE erp.pembayaran (
    id          SERIAL PRIMARY KEY,
    faktur_id   INT  NOT NULL REFERENCES erp.faktur(id),
    tanggal     DATE NOT NULL,
    jumlah      NUMERIC(16,2) NOT NULL
);

-- ---------------------------------------------------------------------
-- Persediaan
-- ---------------------------------------------------------------------
CREATE TABLE erp.stok (
    produk_id      INT  NOT NULL REFERENCES erp.produk(id),
    gudang         TEXT NOT NULL,
    qty            INT  NOT NULL,
    stok_minimum   INT  NOT NULL,
    PRIMARY KEY (produk_id, gudang)
);

-- ---------------------------------------------------------------------
-- Data sensitif: TIDAK boleh bisa dibaca asisten AI.
-- Dipakai untuk mendemonstrasikan pengaman di level database.
-- ---------------------------------------------------------------------
CREATE TABLE erp.gaji_karyawan (
    id         SERIAL PRIMARY KEY,
    nama       TEXT NOT NULL,
    jabatan    TEXT NOT NULL,
    gaji       NUMERIC(14,2) NOT NULL
);

CREATE INDEX ON erp.faktur (tanggal);
CREATE INDEX ON erp.faktur (customer_id);
CREATE INDEX ON erp.faktur_detail (faktur_id);
CREATE INDEX ON erp.faktur_detail (produk_id);
CREATE INDEX ON erp.pembayaran (faktur_id);
