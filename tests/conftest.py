"""
Konfigurasi pytest untuk unit test aturan bisnis ERP, tanpa database.

Fungsi di server/logika.py yang membaca database (kondisi_kredit, _margin_produk) diganti
dengan data palsu lewat fixture di bawah, jadi test cukup memanggil evaluasi_so().
"""
from __future__ import annotations

import os

# server.config membuat file .kunci-sesi bila variabel ini kosong; test tidak butuh file itu.
os.environ.setdefault("ERP_SESSION_SECRET", "kunci-untuk-test")

import pytest  # noqa: E402

from server import logika  # noqa: E402

from .bantuan import kredit  # noqa: E402


@pytest.fixture
def erp(monkeypatch):
    """Ganti akses database di logika.py. Atur kondisi lewat erp.kredit_customer dan erp.margin."""

    class Palsu:
        kredit_customer = kredit()
        margin = {1: 35.0}

    palsu = Palsu()
    monkeypatch.setattr(logika, "kondisi_kredit", lambda conn, customer_id: palsu.kredit_customer)
    monkeypatch.setattr(logika, "_margin_produk", lambda conn, produk_ids: palsu.margin)
    return palsu
