# ERP Nusantara Rasa — aplikasi ERP demo dengan Asisten AI lokal

Aplikasi ERP lengkap untuk demo workshop: penjualan, keuangan, persediaan, produksi & HPP, dokumen,
dan pengaturan hak akses, dengan **Asisten AI** yang berjalan lokal (Ollama) di dalam setiap halaman.

> PT Nusantara Rasa adalah perusahaan **fiktif**. Seluruh data adalah data dummy dari generator di kit
> (`../kit/asisten-erp-ai/db/generate_seed.py --bulan-akhir 2026-10`): periode **Mei 2025 – Oktober 2026**,
> tanggal sistem ERP 31-10-2026 (periode berjalan = Oktober 2026).

```
Browser (Angular 21 + PrimeNG)
   │  REST + SSE (satu port, bisa offline)
   ▼
FastAPI  ── server/routers/*  ── role DB erp_app (baca-tulis transaksi)
   │
   └── /api/ai/chat ── paket "asisten" dari kit (agent loop + 7 tools + RAG)
                         └── role DB erp_ai_readonly (hanya baca view schema ai)
                         └── Ollama qwen3:8b + bge-m3 (lokal) / model cloud (opsional)
PostgreSQL 17 + pgvector (docker, dari kit)
```

Asisten AI di ERP ini memakai **otak yang sama** dengan kit hands-on (`../kit/asisten-erp-ai/asisten`).
Tool baru yang ditambahkan peserta / saat Demo 5 di `tools_tambahan.py` otomatis ikut muncul di ERP.

## Menjalankan

### Cara 1 — semua di Docker (disarankan)

```bash
cd erp-nusantara-rasa
docker compose up -d --build        # pertama kali ±1–3 menit (build image Angular + Python)
# buka http://localhost:8080
```

Satu perintah ini menjalankan: database (PostgreSQL + pgvector, dari kit), server ERP, migrasi, dan pengisian
indeks dokumen RAG otomatis. Compose ini memakai proyek yang sama dengan kit (`name: asisten-erp-ai`),
jadi database dan model yang sudah ada dipakai bersama.

**Model AI (Ollama)** — pilih salah satu lewat file `.env` di folder ini:

| Pilihan | Isi `.env` | Catatan |
|---|---|---|
| Ollama diinstal langsung di Mac (**disarankan untuk demo**) | kosongkan / hapus `COMPOSE_PROFILES` dan `OLLAMA_URL` | memakai GPU Apple Silicon. Siapkan sekali: `ollama pull qwen3:8b && ollama pull bge-m3`, jalankan dengan `OLLAMA_CONTEXT_LENGTH=8192` |
| Ollama di Docker | `COMPOSE_PROFILES=ollama` dan `OLLAMA_URL=http://ollama:11434` | model diunduh otomatis (±6,4 GB). Di Mac hanya CPU → jawaban 1–2 menit |

**Model cloud di Docker** (Demo lokal vs cloud): dengan `CLOUD_PENYEDIA=claude-code` (default) tombol **Cloud** tidak aktif,
karena image ERP tidak berisi Claude Code (tooltip tombol menjelaskan alasannya). Pilih salah satu:

- isi `../kit/asisten-erp-ai/.env` dengan `CLOUD_PENYEDIA=api`, `CLOUD_BASE_URL=https://api.anthropic.com/v1/`,
  `CLOUD_MODEL=claude-haiku-5-5` (model Demo 3 di workshop), `CLOUD_API_KEY=…`, dan biarkan `CLOUD_SUHU` kosong
  (model Claude terbaru menolak temperature < 1), lalu `docker compose up -d erp` (`restart` tidak membaca ulang `.env`);
- atau jalankan ERP tanpa Docker (Cara 2) di laptop yang sudah login `claude` (tidak dipakai di workshop).

Dari `.env` kit, container ERP hanya memakai `CLOUD_*` dan setelan umum (mis. `MAKS_LANGKAH`). Model lokal, embedding,
dan `RAG_KOLEKSI` dikunci di `docker-compose.yml` (`qwen3:8b` + `bge-m3` di Ollama), jadi profil (b)/(c) yang
ditempel di `.env` kit tidak mengubah ERP. Profil (c) diuji dari laptop peserta, bukan dengan mengubah `.env` kit di server.

Perintah lain:

```bash
docker compose logs -f erp          # log ERP (migrasi, indeks RAG, error)
docker compose restart erp          # setelah menambah tool di kit (Demo 5) — folder agent kit dipasang langsung
docker compose up -d --build erp    # setelah mengubah kode ERP (server/ atau frontend/)
docker compose down                 # berhenti (data & model tetap)
./scripts/reset-data.sh             # kembalikan data ke kondisi awal setelah gladi
```

### Cara 2 — server ERP tanpa Docker (pengembangan)

Prasyarat: Python 3.10+, Node.js 20+, database & Ollama berjalan (`cd ../kit/asisten-erp-ai && docker compose up -d`,
lalu `python -m asisten.rag ingest` sekali).

```bash
./scripts/jalankan.sh               # membuat venv + build frontend bila belum, lalu start server :8080
cd frontend && npm start            # dev server :4200 dengan hot reload (proxy /api ke :8080)
```

Pakai salah satu cara saja; keduanya memakai port 8080.

### Password database (wajib sebelum port 5433 dibuka di jaringan)

Password default (`admin_workshop`, `aplikasi_erp`) tertulis di kit yang dibagikan ke peserta. Sebelum database dibuka
di server LAN bersama, isi `.env` folder ini (huruf, angka, `-`, `_` saja, karena masuk ke URL koneksi):

```bash
DB_ADMIN_PASSWORD=…     # superuser erp_admin (POSTGRES_PASSWORD service db kit)
ERP_APP_PASSWORD=…      # role aplikasi erp_app
```

- `.env` folder ini juga dipakai compose kit yang di-include (mengalahkan `.env` milik kit), oleh Cara 2, serta oleh
  `scripts/reset-data.sh` dan `scripts/jalankan.sh`. Bila kit dijalankan sendiri, isi nilai yang sama di `.env` kit.
- `ERP_APP_PASSWORD`: ubah lalu `docker compose up -d erp`; migrasi menyetel ulang password `erp_app` setiap ERP start.
- `DB_ADMIN_PASSWORD` hanya dipakai saat volume database dibuat (pertama kali atau setelah `reset-data.sh`). Untuk database
  yang sudah berjalan, ganti dulu di PostgreSQL (`docker exec -it erp-ai-db psql -U erp_admin -d erp -c "ALTER ROLE erp_admin PASSWORD '…'"`),
  lalu isi `.env` dan `docker compose up -d erp`.
- Periksa hasilnya tanpa menjalankan apa pun: `docker compose config | grep -E "PASSWORD|DATABASE_URL"`.
- Role read-only asisten (`erp_ai_readonly`) dibuat oleh kit (`db/init`).

### Sebelum praktik Hari 2

- Hentikan container demo Hari 1 (proyek docker compose `h1-*`; erp-demo Hari 1 sengaja berisi bug diskon):
  `docker ps --filter name=h1-` lalu `docker ps -q --filter name=h1- | xargs -r docker stop` (aman bila tidak ada
  container yang cocok).

## Akun demo (password `demo123`)

| User | Jabatan | Bisa apa | Asisten AI boleh baca |
|---|---|---|---|
| `budi` | Direktur Operasional | semua, termasuk memutuskan SO credit hold & hak akses | semua data |
| `dewi` | Manajer Penjualan | buat SO, setujui diskon > 1,5% | produk, penjualan, piutang, stok, dokumen |
| `andi` | Sales Supervisor | buat SO (diskon ≤ 1,5%), kelola customer | produk, penjualan, stok, dokumen (**tanpa HPP**) |
| `sari` | Staf Finance & Accounting | catat pembayaran, setujui SO > limit, ubah limit | produk, penjualan, HPP, piutang, dokumen |
| `agus` | Supervisor Gudang | stock opname | produk, stok, dokumen |
| `rudi` | Administrator Sistem | pengguna & hak akses | dokumen |

Hak akses diatur di **Pengaturan › Pengguna & Hak Akses**. Izin "Akses data" dipakai juga oleh tool AI,
jadi mencabut izin di sini langsung membuat tool AI terkait ditolak (dicek oleh kode, bukan oleh prompt).

## Modul

| Modul | Halaman | Aturan bisnis yang ditegakkan sistem |
|---|---|---|
| Dashboard | KPI, omzet 12 bulan, kategori, "Perlu perhatian" (+ tombol Tanya AI), umur piutang, aktivitas | isi mengikuti hak akses; kartu tanpa akses tampil terkunci |
| Penjualan | Sales Order (daftar, buat, detail + persetujuan), Faktur (+ cetak A4), Customer, Laporan | diskon standar per segmen; diskon tambahan ≤ 1,5% / ≤ 3% (Manajer Penjualan); tidak ada diskon bila tunggakan > 30 hari; SO melebihi limit → Ditahan (Finance); tunggakan > H+60 → credit hold (Direktur); cek stok gudang; tanggal di periode berjalan |
| Keuangan | Umur piutang (5 kelompok + tahap penagihan), Penerimaan pembayaran | pembayaran dialokasikan ke faktur tertua lebih dulu |
| Persediaan | Stok gudang (hari cukup, opname), Mutasi stok | faktur mengurangi stok + mencatat mutasi |
| Produksi & Biaya | Produk (HPP, margin, resep), Bahan baku (riwayat harga), Analisis HPP | HPP naik > 8% → tanda wajib kajian |
| Dokumen | 5 SOP & kebijakan (sumber RAG yang sama dengan AI) | – |
| Pengaturan | Matriks hak akses, Log aktivitas (termasuk setiap pertanyaan AI + tool yang dipakai) | perubahan izin tercatat |

Aturan diambil dari dokumen kebijakan di kit (`dokumen/02-…`, `03-…`, `05-…`). Prinsipnya: **aturan
ditegakkan kode ERP; AI hanya menjelaskan aturan dari dokumen**.

## Skenario demo di ERP

| # | Skenario | Langkah | Poin ajar |
|---|---|---|---|
| 1 | Pembukaan | Login `budi` → Ringkasan → "Perlu tindakan: HPP Roti Cokelat naik 11,1%" → **Tanya** | AI di dalam layar kerja, bukan aplikasi terpisah |
| 2 | Tanpa internet | Matikan WiFi (indikator topbar berubah "Offline") → tanya tren Biskuit Kelapa | model lokal |
| 3 | HPP multi-langkah | Produk › Roti Cokelat → **Analisis HPP** → buka langkah agent | tool chaining, angka dari query |
| 4 | Hak akses | Login `andi` → menu HPP tidak ada → tanya HPP di panel AI → ⛔ ditolak | izin dicek kode |
| 5 | Hak akses live | Login `rudi`/`budi` → cabut izin HPP milik Sari → login `sari` → tanya HPP → ditolak | satu sumber hak akses ERP = AI |
| 6 | Data live | Login `andi` → buat SO (mis. Wafer Vanila ke Mart Harian Kita; hindari Biskuit Kelapa & Teh Melati agar angka demo tren tidak bergeser) → faktur terbit → tanya "5 customer dengan penjualan terbesar bulan ini" | AI membaca transaksi terbaru |
| 7 | Aturan vs AI | SO CV Laju Makmur Abadi (Ditahan) → **Tanya Asisten soal aturannya** | RAG menjelaskan; keputusan tetap di sistem & manusia |
| 8 | Persetujuan | Login `budi` → sidebar "Sales order (2)" / Perlu tindakan → setujui credit hold CV Laju Makmur Abadi (lewat jatuh tempo 107 hari, piutang masih di bawah limit) → faktur terbit, tahapan & riwayat dokumen ikut terisi; login `dewi` → setujui diskon tambahan 2% Swalayan Sentosa | alur kerja nyata |
| 9 | Audit | Pengaturan › Log Aktivitas → baris "Asisten AI" berisi pertanyaan & tool | governance |
| 10 | Lokal vs cloud / cadangan | Panel AI › ⋯ › Bandingkan lokal vs cloud, atau Putar rekaman demo | kualitas vs privasi; cadangan presentasi |
| 11 | Agent penyiap transaksi | Login `andi` → panel Asisten: "Buatkan SO untuk Toko Murah Meriah: 40 pak Wafer Vanila dan 30 pak Keripik Singkong Balado" → kartu **Draft sales order** (harga, diskon, kredit, status dari simulasi ERP: total Rp 554.680, Faktur Terbit) → **Simpan sales order** → buka SO: badge "Dibuat lewat Asisten AI", riwayat "Asisten AI menyiapkan draft · Andi mengonfirmasi". Variasi (jangan disimpan: SO yang tersimpan mengubah penjualan & stok Oktober untuk semua peserta): "Buatkan SO untuk Swalayan Sentosa: 40 pak Wafer Vanila dan 30 pak Keripik Singkong Balado, diskon tambahan 2%" → Rp 520.720, Menunggu Persetujuan Manajer Penjualan; Toko Berkah Abadi → Ditahan (credit hold + limit), CV Laju Makmur Abadi → Ditahan (credit hold); 20.000 pak Wafer Vanila → stok tidak cukup (tersedia 6.837), Simpan nonaktif; diskon 4% → ditolak sistem; "5 karton Wafer Vanila" atau "Nastar Keju" → asisten bertanya balik (satuan belum dikenal / produk tidak persis cocok); **Ubah di form** → form SO terisi draft. Buka langkah agent → "Query yang dijalankan" | AI hanya mengisi draft; sistem menghitung & menegakkan aturan; manusia menyimpan dengan sesi & hak aksesnya sendiri |

Pintasan: `⌘J` / `Ctrl+J` panel Asisten, `⌘K` / `Ctrl+K` pencarian global (Enter tanpa hasil = tanyakan ke Asisten).
Di layar 1366 px (proyektor), sidebar otomatis diringkas saat panel Asisten dibuka.

## Desain & alur

- Design system netral dengan satu warna merek (hijau tua) — token di `frontend/src/styles/_token.scss`, mode gelap tersedia
  (menu pengguna). Ikon Lucide (ISC). Warna semantik hanya untuk status; Asisten memakai satu aksen (ungu) tanpa gradien.
- Pola halaman konsisten: breadcrumb di topbar → judul + meta + aksi → strip statistik → panel/tabel.
- Dokumen transaksi (SO, faktur) punya **tahapan** (Dibuat → Persetujuan → Faktur → Lunas), **dokumen terkait**, dan
  **riwayat** (siapa melakukan apa, kapan). Persetujuan yang menjadi tugas user ditandai dan dihitung di sidebar.
- Semua daftar bisa difilter, diurutkan, dan **diekspor ke CSV** (pemisah `;`, langsung terbaca Excel).
- Form SO memeriksa aturan secara langsung sebelum disimpan, dan meminta konfirmasi bila halaman ditinggalkan.
  Diskon tambahan menerima koma atau titik desimal (`1,5` = `1.5` = 1,5%).
- Kartu draft SO di panel Asisten tampil sebagai dokumen ERP yang belum disimpan (bukan teks chat): angkanya dari
  `POST /api/sales-order/simulasi`, tombolnya Simpan / Ubah di form / Batal.

## Struktur

```
server/            FastAPI: config, db, keamanan (hash & sesi), izin, logika (aturan bisnis), migrasi, routers/
frontend/          Angular 21 + PrimeNG 21 (standalone, signals, zoneless)
  src/app/core     api, auth, format, model, pipes, tema
  src/app/layout   shell (sidebar, topbar, pencarian ⌘K, notifikasi)
  src/app/ai       panel Asisten AI, kartu langkah agent, streaming SSE, rekaman
  src/app/pages    halaman per modul
  src/styles       token desain (terang/gelap), layout, komponen
scripts/           jalankan.sh (tanpa Docker), reset-data.sh
Dockerfile         build multi-tahap (Node → Python); docker-compose.yml menyertakan compose kit
rekaman/           rekaman jawaban AI dari ERP (otomatis, grup "Riwayat dari ERP ini"); tidak ikut git (.gitignore):
                   salin manual file <tanggal>-<jam>-lokal-<user>-….json ke laptop demo bila ingin dipakai
```

## Keamanan (ringkas)

- ERP memakai role `erp_app` (tanpa DELETE, tanpa akses tabel gaji); AI memakai role `erp_ai_readonly` yang
  hanya bisa membaca view `ai.*`. Nama variabel koneksi sengaja beda (`ERP_DATABASE_URL` vs `DATABASE_URL`).
- Identitas user AI diambil dari cookie sesi ERP (HMAC), bukan dari isi request.
- Password di-hash PBKDF2; jawaban model di-escape sebelum dirender.
- Agent penyiap transaksi: tool `siapkan_draft_so` hanya membaca view `ai.*` dan mengembalikan draft; model tidak punya
  tool simpan. Harga, diskon, kredit, dan persetujuan dihitung ERP; SO disimpan oleh browser user lewat
  `POST /api/sales-order` dengan sesi dan izin `so_buat` miliknya (aturan bisnis sama dengan form). Kolom
  `sales_order.sumber` (`manual` / `asisten_ai`) dan log aktivitas mencatat bahwa draft berasal dari Asisten AI dan siapa yang mengonfirmasi.
- Password database bisa diganti lewat `DB_ADMIN_PASSWORD` / `ERP_APP_PASSWORD` (lihat di atas); wajib sebelum port 5433 dibuka di jaringan.
- Ini aplikasi demo: daftar akun demo tampil di halaman login, password seragam. Jangan dipakai untuk data nyata.
