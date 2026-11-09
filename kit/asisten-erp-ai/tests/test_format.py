from asisten import format as fmt


def test_rupiah():
    assert fmt.rupiah(6750) == "Rp 6.750"
    assert fmt.rupiah(296_547_174) == "Rp 296,5 juta"
    assert fmt.rupiah(2_670_000_000) == "Rp 2,67 miliar"
    assert fmt.rupiah_selisih(505.3) == "+Rp 505"
    assert fmt.rupiah_selisih(-4) == "-Rp 4"


def test_persen_dan_bulan():
    assert fmt.persen(36.4) == "+36,4%"
    assert fmt.persen(-3.0) == "-3,0%"
    assert fmt.ubah_persen(100, 111.1) == 11.1
    assert fmt.bulan("2026-09-01") == "September 2026"
