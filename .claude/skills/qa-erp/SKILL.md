---
name: qa-erp
description: Agent QA untuk ERP Nusantara Rasa. Menyusun skenario uji dari SOP diskon (KBJ-PJL-002), menjalankannya di browser lewat Playwright MCP, lalu melaporkan yang gagal sebagai issue GitHub berlabel bug-dari-qa. Pakai saat diminta menguji aturan diskon sales order.
argument-hint: "[dry-run] [lengkap] [url=http://localhost:8081]"
disable-model-invocation: true
---

# QA aturan diskon sales order

Kamu agent QA. Uji ERP **sebagai pengguna**, lewat browser. Jangan membaca kode di `erp-nusantara-rasa/`, `kit/asisten-erp-ai/asisten/`, atau `tests/`. Yang menjadi acuan hanya dokumen SOP dan apa yang terlihat di layar.

Argumen: `$ARGUMENTS`

- Berisi `dry-run` → **mode dry-run**: jangan menyentuh GitHub sama sekali. Laporan ditulis ke file di `qa-hasil/`.
- Berisi `lengkap` → jalankan 5 skenario. Tanpa itu, jalankan 3 skenario inti (untuk demo live).
- Berisi `url=...` → alamat ERP. Tanpa itu: `http://localhost:8081`.

## 1. Baca aturan

Baca `kit/asisten-erp-ai/dokumen/02-Kebijakan-Harga-dan-Diskon.md`, bagian **Diskon tambahan**. Catat nomor dokumennya (KBJ-PJL-002) untuk dirujuk di laporan.

## 2. Susun skenario

Turunkan skenario dari SOP. Tulis daftarnya dulu (tabel singkat: nomor, diskon tambahan, harapan) sebelum mulai menguji.

Tiga skenario inti, wajib, menguji batas diskon tambahan:

| No | Diskon tambahan | Harapan menurut SOP |
|---|---|---|
| S1 | 1,5% | Cukup Sales Supervisor → SO langsung **Faktur Terbit** |
| S2 | 2% | Di atas 1,5% → **Menunggu Persetujuan** Manajer Penjualan, faktur belum terbit |
| S3 | 3,5% | Di atas 3% → **ditolak**, tidak bisa disimpan |

Dengan argumen `lengkap`, tambahkan:

| No | Kasus | Harapan menurut SOP |
|---|---|---|
| S4 | Diskon tambahan 1% untuk customer yang punya faktur lewat jatuh tempo > 30 hari (lihat panel **Kredit customer**: "Tunggakan terlama" > 30 hari, mis. Swalayan Segar Jaya) | **Ditolak** |
| S5 | Tanpa diskon tambahan (0%) | Langsung **Faktur Terbit** |

## 3. Data uji

- Login sebagai **andi** (Andi Pratama, **Sales Supervisor**), password `demo123`. Di halaman login ada daftar "Akun demo", boleh klik langsung.
- Customer untuk S1, S2, S3, S5: customer Retail Modern di Jakarta yang **tunggakan terlamanya 0 hari** dan limit kreditnya masih longgar, misalnya **Swalayan Sentosa** (CUS-009). Pastikan di panel **Kredit customer** sebelum menyimpan. Kalau tidak bersih, pilih customer lain yang bersih dan sebutkan di laporan.
- Produk: satu baris saja, mis. **Biskuit Kelapa 200g** (BSK-001), qty 100. Tanggal dan gudang biarkan terisi otomatis.

## 4. Jalankan di browser (Playwright MCP)

Untuk setiap skenario:

1. Buka `<url>/penjualan/sales-order/baru`.
2. Pilih customer: klik kotak **Customer**, ketik nama di kolom pencarian, klik opsinya.
3. Isi **Diskon tambahan**: klik kolomnya, pilih semua isinya (`ControlOrMeta+a`), lalu ketik angkanya seperti pengguna biasa, mis. `1,5` (titik `1.5` juga diterima). Pastikan di snapshot kolom menampilkan nilai yang benar (mis. "1,5 %") sebelum lanjut.
4. Pilih produk di baris pertama, biarkan qty 100.
5. Tunggu panel **Pemeriksaan** di kanan diperbarui, lalu ambil snapshot. Catat teksnya ("Lolos semua pemeriksaan", "Akan berstatus ...", atau "Belum dapat disimpan").
6. Kalau tombol **Simpan sales order** aktif, klik. Halaman pindah ke detail SO. Catat **nomor SO** dan **status** yang tampil.
7. Ambil screenshot bukti: `browser_take_screenshot` dengan `filename` `qa-hasil/S<no>.png` (bukan fullPage).
8. Bandingkan hasil dengan harapan → **LULUS** atau **GAGAL**.

Jangan membuat lebih banyak SO dari yang dibutuhkan skenario. Kalau halaman macet lebih dari dua kali percobaan, catat skenario itu sebagai **TIDAK DAPAT DIUJI** beserta alasannya, lalu lanjut.

## 5. Laporkan yang GAGAL

Satu issue untuk setiap aturan yang dilanggar. Format isi issue:

```
## Ringkasan
<satu kalimat: apa yang salah>

## Langkah reproduksi
1. Login sebagai andi (Sales Supervisor)
2. Penjualan → Sales order → Baru
3. Customer: <nama>, produk: <produk> qty <qty>, diskon tambahan: <x>%
4. Klik Simpan sales order

## Hasil
<status yang tampil, nomor SO, nomor faktur kalau ada>

## Harapan
<status yang seharusnya>, sesuai KBJ-PJL-002 (Kebijakan Harga dan Diskon):
> <kutipan kalimat aturan dari SOP>

## Dampak
<satu-dua kalimat dampak bisnis>

## Bukti
<baris gambar dari unggah-bukti.sh, atau path file di dry-run>

## Lingkungan
ERP: <url> · diuji: <tanggal dan jam lokal dari perintah `date`> · oleh agent QA (Claude Code + Playwright MCP)
```

Judul: `[QA] <aturan yang dilanggar, singkat>`, mis. `[QA] SO diskon tambahan 2% langsung terbit faktur tanpa persetujuan Manajer Penjualan`.

**Mode biasa (GitHub):**
1. Cek duplikat: `gh issue list --label bug-dari-qa --state open --search "<kata kunci>"`. Kalau sudah ada issue yang sama, jangan membuat baru; sebutkan nomornya di ringkasan akhir.
2. Unggah screenshot: `./scripts/unggah-bukti.sh qa-hasil/S<no>.png`. Pakai baris Markdown yang dicetak skrip di bagian Bukti.
3. Tulis isi issue ke `qa-hasil/issue-S<no>.md`, lalu buat issue:
   `gh issue create --label bug-dari-qa --title "<judul>" --body-file qa-hasil/issue-S<no>.md`

**Mode dry-run:** jangan menjalankan `gh` dan jangan mengunggah. Tulis isi issue ke `qa-hasil/issue-S<no>.md` dengan baris pertama `# <judul>` dan bagian Bukti berisi path screenshot lokal.

## 6. Ringkasan akhir

Tutup dengan tabel: skenario, harapan, hasil, LULUS/GAGAL, nomor SO, issue (URL atau path file). Tulis juga ringkasannya ke `qa-hasil/ringkasan.md`. Tutup browser (`browser_close`).

## Batasan

- Hanya membuat sales order untuk skenario di atas. Jangan menyetujui, membatalkan, atau mengubah data lain.
- Jangan login sebagai user lain selain andi.
- Jangan memberi label selain `bug-dari-qa`. Label `siap-dikerjakan` adalah keputusan developer.
- Jangan membaca `.env` atau file kredensial apa pun.
