"""
Unit test aturan sales order (server/logika.py, fungsi evaluasi_so).

Sumber aturan: kit/asisten-erp-ai/dokumen/02-Kebijakan-Harga-dan-Diskon.md (KBJ-PJL-002)
dan 03-Kebijakan-Kredit-dan-Penagihan.md (KBJ-KEU-004).
"""
from __future__ import annotations

import pytest

from server import logika

from .bantuan import hitungan, kredit


def test_tanpa_diskon_tambahan_faktur_langsung_terbit(erp):
    status, perlu, peringatan = logika.evaluasi_so(None, 1, hitungan(0))
    assert status == "Faktur Terbit"
    assert perlu == []
    assert peringatan == []


def test_diskon_tambahan_tepat_batas_supervisor_tidak_perlu_persetujuan(erp):
    # KBJ-PJL-002: diskon tambahan sampai 1,5% cukup disetujui Sales Supervisor (pembuat SO).
    status, perlu, _ = logika.evaluasi_so(None, 1, hitungan(1.5))
    assert status == "Faktur Terbit"
    assert perlu == []


def test_diskon_tambahan_di_atas_3_persen_ditolak(erp):
    with pytest.raises(logika.AturanBisnis, match="maksimal 3%"):
        logika.evaluasi_so(None, 1, hitungan(3.5))


def test_diskon_tambahan_negatif_ditolak(erp):
    with pytest.raises(logika.AturanBisnis, match="negatif"):
        logika.evaluasi_so(None, 1, hitungan(-1))


def test_customer_menunggak_lebih_30_hari_tidak_boleh_diskon_tambahan(erp):
    erp.kredit_customer = kredit(hari_lewat_maks=45, boleh_diskon_tambahan=False)
    with pytest.raises(logika.AturanBisnis, match="lewat jatuh tempo 45 hari"):
        logika.evaluasi_so(None, 1, hitungan(1.0))


def test_produk_margin_di_bawah_20_persen_tidak_boleh_diskon_tambahan(erp):
    erp.margin = {1: 15.0}
    with pytest.raises(logika.AturanBisnis, match="margin kotor < 20%"):
        logika.evaluasi_so(None, 1, hitungan(1.0))


def test_melebihi_limit_kredit_ditahan_menunggu_finance(erp):
    erp.kredit_customer = kredit(limit_kredit=40_000_000.0, piutang=35_000_000.0)
    status, perlu, _ = logika.evaluasi_so(None, 1, hitungan(0, total=10_000_000.0))
    assert status == "Ditahan"
    assert [p["jenis"] for p in perlu] == ["limit_kredit"]
    assert perlu[0]["peran"] == "Divisi Finance"


def test_tunggakan_lebih_60_hari_credit_hold(erp):
    erp.kredit_customer = kredit(hari_lewat_maks=75, tahap="Credit hold", credit_hold=True,
                                 boleh_diskon_tambahan=False)
    status, perlu, _ = logika.evaluasi_so(None, 1, hitungan(0))
    assert status == "Ditahan"
    assert perlu[0]["jenis"] == "credit_hold"
    assert perlu[0]["status"] == "menunggu"
