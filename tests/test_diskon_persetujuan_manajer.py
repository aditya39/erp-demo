"""
Unit test persetujuan Manajer Penjualan untuk diskon tambahan (Issue #2).

Sumber aturan: KBJ-PJL-002 (02-Kebijakan-Harga-dan-Diskon.md):
"Diskon tambahan sampai 1,5% cukup disetujui Sales Supervisor; di atas 1,5% sampai 3%
wajib disetujui Manajer Penjualan."
"""
from __future__ import annotations

import pytest

from server import logika

from .bantuan import hitungan


@pytest.mark.parametrize("diskon", [1.6, 2.0, 3.0])
def test_diskon_di_atas_1_5_sampai_3_persen_menunggu_persetujuan_manajer(erp, diskon):
    status, perlu, _ = logika.evaluasi_so(None, 1, hitungan(diskon))
    assert status == "Menunggu Persetujuan"
    assert [p["jenis"] for p in perlu] == ["diskon"]
    assert perlu[0]["peran"] == "Manajer Penjualan"
