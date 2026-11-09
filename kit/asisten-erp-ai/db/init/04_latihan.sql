-- =====================================================================
-- Schema "latihan": koleksi dokumen RAG milik peserta (Sesi 2.4)
--
-- Prinsip:
--   1. Indeks dokumen bersama (rag.dokumen_chunk) hanya diisi admin/mentor.
--   2. Peserta memakai role erp_peserta yang HANYA bisa membuat tabel di
--      schema latihan (python -m asisten.rag ingest --koleksi <nama>).
--      Role ini tidak punya akses ke schema erp, ai, maupun rag.
--   3. Role asisten (erp_ai_readonly) boleh MEMBACA tabel di schema latihan,
--      sehingga cari_dokumen bisa mencari di koleksi peserta (RAG_KOLEKSI).
--
-- Berjalan otomatis pada volume database baru. Untuk database yang sudah ada:
--   docker exec -i erp-ai-db psql -U erp_admin -d erp -v ON_ERROR_STOP=1 < db/init/04_latihan.sql
-- (aman dijalankan berulang; scripts/server_bersama.sh menjalankannya otomatis)
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS latihan;

-- Password ini hanya untuk workshop; ganti untuk lingkungan lain.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_peserta') THEN
        CREATE ROLE erp_peserta LOGIN PASSWORD 'latihan_rag';
    END IF;
END
$$;

ALTER ROLE erp_peserta LOGIN PASSWORD 'latihan_rag' CONNECTION LIMIT 60;
ALTER ROLE erp_peserta SET statement_timeout = '30s';

-- Hanya peserta (CREATE) dan asisten (baca) yang boleh memakai schema latihan.
REVOKE ALL ON SCHEMA latihan FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA latihan TO erp_peserta;
GRANT USAGE ON SCHEMA latihan TO erp_ai_readonly;

-- Tabel yang dibuat peserta otomatis bisa dibaca asisten (ingest juga memberi GRANT eksplisit).
ALTER DEFAULT PRIVILEGES FOR ROLE erp_peserta IN SCHEMA latihan GRANT SELECT ON TABLES TO erp_ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA latihan TO erp_ai_readonly;

-- Tabel sementara tidak dipakai ERP maupun kit: cabut dari semua role biasa (sama dengan
-- 03_views_roles.sql; diulang di sini karena file ini juga dijalankan pada database yang sudah ada).
REVOKE TEMPORARY ON DATABASE erp FROM PUBLIC;

-- Catatan: erp_peserta sengaja TIDAK diberi USAGE pada schema erp, ai, dan rag.
-- Tipe "vector" (extension pgvector di schema public) tetap bisa dipakai karena
-- PUBLIC memiliki USAGE pada schema public, tetapi tidak bisa membuat objek di sana.
