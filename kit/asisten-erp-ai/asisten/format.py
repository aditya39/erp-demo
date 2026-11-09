"""Format angka & tanggal gaya Indonesia. Angka diformat oleh kode, bukan oleh model."""
from __future__ import annotations

import datetime as dt

NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]


def _titik(n: float, desimal: int = 0) -> str:
    teks = f"{n:,.{desimal}f}"                      # 1,234,567.89
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


def angka(n: float, desimal: int = 0) -> str:
    return _titik(n, desimal)


def rupiah(n: float) -> str:
    """Rp 1.234.567 untuk angka kecil, Rp 2,45 miliar / Rp 281,2 juta untuk angka besar."""
    negatif = n < 0
    n = abs(n)
    if n >= 1e9:
        teks = f"Rp {_titik(n / 1e9, 2)} miliar"
    elif n >= 1e6:
        teks = f"Rp {_titik(n / 1e6, 1)} juta"
    else:
        teks = f"Rp {_titik(n, 0)}"
    return ("-" if negatif else "") + teks


def rupiah_selisih(n: float) -> str:
    """+Rp 505 / -Rp 4 / Rp 0"""
    if round(n) == 0:
        return "Rp 0"
    return ("+" if n > 0 else "-") + rupiah(abs(n))


def persen(n: float | None, tanda: bool = True) -> str:
    if n is None:
        return "-"
    teks = _titik(n, 1) + "%"
    return ("+" + teks) if tanda and n > 0 else teks


def ubah_persen(awal: float, akhir: float) -> float | None:
    if not awal:
        return None
    return round((akhir - awal) / awal * 100, 1)


def bulan(tanggal: str | dt.date) -> str:
    if isinstance(tanggal, str):
        tanggal = dt.date.fromisoformat(tanggal[:10])
    return f"{NAMA_BULAN[tanggal.month - 1]} {tanggal.year}"


def bulan_pendek(tanggal: str | dt.date) -> str:
    if isinstance(tanggal, str):
        tanggal = dt.date.fromisoformat(tanggal[:10])
    return f"{NAMA_BULAN[tanggal.month - 1][:3]} {str(tanggal.year)[2:]}"


def tambah_bulan(tanggal: dt.date, n: int) -> dt.date:
    y, m = divmod(tanggal.month - 1 + n, 12)
    return dt.date(tanggal.year + y, m + 1, 1)
