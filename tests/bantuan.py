"""Data contoh untuk unit test aturan sales order."""
from __future__ import annotations


def kredit(**ubah) -> dict:
    """Kondisi kredit customer yang sehat (tanpa tunggakan, limit masih longgar)."""
    dasar = {
        "limit_kredit": 300_000_000.0,
        "piutang": 50_000_000.0,
        "lewat_jatuh_tempo": 0.0,
        "sisa_limit": 250_000_000.0,
        "pemakaian_persen": 16.7,
        "hari_lewat_maks": 0,
        "tahap": "Lancar",
        "credit_hold": False,
        "boleh_diskon_tambahan": True,
    }
    dasar.update(ubah)
    return dasar


def hitungan(diskon_tambahan: float, total: float = 10_000_000.0) -> dict:
    """Hasil hitung_so() untuk satu produk; cukup untuk evaluasi_so()."""
    return {
        "customer": {"id": 1, "nama": "PT Contoh Retail", "segmen": "Retail Modern", "termin_hari": 30},
        "diskon_standar": 6.0,
        "diskon_tambahan": diskon_tambahan,
        "item": [{"produk_id": 1, "kode": "BSK-001", "nama": "Biskuit Kelapa", "qty": 100}],
        "total": total,
    }
