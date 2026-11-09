"""
LATIHAN 6 — Membuat tool sendiri                                      (±20 menit)

Tujuan
  Menambah kemampuan baru ke asisten, lalu memakainya dari aplikasi web.

Langkah
  1. Buka asisten/tools_tambahan.py dan tulis tool baru dengan dekorator @tool.
     Contoh pola lengkap: asisten/tools.py (lihat penjualan_teratas).
  2. Uji tool Anda dengan skrip ini:
        python latihan/06_tool_sendiri.py                       # cek tool terdaftar & bisa dijalankan
        python latihan/06_tool_sendiri.py "pertanyaan untuk asisten"
  3. Jalankan aplikasi web (python -m web) dan coba tanyakan dari panel Asisten AI.

Ide tool (pilih satu, atau buat ide sendiri):
  ┌────────────────────────────┬────────────────────────────────────────────┬─────────┐
  │ Ide                        │ View yang dipakai                          │ Izin    │
  ├────────────────────────────┼────────────────────────────────────────────┼─────────┤
  │ Stok di bawah minimum      │ ai.v_stok (kolom di_bawah_minimum)         │ stok    │
  │ Customer piutang terbesar  │ ai.v_piutang (sisa, hari_lewat_jatuh_tempo)│ piutang │
  │ Produk dengan margin       │ ai.v_hpp_bulanan + ai.v_produk (harga_jual)│ hpp     │
  │ terendah                   │                                            │         │
  │ Customer yang berhenti     │ ai.v_penjualan (tanggal faktur terakhir    │penjualan│
  │ membeli                    │ per customer)                              │         │
  │ Penjualan satu customer    │ ai.v_penjualan (customer, bulan)           │penjualan│
  └────────────────────────────┴────────────────────────────────────────────┴─────────┘

Aturan main tool yang baik
  - Deskripsi menjelaskan KAPAN tool dipakai (model membacanya).
  - Query berparameter (%(nama)s), hanya membaca view schema "ai".
  - Batasi jumlah baris (LIMIT) dan hitung angka/persen di kode, sertakan field *_fmt.
  - Tentukan izin yang sesuai.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asisten import agent, tools

BAWAAN = {"cari_produk", "tren_penjualan", "penjualan_teratas", "rincian_hpp",
          "riwayat_harga_bahan", "produk_pengguna_bahan", "cari_dokumen", "siapkan_draft_so"}

baru = [t for n, t in tools.REGISTRY.items() if n not in BAWAAN]
if not baru:
    print("Belum ada tool baru di asisten/tools_tambahan.py. Tulis tool Anda dulu (lihat petunjuk di atas).")
    sys.exit(1)

for t in baru:
    print(f"Tool baru terdaftar: {t.nama}  (izin: {t.izin})")
    print(f"   deskripsi: {t.deskripsi}")
    try:
        hasil = t.fungsi()
        hasil.pop("grafik", None)
        print("   uji tanpa argumen →", json.dumps(hasil, ensure_ascii=False, default=str)[:400])
    except TypeError:
        print("   (tool butuh argumen wajib; diuji lewat pertanyaan ke asisten)")

if len(sys.argv) > 1:
    pertanyaan = " ".join(sys.argv[1:])
    print(f"\nTanya: {pertanyaan}  (login sebagai budi)")
    for ev in agent.jalankan(pertanyaan, "budi"):
        if ev["tipe"] == "tool":
            print(f"   tool {ev['nama']}({ev['argumen']}) → {ev['status']}: {ev['ringkas']}")
        elif ev["tipe"] in ("jawaban", "error"):
            print(f"Jawab: {ev.get('teks') or ev.get('pesan')}")
