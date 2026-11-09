# AGENTS.md — Asisten AI untuk ERP (kode contoh workshop)

Panduan untuk coding agent (Claude Code, Codex, dll.) dan developer yang mengubah proyek ini.

## Gambaran
- Python 3.10+. Paket `asisten/` (agent loop, tools, RAG), aplikasi web `web/` (FastAPI + HTML/JS tanpa build step).
- Database PostgreSQL 17 + pgvector lewat `docker compose`. Seluruh data adalah data dummy perusahaan fiktif.
- Model: lokal lewat Ollama (API kompatibel OpenAI, `asisten/llm.py`). Cloud opsional: Claude Code (`asisten/claude_code.py`, tools lewat MCP `asisten/mcp_server.py`) atau API kompatibel OpenAI.

## Perintah
- Test: `python -m pytest -q`
- Tanya asisten dari terminal: `python -m asisten --pengguna budi "pertanyaan"`
- Aplikasi web: `python -m web` lalu buka http://localhost:8000
- Evaluasi akurasi model: `python scripts/evaluasi.py`

## Cara menambah tool
1. Tulis di `asisten/tools_tambahan.py` memakai dekorator `@tool` (contoh lengkap di `asisten/tools.py`, mis. `penjualan_teratas`). Jangan mengubah `asisten/agent.py` untuk menambah tool.
2. Query HANYA ke view schema `ai` (daftar view: `db/init/03_views_roles.sql`). Jangan membaca schema `erp` dan jangan menulis data.
3. Selalu pakai parameter psycopg (`%(nama)s`). Nama kolom/tabel yang dinamis wajib dipilih dari whitelist.
4. Batasi jumlah baris (default 5, maksimal 20).
5. Hitung angka turunan (persen, selisih, total) di kode, lalu sertakan field `*_fmt` memakai `asisten/format.py` (`rupiah`, `persen`, `bulan`).
6. Isi `izin` yang sesuai: `produk | penjualan | hpp | piutang | stok | dokumen | so_buat`.
7. Deskripsi tool berbahasa Indonesia dan menjelaskan KAPAN tool dipakai.
8. Opsional: field `grafik` (`tipe` line/bar, `judul`, `label`, `seri`, `horizontal`) untuk ditampilkan di web; field ini tidak dikirim ke model.
9. Tambahkan test di `tests/test_tools.py` dan pastikan `python -m pytest -q` lulus.
10. Aksi tulis (mis. membuat sales order) memakai pola draft + konfirmasi manusia, seperti `asisten/transaksi.py`: tool hanya menyusun draft dari view `ai`, sistem ERP menghitung harga/persetujuan, user menekan Simpan, lalu KODE aplikasi (bukan model) yang memanggil API ERP.

## Larangan
- Jangan membuat tool yang menjalankan SQL bebas tulisan model.
- Jangan memberi model tool yang menyimpan atau mengubah transaksi; model hanya boleh menyiapkan draft.
- Jangan memakai `DATABASE_URL_ADMIN` di tool (hanya untuk ingest RAG).
- Jangan menaruh API key di kode; jangan commit `.env`.
