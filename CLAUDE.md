# erp-demo

ERP Nusantara Rasa (perusahaan fiktif, data dummy) untuk demo workshop: agent QA menguji aplikasi lewat browser, melaporkan bug sebagai issue, lalu agent perbaikan menyiapkan draft pull request.

## Struktur

| Folder | Isi |
|---|---|
| `erp-nusantara-rasa/server/` | Backend FastAPI. **Aturan bisnis ada di `logika.py`** (diskon, limit kredit, persetujuan SO, faktur). Endpoint di `routers/` |
| `erp-nusantara-rasa/frontend/` | Frontend Angular 21 + PrimeNG |
| `kit/asisten-erp-ai/dokumen/` | SOP dan kebijakan perusahaan. Ini sumber kebenaran aturan bisnis. Diskon: `02-Kebijakan-Harga-dan-Diskon.md` (KBJ-PJL-002). Kredit: `03-Kebijakan-Kredit-dan-Penagihan.md` (KBJ-KEU-004) |
| `kit/asisten-erp-ai/` | Paket asisten AI dan database contoh. Tidak perlu diubah untuk perbaikan bug aturan penjualan |
| `tests/` | Unit test aturan bisnis, jalan tanpa database |
| `.claude/skills/qa-erp/` | Skill agent QA |

## Test

```
pip install -r requirements-dev.txt
python -m pytest
```

Test tidak butuh database. Fungsi yang membaca database (`kondisi_kredit`, `_margin_produk`) diganti data palsu lewat fixture `erp` di `tests/conftest.py`. Contoh pola ada di `tests/test_aturan_so.py`.

## Menjalankan aplikasi (opsional)

`docker compose up -d --build` di root repo, lalu buka http://localhost:8081. Akun demo: `andi` (Sales Supervisor), `dewi` (Manajer Penjualan), password `demo123`.

## Aturan kerja

- Aturan bisnis mengikuti dokumen di `kit/asisten-erp-ai/dokumen/`. Kalau kode dan dokumen berbeda, dokumen yang benar.
- Perbaikan seminimal mungkin. Jangan merapikan kode lain di commit yang sama.
- Setiap perbaikan bug disertai unit test yang gagal sebelum perbaikan dan lulus sesudahnya.
- Jangan mengubah test yang sudah ada supaya lulus.
- Pesan commit dan isi pull request dalam Bahasa Indonesia.
