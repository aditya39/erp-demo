# Dokumen latihan RAG (Sesi 2.4)

Dokumen di folder ini **sengaja tidak ada di indeks bersama** (`rag.dokumen_chunk`, isi folder `dokumen/`).
Sebelum di-ingest, asisten tidak bisa menjawab pertanyaan tentang isinya. Peserta memasukkannya sendiri ke
koleksi miliknya, lalu membandingkan jawaban sebelum dan sesudah:

```bash
python -m asisten.rag ingest --koleksi <nama>      # -> tabel latihan.dokumen_<nama>
RAG_KOLEKSI=<nama> python -m asisten --pengguna andi "Jam berapa batas order agar dikirim besok ke Bandung?"
```

Windows PowerShell: `$env:RAG_KOLEKSI="<nama>"` lalu jalankan `python -m asisten ...`, atau isi `RAG_KOLEKSI` di `.env`.

- Nama koleksi: huruf kecil, angka, dan garis bawah, maksimal 30 karakter (mis. `andi` atau `tim_2`).
- Di server bersama, ingest memakai role `erp_peserta` (`DATABASE_URL_PESERTA`) yang hanya bisa membuat tabel di
  schema `latihan`; indeks bersama dan data ERP tidak bisa diubah.
- File `README.md` ini tidak ikut di-ingest. Dokumen `.md` lain yang Anda tambahkan ke folder ini ikut di-ingest.
- Format dokumen sama dengan folder `dokumen/`: judul `#`, baris nomor dokumen, lalu bagian `##` (satu bagian = satu potongan).
- Hapus koleksi setelah latihan: `python -m asisten.rag hapus --koleksi <nama>`.
