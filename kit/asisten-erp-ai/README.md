# Asisten AI untuk Aplikasi ERP — Kit Demo & Workshop

Kode contoh untuk workshop **Agentic AI, RAG, dan AI Lokal**: asisten AI di dalam layar ERP yang
menjawab pertanyaan seperti *"bagaimana tren penjualan produk X?"* atau *"kenapa HPP produk Y naik?"*
memakai data ERP, berjalan dengan model lokal (tanpa internet).

> Seluruh data adalah **data dummy** perusahaan fiktif *PT Nusantara Rasa*. Tidak ada data klien.

```
 Layar ERP (web)  ──►  Agent loop (Python)  ──►  Model lokal (Ollama)  / model cloud (opsional)
   panel chat            │   ▲
                         ▼   │ hasil tool
                   Tools berparameter ──► PostgreSQL: view schema "ai" (role read-only)
                   cari_dokumen      ──► pgvector: potongan dokumen SOP & kebijakan (RAG)
```

Model cloud default-nya **Claude Code** dengan akun Claude masing-masing (tanpa API key): Claude Code
menjadi "otak" agent, sedangkan tools, hak akses, dan koneksi read-only tetap sama karena dipakai lewat
MCP (`asisten/mcp_server.py`). Lihat [Model cloud](#model-cloud-opsional).

## Isi folder

| Folder / file | Isi |
|---|---|
| `asisten/` | Inti asisten: `agent.py` (loop), `tools.py` (tools), `rag.py` (RAG), `pengguna.py` (hak akses), `transaksi.py` (tool `siapkan_draft_so`), `erp_api.py` (klien API ERP untuk Latihan 7), `tools_tambahan.py` (tempat tool baru), `mcp_server.py` (tools lewat MCP), `claude_code.py` (mode cloud lewat Claude Code) |
| `web/` | Aplikasi web ala ERP: dashboard + panel Asisten AI, langkah agent, grafik, mode bandingkan, putar rekaman |
| `db/` | Skema, generator data dummy, view & role read-only (`docker compose` menjalankan semuanya) |
| `dokumen/` | 5 dokumen internal dummy untuk RAG (SOP retur, kebijakan harga, kredit, panduan HPP, FAQ) — indeks bersama |
| `dokumen-latihan/` | SOP Pengiriman Barang: sengaja tidak ada di indeks bersama, di-ingest peserta ke koleksinya sendiri (Sesi 2.4) |
| `dokumen-uji/` | Dokumen berisi prompt injection (jangan di-ingest ke indeks bersama) dan `Email-PO-Swalayan-Sentosa.txt` (email PO berisi instruksi tersembunyi, untuk Latihan 7 `--file`) |
| `latihan/` | Latihan hands-on 01–07 (ada bagian TODO) + `pertanyaan-menjebak.md` (lembar kerja Sesi 2.3) |
| `solusi/` | Solusi latihan + contoh tool tambahan |
| `scripts/` | `cek_setup.py` (cek kesiapan laptop), `evaluasi.py` (uji akurasi model), `server_bersama.sh` (siapkan laptop mentor sebagai server), `uji_beban.py` (uji kapasitas server model) |
| `tests/` | Unit test (`python -m pytest -q`) |
| `referensi-java/` | Kerangka pola yang sama dengan Spring AI |
| `AGENTS.md` / `CLAUDE.md` | Aturan proyek untuk coding agent (dipakai di Demo 5) |
| `mcp-erp.json` | Konfigurasi untuk memakai tools ERP dari sesi Claude Code Anda (opsional) |

## Persiapan

### 1. Kebutuhan

- Python 3.10+ (cek: `python3 --version`; python3 bawaan macOS 3.9 terlalu lama, instal dari python.org)
- [Ollama](https://ollama.com) (model lokal) — tidak perlu jika memakai model di server mentor
- Docker Desktop (database) — tidak perlu jika memakai database di server mentor
- RAM 16 GB untuk menjalankan `qwen3:8b` di laptop sendiri
- Opsional, untuk tombol **Cloud**: [Claude Code](https://claude.com/claude-code) yang sudah login dengan akun Claude Anda

### 2. Database

```bash
docker compose up -d                 # PostgreSQL + pgvector di localhost:5433, data dummy otomatis dimuat
```

Data dummy mencakup **Mei 2025 – Oktober 2026** (18 bulan, posisi 31-10-2026); bagi asisten, "bulan ini" =
Oktober 2026. Seed dibuat dengan `python3 db/generate_seed.py --bulan-akhir 2026-10` (hasilnya selalu sama).
Untuk periode lain: ganti `--bulan-akhir` (tanpa argumen = bulan lalu dari tanggal hari ini), lalu
`docker compose down -v && docker compose up -d`.

### 3. Model lokal

```bash
ollama pull qwen3:8b                 # model chat (±5,2 GB)
ollama pull bge-m3                   # model embedding untuk RAG (±1,2 GB)
```

Atur panjang konteks Ollama minimal 8192 token (default 4096 terlalu pendek: prompt agent terpotong tanpa
pesan error). macOS: `launchctl setenv OLLAMA_CONTEXT_LENGTH 8192`, lalu Quit Ollama dan buka lagi (ulangi
setelah Mac restart). Windows: `setx OLLAMA_CONTEXT_LENGTH 8192`, lalu buka ulang Ollama. `cek_setup.py` memeriksanya.

### 4. Python

```bash
python3 -m venv .venv                # Windows: python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
python -m asisten.rag ingest         # simpan dokumen ke pgvector (sekali saja; di server bersama sudah oleh mentor)
python scripts/cek_setup.py          # semua baris harus ✓
```

## Mode praktik

Pilih satu profil di `.env` (contoh lengkap di `.env.example`). `python scripts/cek_setup.py` menampilkan
mode yang terbaca.

| Profil | Untuk | Yang diisi di `.env` |
|---|---|---|
| (a) Laptop sendiri | laptop dengan RAM 16 GB dan GPU / Apple Silicon | nilai bawaan `.env.example` |
| (b) Server bersama | laptop peserta ringan (mis. i5 tanpa GPU: `qwen3:8b` terlalu lambat) | `DATABASE_URL`, `DATABASE_URL_PESERTA`, `LOKAL_BASE_URL`, `EMBED_BASE_URL`, `ERP_URL` ke IP mentor |
| (c) Cadangan cloud | server bersama terlalu lambat atau mati | `LOKAL_BASE_URL=https://api.anthropic.com/v1/`, `LOKAL_MODEL=claude-haiku-5-5`, `LOKAL_API_KEY` (kunci kelompok dari mentor), `LOKAL_REASONING_EFFORT=` dan `LOKAL_SUHU=` kosong; `EMBED_BASE_URL` tetap ke Ollama |

- Profil (c) memakai kode yang sama (latihan 01–04 dan `python -m asisten`): hanya `base_url`, `api_key`, dan
  `model` yang berubah. Pertanyaan, hasil query, dan potongan dokumen **dikirim ke Anthropic** (di kit ini data
  dummy). Anthropic tidak menyediakan endpoint embedding, jadi `EMBED_BASE_URL` wajib menunjuk ke Ollama;
  `LOKAL_API_KEY` tidak pernah dikirim ke endpoint embedding (`EMBED_API_KEY`, default `ollama`).
- Temperature: `LOKAL_SUHU` (nama lama `SUHU` tetap dibaca, default 0.2) dan `CLOUD_SUHU` (default kosong). Kosong
  berarti temperature tidak dikirim; wajib untuk model Claude terbaru, yang menolak nilai di bawah 1 (error 400).

Contoh `.env` profil (b), dengan IP mentor 192.168.1.20 (`scripts/server_bersama.sh` mencetak blok ini dengan IP
yang benar):

```
DATABASE_URL=postgresql://erp_ai_readonly:baca_saja@192.168.1.20:5433/erp
DATABASE_URL_PESERTA=postgresql://erp_peserta:latihan_rag@192.168.1.20:5433/erp
LOKAL_BASE_URL=http://192.168.1.20:11434/v1
EMBED_BASE_URL=http://192.168.1.20:11434/v1
ERP_URL=http://192.168.1.20:8080
```

**Laptop mentor sebagai server bersama** (macOS, Ollama native agar memakai GPU):

```bash
scripts/server_bersama.sh --dry-run     # cek saja: Docker, Ollama (OLLAMA_HOST=0.0.0.0, konteks 8192), model, firewall
scripts/server_bersama.sh               # jalankan database + ERP, siapkan role peserta, cetak blok .env untuk peserta
python scripts/uji_beban.py --peserta 10 --base-url http://<IP mentor>:11434/v1   # uji kapasitas sebelum kelas
```

> **Peringatan keamanan.** Secara default port database (5433), ERP (8080), dan Ollama Docker (11434) hanya
> terbuka untuk laptop itu sendiri (`127.0.0.1`). Password admin database tertulis di kit ini, jadi siapa pun di
> jaringan yang sama bisa masuk sebagai superuser dan menjalankan perintah di container. Jangan mengisi
> `DB_BIND`, `ERP_BIND`, atau `OLLAMA_BIND` dengan `0.0.0.0` secara manual; biarkan `scripts/server_bersama.sh`
> melakukannya setelah password diganti, dan hanya di jaringan kelas yang Anda kendalikan.

Skrip ini aman dijalankan berulang, tanpa sudo, dan tidak menghapus data. Pengaturan Ollama, firewall, dan
container demo Hari 1 hanya ditampilkan sebagai perintah. Password `erp_admin` dan `erp_app` diganti acak
(disimpan di `.env` folder ERP), baru kemudian port dibuka ke jaringan (`DB_BIND`/`ERP_BIND=0.0.0.0`) dan
container dibuat ulang; peserta hanya mendapat `erp_ai_readonly` dan `erp_peserta`. `uji_beban.py` mengirim permintaan bersamaan (system prompt + skema tool
asli; `--agent` untuk agent loop lengkap) lalu mencetak latensi p50/p95/maks, token/detik, dan rekomendasi.

## Menjalankan

```bash
python -m web                                        # http://localhost:8000
python -m asisten "Bagaimana tren penjualan Biskuit Kelapa 3 bulan terakhir?"
python -m asisten --pengguna andi "Berapa HPP Roti Cokelat bulan ini?"
python -m asisten --detail --pengguna andi "..."     # tampilkan juga SQL dan hasil mentah setiap tool
python -m asisten --mode cloud "Kenapa HPP Roti Cokelat naik bulan ini?"   # lewat Claude Code
python scripts/evaluasi.py --model qwen3:8b          # skor akurasi model
python -m pytest -q
```

Pengguna contoh (simulasi login ERP):

| Kode | Nama | Jabatan | Hak akses |
|---|---|---|---|
| `andi` | Andi Pratama | Sales Supervisor | produk, penjualan, stok, dokumen, membuat SO |
| `sari` | Sari Wulandari | Finance & Accounting | produk, penjualan, HPP, piutang, dokumen |
| `budi` | Budi Santoso | Direktur Operasional | semua, termasuk membuat SO |

Aplikasi ERP punya enam akun (ditambah `dewi`, `agus`, `rudi`); hak aksesnya diatur di menu Pengaturan ERP.

## Latihan

| No | File | Topik | Waktu |
|---|---|---|---|
| 1 | `latihan/01_ngobrol.py` | Memanggil model lokal; melihat model mengarang | 5 menit |
| 2 | `latihan/02_tool_pertama.py` | Definisi tool (JSON Schema); model meminta tool | 15 menit |
| 3 | `latihan/03_agent_loop.py` | Agent loop: tool → hasil → jawaban | 20 menit |
| 4 | `latihan/04_rag.py` | Chunking, vector search pgvector, jawaban bersumber; bagian D: koleksi dokumen sendiri (`--koleksi <nama>`) | 20 menit (+15) |
| 5 | `latihan/05_pengaman.py` | Role read-only, hak akses di kode, prompt injection | 15 menit |
| 6 | `latihan/06_tool_sendiri.py` | Membuat tool baru dan memakainya di aplikasi web | 20 menit |
| 7 | `latihan/07_draft_so.py` | Agent penyiap draft sales order + konfirmasi user (butuh ERP berjalan) | ±30 menit |

Jalankan dari folder utama: `python latihan/01_ngobrol.py`. Solusi ada di `solusi/`; Latihan 6 sengaja tidak
punya `solusi/06_*.py`, contoh jawabannya `solusi/tools_tambahan_contoh.py`. Lembar kerja Sesi 2.3
(pertanyaan menjebak, cara membaca langkah agent dan SQL): `latihan/pertanyaan-menjebak.md`.

### Koleksi dokumen peserta (Sesi 2.4)

Indeks bersama (`rag.dokumen_chunk`, folder `dokumen/`) hanya diisi mentor. Peserta menambah dokumen ke
koleksinya sendiri, tabel `latihan.dokumen_<nama>`, lewat role `erp_peserta` (`DATABASE_URL_PESERTA`) yang hanya
bisa membuat tabel di schema `latihan`:

```bash
python -m asisten.rag ingest --koleksi andi          # folder dokumen-latihan/ -> latihan.dokumen_andi
python -m asisten.rag cari --koleksi andi "jadwal kirim ke Medan"
RAG_KOLEKSI=andi python -m asisten --pengguna andi "Jam berapa batas order agar dikirim besok ke Bandung?"
python -m asisten.rag hapus --koleksi andi
```

Dengan `RAG_KOLEKSI=<nama>` (di `.env` atau environment), tool `cari_dokumen` mencari di indeks bersama dan
koleksi itu sekaligus; setiap hasil diberi label koleksi serta nomor dokumennya. Semua peserta memakai role
`erp_peserta` yang sama, jadi koleksi dibedakan hanya oleh nama: `ingest` menolak menimpa koleksi yang sudah
ada (gunakan nama lain, atau `--timpa` bila koleksi itu milik Anda). Mode laptop sendiri tanpa
`DATABASE_URL_PESERTA` memakai koneksi admin.

### Draft sales order (Latihan 7)

Prinsipnya: **AI mengisi formulir → sistem ERP menghitung dan menegakkan aturan → manusia mengonfirmasi →
kode yang menyimpan.** Tool `siapkan_draft_so` hanya membaca view `ai` dan mengembalikan draft. Harga, diskon,
limit kredit, dan persetujuan dihitung oleh ERP (simulasi); user menekan Simpan di panel ERP atau menjawab `ya`
di Latihan 7; kode program yang memanggil API ERP dengan sesi login user itu (`ERP_URL`, `ERP_PASSWORD`).
Model tidak pernah diberi tool untuk menyimpan.

```bash
python latihan/07_draft_so.py ["permintaan"] [--pengguna andi] [--mode lokal|cloud] [--file path.txt] [--jawab ya|tidak]
python latihan/07_draft_so.py "Buatkan SO untuk Toko Murah Meriah: 40 pak Wafer Vanila dan 30 pak Keripik Singkong Balado"
python latihan/07_draft_so.py --file dokumen-uji/Email-PO-Swalayan-Sentosa.txt
```

ERP harus berjalan di `ERP_URL`. SO yang benar-benar disimpan di ERP bersama sebaiknya memakai produk non-demo
(Wafer Vanila, Keripik Singkong Balado), agar angka Biskuit Kelapa dan Teh Melati untuk demo dan evaluasi tidak
bergeser. Rekaman demo: `rekaman/demo-06a-draft-so.json` (Toko Murah Meriah, Faktur Terbit),
`demo-06b-draft-so-diskon.json` (Swalayan Sentosa + diskon 2%, Menunggu Persetujuan), `demo-06c-draft-so-ambigu.json`
("biskuit", asisten bertanya balik). Hanya `rekaman/demo-*.json` yang ikut git; rekaman otomatis lain (nama
berawalan tanggal, `REKAM=1`) tetap lokal. Batasan: pada `--mode cloud` (Claude Code lewat MCP) penyesuaian deskripsi tool
Latihan 7 tidak sampai ke proses MCP; pengguna khusus ERP (`dewi`, `agus`, `rudi`) tidak ada di `pengguna.py` kit.

## Model cloud (opsional)

Tombol **Cloud** dan menu **Bandingkan lokal vs cloud** memakai salah satu dari dua cara (`CLOUD_PENYEDIA` di `.env`):

**a. Claude Code — `claude-code` (default, tanpa API key).** Cukup Claude Code yang sudah login dengan
akun Claude Anda (`claude` → `/login`). Setiap pertanyaan menjalankan `claude -p` dengan system prompt
asisten yang sama dengan model lokal. Semua tool bawaan Claude Code (Bash, baca/tulis file, web) dimatikan,
server MCP lain dan CLAUDE.md tidak dipakai, dan satu-satunya tool adalah tools ERP lewat MCP
(`asisten/mcp_server.py`), jadi hak akses dan koneksi read-only tetap sama. Pilih model dengan
`CLOUD_MODEL` (`sonnet`, `opus`, `haiku`). Pemakaian dihitung ke kuota langganan masing-masing.

**b. API — `api`.** Isi `CLOUD_BASE_URL`, `CLOUD_MODEL`, `CLOUD_API_KEY` (endpoint apa pun yang kompatibel OpenAI).
Untuk model Claude, biarkan `CLOUD_SUHU` kosong (temperature tidak dikirim). Di workshop, Tantangan B dan Demo 3
(ERP di Docker) memakai cara ini dengan `CLOUD_MODEL=claude-haiku-5-5`.

Dalam mode cloud, pertanyaan dan hasil query dikirim ke penyedia model (di kit ini: data dummy).
Embedding dokumen RAG tetap lokal.

> Login langganan Claude ditujukan untuk pemakaian Claude Code oleh pemilik akun sendiri (belajar, demo,
> development). Untuk fitur AI di aplikasi yang dipakai klien, gunakan API key (cara b) atau model lokal.

### Memakai tools ERP dari sesi Claude Code Anda (opsional)

Tools yang sama bisa dipanggil langsung dari Claude Code interaktif lewat MCP. Dari folder kit, dengan
virtual environment aktif:

```bash
claude --mcp-config mcp-erp.json --strict-mcp-config --tools ""
ASISTEN_PENGGUNA=andi claude --mcp-config mcp-erp.json --strict-mcp-config --tools ""   # sebagai Andi
```

Windows PowerShell: `$env:ASISTEN_PENGGUNA="andi"` lalu jalankan perintah `claude` di atas.

`--tools ""` mematikan tool bawaan Claude Code. Tanpa itu, Claude Code bisa membaca `.env` lalu
menjalankan query langsung dengan akun admin, melewati hak akses di tools. Pengaman asisten hanya
sekuat tool paling longgar yang diberikan ke agent.

## Masalah umum

| Gejala | Solusi |
|---|---|
| `Model lokal tidak dapat dihubungi` | Buka aplikasi Ollama; cek `LOKAL_BASE_URL` |
| `Panjang konteks ... hanya 4.096 token` di `cek_setup.py` | Atur `OLLAMA_CONTEXT_LENGTH=8192` (lihat [Model lokal](#3-model-lokal)), buka ulang Ollama |
| Jawaban sangat lambat | Pastikan `LOKAL_REASONING_EFFORT=none`; tutup aplikasi berat; pakai server mentor |
| Server bersama lambat saat semua peserta bertanya | `python scripts/uji_beban.py`; praktik bergiliran per kelompok, atau sebagian kelompok pakai profil (c) |
| Peserta tidak bisa terhubung ke server mentor | Wi-Fi harus sama dan tanpa client isolation; izinkan Ollama/Docker di firewall Mac; jalankan `scripts/server_bersama.sh` (port baru dibuka ke jaringan setelah password diganti) |
| Error 400 terkait `temperature` di mode cloud | Kosongkan `LOKAL_SUHU` (atau `CLOUD_SUHU`) di `.env` |
| Embedding gagal di mode cloud | Isi `EMBED_BASE_URL` dengan Ollama (server mentor atau `http://localhost:11434/v1`) |
| Error terkait `reasoning_effort` pada model selain Qwen3 | Kosongkan `LOKAL_REASONING_EFFORT` |
| `Database tidak dapat dihubungi` | `docker compose up -d`; cek port 5433 dan `DATABASE_URL` |
| `relation "rag.dokumen_chunk" does not exist` | `python -m asisten.rag ingest` |
| `Schema 'latihan' belum ada` / akses ditolak saat `ingest --koleksi` | Mentor menjalankan `scripts/server_bersama.sh`; periksa `DATABASE_URL_PESERTA` |
| `Koleksi '...' sudah ada` | Pakai nama koleksi lain, atau `--timpa` bila koleksi itu milik Anda |
| `ERP belum bisa dipakai` di `cek_setup.py` | Hanya dibutuhkan Latihan 7: jalankan ERP, cek `ERP_URL` dan `ERP_PASSWORD` |
| Model menjawab tanpa memanggil tool | Wajar sesekali pada model kecil; perjelas deskripsi tool, ukur dengan `scripts/evaluasi.py` |
| Tombol **Cloud** tidak aktif | Instal Claude Code (perintah `claude` harus dikenali), atau `CLOUD_PENYEDIA=api` + isi `CLOUD_*` |
| `Claude Code belum login` | Jalankan `claude` di terminal lalu `/login` dengan akun Claude |
| `Batas pemakaian langganan Claude tercapai` | Tunggu kuota pulih, coba `CLOUD_MODEL=haiku`, atau pakai mode lokal |
| `Claude Code gagal menjalankan server tools ERP` | Cek database, lalu jalankan `python -m asisten.mcp_server` untuk melihat error-nya (Ctrl+C untuk keluar) |

## Catatan keamanan

- Asisten memakai role database `erp_ai_readonly`: hanya SELECT pada view schema `ai`, `rag`, dan koleksi
  peserta di `latihan`, tanpa hak membuat tabel (termasuk tabel sementara). Transaksi read-only dan batas waktu
  query 5 detik adalah setelan awal sesi: klien yang memegang password role ini bisa mengubahnya sendiri
  (`SET ...`), jadi yang benar-benar menahan penulisan adalah hak akses (GRANT) tadi.
- Role `erp_peserta` (ingest koleksi peserta) hanya bisa membuat tabel di schema `latihan`; tidak punya akses
  ke schema `erp`, `ai`, maupun `rag`.
- Di server bersama, password `erp_admin` dan `erp_app` diganti acak oleh `scripts/server_bersama.sh`.
- Hak akses dicek oleh kode setiap kali tool dijalankan (`asisten/agent.py` › `eksekusi_tool`).
- Password di proyek ini hanya untuk workshop. Ganti untuk lingkungan lain; jangan commit `.env`.
- Teks jawaban model di-escape sebelum ditampilkan di web (mencegah XSS).
- Mode cloud lewat Claude Code: tool bawaan Claude Code dimatikan dan server MCP lain diabaikan. Claude Code
  tetap menyisipkan email akun ke konteks model; system prompt melarang model menyebutnya di jawaban.

## Pihak ketiga

Chart.js 4.5.1 (lisensi MIT, `web/static/vendor/`) disertakan agar aplikasi berjalan tanpa internet.
