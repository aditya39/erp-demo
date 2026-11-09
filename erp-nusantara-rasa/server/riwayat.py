"""Riwayat dokumen (timeline) untuk sales order & faktur, disusun dari data transaksi + log aktivitas."""
from __future__ import annotations

import datetime as dt

from . import db
from .logika import rp

WIB = dt.timezone(dt.timedelta(hours=7))


def _nama() -> dict[str, str]:
    m = {r["kode"]: r["nama"] for r in db.query("SELECT kode, nama FROM erp.pengguna")}
    m["sistem"] = "Sistem"
    return m


def _waktu(nilai) -> dt.datetime:
    if isinstance(nilai, dt.datetime):
        return nilai if nilai.tzinfo else nilai.replace(tzinfo=WIB)
    if isinstance(nilai, dt.date):
        return dt.datetime.combine(nilai, dt.time(12, 0), WIB)
    t = dt.datetime.fromisoformat(str(nilai))
    return t if t.tzinfo else t.replace(tzinfo=WIB)


def _ev(waktu, aktor: str, aksi: str, ket: str = "", jenis: str = "info", hanya_tanggal: bool = False) -> dict:
    return {"waktu": _waktu(waktu), "aktor": aktor, "aksi": aksi, "ket": ket, "jenis": jenis, "hanya_tanggal": hanya_tanggal}


def _selesai(ev: list[dict]) -> list[dict]:
    ev.sort(key=lambda e: e["waktu"])
    for e in ev:
        e["waktu"] = e["waktu"].isoformat(timespec="seconds")
    return ev


def _pembayaran(faktur_id: int, nama: dict[str, str]) -> list[dict]:
    rows = db.query("SELECT tanggal, jumlah, metode, referensi, dibuat_oleh FROM erp.pembayaran WHERE faktur_id = %s ORDER BY tanggal, id",
                    (faktur_id,))
    return [_ev(dt.date.fromisoformat(r["tanggal"]), nama.get(r["dibuat_oleh"], "Sari Wulandari") if r["dibuat_oleh"] != "migrasi" else "Sari Wulandari",
                "Mencatat pembayaran", f"{rp(r['jumlah'])} · {r['metode']}{' · ' + r['referensi'] if r['referensi'] else ''}",
                "bayar", hanya_tanggal=True) for r in rows]


def _audit(objek: list[str]) -> list[dict]:
    return db.query("""SELECT waktu, pengguna, aksi, objek, keterangan FROM erp.audit_log
                       WHERE objek = ANY(%s) ORDER BY waktu""", (objek,))


def riwayat_so(so: dict) -> list[dict]:
    nama = _nama()
    dibuat = so["dibuat_pada"]
    if so.get("sumber") == "asisten_ai":
        # urutan dijaga sort stabil: draft AI lebih dulu, lalu konfirmasi user (waktu simpan yang sama)
        ev = [_ev(dibuat, "Asisten AI", "Menyiapkan draft sales order",
                  f"Atas permintaan {so['dibuat_oleh_nama']} · harga, diskon, dan persetujuan dihitung sistem", "ai"),
              _ev(dibuat, so["dibuat_oleh_nama"], "Mengonfirmasi draft dan menyimpan sales order", rp(so["total"]), "buat")]
    else:
        ev = [_ev(dibuat, so["dibuat_oleh_nama"], "Membuat sales order", rp(so["total"]), "buat")]
    if so["persetujuan"]:
        kredit = any(p["jenis"] in ("credit_hold", "limit_kredit") for p in so["persetujuan"])
        ev.append(_ev(_waktu(dibuat) + dt.timedelta(seconds=1), "Sistem", "Menahan sales order" if kredit else "Meminta persetujuan",
                      ", ".join(p["judul"] for p in so["persetujuan"]), "tahan"))
    for p in so["persetujuan"]:
        if p.get("waktu"):
            ev.append(_ev(p["waktu"], p["oleh"], f"{'Menyetujui' if p['status'] == 'disetujui' else 'Menolak'}: {p['judul']}",
                          p.get("catatan") or "", "setuju" if p["status"] == "disetujui" else "tolak"))
    terbit = None
    for a in _audit([so["nomor"]] + ([so["nomor_faktur"]] if so.get("nomor_faktur") else [])):
        if a["aksi"] == "Membatalkan sales order":
            ev.append(_ev(a["waktu"], nama.get(a["pengguna"], a["pengguna"]), "Membatalkan sales order", a["keterangan"], "batal"))
        elif a["aksi"] == "Menerbitkan faktur":
            terbit = a
    if so.get("faktur_id"):
        if terbit:
            ev.append(_ev(terbit["waktu"], nama.get(terbit["pengguna"], terbit["pengguna"]), f"Menerbitkan faktur {so['nomor_faktur']}", "", "faktur"))
        else:
            ev.append(_ev(_waktu(dibuat) + dt.timedelta(minutes=3), "Sistem", f"Menerbitkan faktur {so['nomor_faktur']}", "", "faktur"))
        ev += _pembayaran(so["faktur_id"], nama)
    return _selesai(ev)


def riwayat_faktur(f: dict) -> list[dict]:
    nama = _nama()
    ev: list[dict] = []
    so = db.satu("""SELECT so.*, coalesce(pg.nama, so.dibuat_oleh) AS dibuat_oleh_nama, fk.nomor AS nomor_faktur
                    FROM erp.sales_order so LEFT JOIN erp.pengguna pg ON pg.kode = so.dibuat_oleh
                    LEFT JOIN erp.faktur fk ON fk.id = so.faktur_id WHERE so.id = %s""", (f["so_id"],)) if f.get("so_id") else None
    if so:
        return riwayat_so(so)
    ev.append(_ev(dt.date.fromisoformat(f["tanggal"]), "Sistem", f"Menerbitkan faktur {f['nomor']}", "", "faktur", True))
    ev += _pembayaran(f["id"], nama)
    return _selesai(ev)
