"""Koleksi RAG peserta (Sesi 2.4): validasi nama, query, dan pencarian tanpa model embedding sungguhan."""
import pytest

from asisten import config, db, rag, tools


@pytest.mark.parametrize("nama", ["andi", "tim_2", "Andi", " sari ", "a" * 30])
def test_nama_koleksi_valid(nama):
    assert rag.nama_koleksi(nama) == nama.strip().lower()


@pytest.mark.parametrize("nama", ["", "2tim", "andi-01", "andi.x", "a b", "../rag", "x;DROP TABLE", "a" * 31, "ändi"])
def test_nama_koleksi_ditolak(nama):
    with pytest.raises(ValueError):
        rag.nama_koleksi(nama)


def test_tabel_koleksi():
    assert rag.tabel_koleksi() == ("rag", "dokumen_chunk")
    assert rag.tabel_koleksi("andi") == ("latihan", "dokumen_andi")


def test_sql_cari():
    bersama = rag.sql_cari()
    assert '"rag"."dokumen_chunk"' in bersama and "UNION" not in bersama
    gabung = rag.sql_cari("andi")
    assert gabung.count("UNION ALL") == 1
    assert '"latihan"."dokumen_andi"' in gabung and "%(koleksi)s" in gabung
    with pytest.raises(ValueError):
        rag.sql_cari("andi; DROP TABLE rag.dokumen_chunk")
    # indeks lama tanpa kolom metadata tetap bisa digabung dengan koleksi baru
    lama = rag.sql_cari("andi", meta_bersama=False)
    assert lama.count("'' AS nomor") == 1 and lama.count("nomor, berlaku, bagian") == 2   # SELECT luar + koleksi


def test_metadata_ikut_setiap_potongan():
    potongan = rag.potong_dokumen(config.FOLDER_DOKUMEN / "02-Kebijakan-Harga-dan-Diskon.md")
    assert {(p["nomor"], p["berlaku"]) for p in potongan} == {("KBJ-PJL-002", "berlaku sejak 2 Januari 2026")}
    assert "KBJ-PJL-002" in rag.teks_untuk_embedding(potongan[0])
    assert rag.metadata_dokumen("# FAQ\n\nNomor dokumen: FAQ-TI-001 · Diperbarui: Agustus 2026\n\n## A\nisi") == \
        {"nomor": "FAQ-TI-001", "berlaku": "diperbarui Agustus 2026"}
    assert rag.metadata_dokumen("# Catatan\n\n## Bagian\nNomor dokumen: palsu") == {"nomor": "", "berlaku": ""}


def test_ingest_tidak_menimpa_koleksi_orang_lain(monkeypatch):
    monkeypatch.setattr(rag, "koleksi_ada", lambda nama: True)
    monkeypatch.setattr(rag, "embed", lambda teks: pytest.fail("embed tidak boleh dipanggil"))
    with pytest.raises(rag.KoleksiSudahAda, match="--timpa"):
        rag.ingest(rag.FOLDER_LATIHAN, koleksi="andi")


def test_koleksi_aktif_dan_url_ingest(monkeypatch):
    monkeypatch.delenv("RAG_KOLEKSI", raising=False)
    assert rag.koleksi_aktif() == ""
    monkeypatch.setenv("RAG_KOLEKSI", "Andi")
    assert rag.koleksi_aktif() == "andi"

    monkeypatch.delenv("DATABASE_URL_PESERTA", raising=False)
    assert rag.url_ingest() == config.DATABASE_URL_ADMIN
    assert rag.url_ingest("andi") == config.DATABASE_URL_ADMIN          # mode laptop sendiri
    monkeypatch.setenv("DATABASE_URL_PESERTA", "postgresql://erp_peserta:x@server:5433/erp")
    assert rag.url_ingest("andi").startswith("postgresql://erp_peserta")
    assert rag.url_ingest() == config.DATABASE_URL_ADMIN                # indeks bersama tetap admin


def test_dokumen_latihan_tanpa_readme():
    potongan = rag.kumpulkan_potongan(rag.FOLDER_LATIHAN)
    assert {p["sumber"] for p in potongan} == {"SOP Pengiriman Barang"}
    assert all(len(p["isi"]) <= rag.MAKS_KARAKTER for p in potongan)


def test_cari_dokumen_nama_koleksi_salah(monkeypatch):
    monkeypatch.setenv("RAG_KOLEKSI", "andi-01")
    monkeypatch.setattr(rag, "embed", lambda teks: pytest.fail("embed tidak boleh dipanggil"))
    assert "tidak valid" in tools.REGISTRY["cari_dokumen"].fungsi(pertanyaan="retur")["error"]


@pytest.fixture
def embed_palsu(monkeypatch, butuh_db):
    try:
        dimensi = db.query("SELECT vector_dims(embedding) AS d FROM rag.dokumen_chunk LIMIT 1")[0]["d"]
    except Exception:  # noqa: BLE001
        pytest.skip("Indeks RAG belum diisi (python -m asisten.rag ingest)")
    monkeypatch.setattr(rag, "embed", lambda teks: [[0.01] * dimensi for _ in teks])


def test_cari_tanpa_koleksi_tetap_sama(monkeypatch, embed_palsu):
    monkeypatch.delenv("RAG_KOLEKSI", raising=False)
    hasil = rag.cari("batas retur", k=3)
    assert len(hasil) == 3 and "koleksi" not in hasil[0]
    assert {"sumber", "nomor", "berlaku", "bagian", "isi", "skor"} <= set(hasil[0])


def test_cari_koleksi_belum_ada_memakai_indeks_bersama(monkeypatch, embed_palsu):
    monkeypatch.setenv("RAG_KOLEKSI", "belum_diingest_xyz")
    hasil = rag.cari("batas retur", k=2)
    assert len(hasil) == 2 and {h["koleksi"] for h in hasil} == {"bersama"}
    # koleksi="" memaksa hanya indeks bersama walau RAG_KOLEKSI diisi (Latihan 4 bagian D1)
    assert "koleksi" not in rag.cari("batas retur", k=1, koleksi="")[0]
