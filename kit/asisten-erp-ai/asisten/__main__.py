"""
Tanya asisten dari terminal.

  python -m asisten "Bagaimana tren penjualan Biskuit Kelapa 3 bulan terakhir?"
  python -m asisten --pengguna andi "Berapa HPP Roti Cokelat bulan ini?"
  python -m asisten --mode cloud "..."
  python -m asisten --detail "..."      # tampilkan juga SQL dan hasil mentah setiap tool
  python -m asisten --pengguna andi "Buatkan SO untuk Toko Murah Meriah: 40 pak Wafer Vanila"
"""
from __future__ import annotations

import argparse
import json

from . import agent, pengguna
from . import format as fmt

PESAN_DRAFT = "Draft belum disimpan. Simpan lewat aplikasi ERP atau jalankan latihan/07_draft_so.py."


def cetak_draft(d: dict, peringatan: list[str]) -> None:
    """Ringkasan draft sales order yang mudah dibaca (draft TIDAK disimpan oleh asisten)."""
    c = d["customer"]
    print("      ┌ Draft sales order (BELUM disimpan)")
    print(f"      │ Customer : {c['nama']} ({c['kode']}) · {c['segmen']} · {c['kota']} · termin {c['termin_hari']} hari")
    print(f"      │ Gudang   : {d['gudang']}" + (" (otomatis dari kota customer)" if d.get("gudang_otomatis") else ""))
    for i, x in enumerate(d["item"]):
        print(f"      │ {'Item' if i == 0 else '':<9}: {fmt.angka(x['qty'])} {x['satuan']} {x['nama']} × "
              f"{x['harga_daftar_fmt']} = Rp {fmt.angka(x['qty'] * x['harga_daftar'])}")
    print(f"      │ Bruto    : {d['nilai_bruto_fmt']} (harga daftar, sebelum diskon; harga akhir dihitung ERP)")
    if d.get("diskon_tambahan"):
        print(f"      │ Diskon tambahan: {fmt.angka(d['diskon_tambahan'], 1)}%")
    if d.get("catatan"):
        print(f"      │ Catatan  : {d['catatan']}")
    for p in peringatan:
        print(f"      │ ⚠ {p}")
    print("      └" + "─" * 40)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pertanyaan")
    ap.add_argument("--pengguna", default="budi", choices=list(pengguna.PENGGUNA))
    ap.add_argument("--mode", default="lokal", choices=["lokal", "cloud"])
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    ada_draft, peringatan = False, []
    for ev in agent.jalankan(args.pertanyaan, args.pengguna, args.mode):
        t = ev["tipe"]
        if t == "mulai":
            print(f"» {ev['pengguna']} · model {ev['mode']} ({ev['model']})")
        elif t == "berpikir":
            print(f"  [{ev['langkah']}] model memutuskan…")
        elif t == "tool":
            tanda = {"ok": "✓", "ditolak": "✗ DITOLAK", "error": "✗ ERROR"}[ev["status"]]
            print(f"      {tanda} {ev['nama']}({json.dumps(ev['argumen'], ensure_ascii=False)}) "
                  f"→ {ev['ringkas']} · {ev['durasi_ms']} ms")
            if args.detail:
                for q in ev.get("query", []):
                    print(f"        SQL: {q['sql']}"
                          + (f"  · params {json.dumps(q['params'], ensure_ascii=False, default=str)}" if q["params"] else ""))
                print("        " + json.dumps(ev["hasil"], ensure_ascii=False, indent=2).replace("\n", "\n        "))
            peringatan = ev["hasil"].get("peringatan") or []
        elif t == "draft_so":
            ada_draft = True
            cetak_draft(ev["draft"], peringatan)
        elif t == "grafik":
            print(f"      grafik: {ev['grafik']['judul']}")
        elif t == "jawaban":
            print("\n" + ev["teks"] + "\n")
        elif t == "error":
            print(f"\n[ERROR] {ev['pesan']}\n")
        elif t == "selesai":
            if ada_draft:
                print(f"  {PESAN_DRAFT}")
            print(f"  selesai dalam {ev['durasi_ms'] / 1000:.1f} dtk · token masuk {ev['token_masuk']} "
                  f"· token keluar {ev['token_keluar']}")


if __name__ == "__main__":
    main()
