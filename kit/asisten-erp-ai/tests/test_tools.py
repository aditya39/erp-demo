import psycopg
import pytest

from asisten import agent, db, tools


def jalankan(nama, **kw):
    hasil = tools.REGISTRY[nama].fungsi(**kw)
    hasil.pop("grafik", None)
    return hasil


def test_tren_penjualan(butuh_db):
    h = jalankan("tren_penjualan", produk="biskuit kelapa", bulan_terakhir=3)
    assert h["produk"] == "Biskuit Kelapa 200g"
    assert len(h["data"]) == 3
    assert h["ringkasan"]["perubahan_qty_persen"].startswith("+")


def test_produk_ambigu_dan_tidak_ada(butuh_db):
    assert "kandidat" in jalankan("tren_penjualan", produk="biskuit")
    assert "produk_tersedia" in jalankan("tren_penjualan", produk="nastar")


def test_rincian_hpp_roti_cokelat(butuh_db):
    h = jalankan("rincian_hpp", produk="roti coklat")
    assert h["produk"] == "Roti Cokelat"
    assert h["komponen_terbesar_perubahannya"][0]["komponen"] == "Bahan: Kakao bubuk"


def test_izin_dicek_oleh_kode(butuh_db):
    hasil, status = agent.eksekusi_tool("rincian_hpp", {"produk": "Roti Cokelat"}, "andi")
    assert status == "ditolak" and hasil["error"] == "AKSES_DITOLAK"
    _, status = agent.eksekusi_tool("rincian_hpp", {"produk": "Roti Cokelat"}, "sari")
    assert status == "ok"


def test_koneksi_asisten_read_only(butuh_db):
    with pytest.raises(psycopg.Error):
        db.query("SELECT * FROM erp.gaji_karyawan")
    with pytest.raises(psycopg.Error):
        db.query("UPDATE erp.produk SET harga_jual = 1")


def test_semua_tool_punya_izin_dan_deskripsi():
    for t in tools.REGISTRY.values():
        assert t.deskripsi and t.izin and t.parameter["type"] == "object"
