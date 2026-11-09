"""Uji tool siapkan_draft_so: draft SO dari permintaan user, tanpa pernah menyimpan."""
import json
import re
from pathlib import Path
from types import SimpleNamespace as NS

from asisten import agent, db, llm, tools, transaksi


def draft(**kw):
    return tools.REGISTRY["siapkan_draft_so"].fungsi(**kw)


def test_draft_normal(butuh_db):
    h = draft(customer="toko berkah abadi",
              item=[{"produk": "Biskuit Kelapa", "qty": 50}, {"produk": "teh melati", "qty": "20"}])
    assert h["status"] == "DRAFT_BELUM_DISIMPAN"
    d = h["draft_so"]
    assert d["customer"]["kode"] == "CUS-021" and d["customer"]["kota"] == "Jakarta"
    assert [(i["kode"], i["qty"]) for i in d["item"]] == [("BSK-001", 50), ("MNM-001", 20)]
    assert d["nilai_bruto"] == sum(i["qty"] * i["harga_daftar"] for i in d["item"])
    assert d["nilai_bruto_fmt"].startswith("Rp ")
    assert d["payload"] == {"customer_id": d["customer"]["id"], "gudang": "Gudang Jakarta", "diskon_tambahan": 0.0,
                            "catatan": "", "item": [{"produk_id": i["produk_id"], "qty": i["qty"]} for i in d["item"]]}
    assert "BELUM disimpan" in h["catatan"]


def test_ambigu_tidak_ada_dan_isian_salah(butuh_db):
    h = draft(customer="Toko Berkah Abadi", item=[{"produk": "biskuit", "qty": 30}])
    assert "error" in h and len(h["kandidat"]) == 3 and "draft_so" not in h
    h = draft(customer="Toko Berkah Abadi", item=[{"produk": "nastar", "qty": 5}])
    assert "tidak ditemukan" in h["error"] and "Biskuit Kelapa 200g" in h["kandidat"]
    h = draft(customer="Sentosa", item=[{"produk": "Teh Melati", "qty": 5}])
    assert "Swalayan Sentosa" in h["kandidat"] and "Toko Sentosa Abadi" in h["kandidat"]
    assert draft(customer="Koperasi Nelayan", item=[{"produk": "Teh Melati", "qty": 5}])["kandidat"] == []
    for item in ([], [{"produk": "Teh Melati", "qty": 0}], [{"produk": "Teh Melati", "qty": -3}],
                 [{"produk": "Teh Melati", "qty": "banyak"}]):
        h = draft(customer="Toko Berkah Abadi", item=item)
        assert "error" in h and h["kandidat"] == []


def test_gudang_otomatis_dan_stok(butuh_db):
    d = draft(customer="Toko Barokah", item=[{"produk": "Biskuit Kelapa", "qty": 10}])["draft_so"]
    assert (d["customer"]["kota"], d["gudang"], d["gudang_otomatis"]) == ("Surabaya", "Gudang Surabaya", True)
    h = draft(customer="Toko Barokah", item=[{"produk": "Biskuit Kelapa", "qty": 10}], gudang="jakarta")
    assert (h["draft_so"]["gudang"], h["draft_so"]["gudang_otomatis"]) == ("Gudang Jakarta", False)
    h = draft(customer="Toko Barokah", item=[{"produk": "Biskuit Kelapa", "qty": 999_999}])
    assert any("kurang dari" in p for p in h["peringatan"])


def test_bentuk_item_dari_model_kecil():
    harap = [{"produk": "Biskuit Kelapa", "qty": "50"}, {"produk": "Teh Melati", "qty": "20"}]
    assert transaksi._rapikan_item("50 pak Biskuit Kelapa dan 20 botol Teh Melati") == [
        {"produk": "Biskuit Kelapa", "qty": "50", "satuan": "pak"}, {"produk": "Teh Melati", "qty": "20", "satuan": "botol"}]
    assert transaksi._rapikan_item("5KARTON Wafer Vanila") == [{"produk": "Wafer Vanila", "qty": "5", "satuan": "karton"}]
    assert transaksi._rapikan_item([{"produk": "Wafer Vanila", "qty": 5, "unit": "dus"}]) == [
        {"produk": "Wafer Vanila", "qty": 5, "satuan": "dus"}]
    assert transaksi._rapikan_item('[{"produk": "Biskuit Kelapa", "qty": "50"}, {"nama": "Teh Melati", "jumlah": "20"}]') == harap
    assert transaksi._rapikan_item({"Biskuit Kelapa": 50}) == [{"produk": "Biskuit Kelapa", "qty": 50}]
    assert transaksi._rapikan_item({"produk": "Teh Melati", "qty": 5}) == [{"produk": "Teh Melati", "qty": 5}]
    assert transaksi._rapikan_item([["Teh Melati", 5]]) == [{"produk": "Teh Melati", "qty": 5}]
    assert [transaksi._qty(x) for x in ("50", "50 pak", "1.000", 20.0, 2.5, "-3", True)] == [50, 50, 1000, 20, None, -3, None]
    assert [transaksi._persen(x) for x in ("2", "2%", "2,5 %", None, "")] == [2.0, 2.0, 2.5, 0.0, 0.0]


def test_satuan_selain_satuan_produk_ditanyakan(butuh_db):
    # "5 karton Wafer Vanila" tidak boleh diam-diam menjadi 5 pak: sistem belum punya konversinya.
    for item, kata in [("5 karton Wafer Vanila", "karton"), ("Wafer Vanila 3 dus", "dus"),
                       ([{"produk": "Wafer Vanila", "qty": "2 lusin"}], "lusin"),
                       ([{"produk": "Wafer Vanila", "qty": 5, "satuan": "Karton"}], "karton"),
                       ([{"produk": "Wafer Vanila (box)", "qty": 5}], "box"),
                       ("5 pack Wafer Vanila", "pack"), ("5 botol Wafer Vanila", "botol")]:
        h = draft(customer="Toko Murah Meriah", item=item)
        assert "draft_so" not in h and h["kandidat"] == [], item
        assert h["error"] == (f"Satuan '{kata}' belum dikenal sistem untuk Wafer Vanila 150g (satuan: pak). "
                              "Tanyakan ke user jumlahnya dalam pak.")
    assert "satuan: pcs" in draft(customer="Toko Murah Meriah", item="6 bungkus Roti Keju")["error"]
    # Satuan produk sendiri (huruf besar/kecil, menempel angka, variasi) atau tanpa satuan: lolos.
    for item, harap in [("40 pak Wafer Vanila dan 30 PAK Keripik Singkong Balado", [40, 30]), ("40pak Wafer Vanila", [40]),
                        ("40 Wafer Vanila", [40]), ("20 btl Teh Melati", [20]), ("6 buah Roti Keju", [6]),
                        ([{"produk": "Teh Melati Botol 350ml", "qty": 20}], [20]),
                        ([{"produk": "Wafer Vanila", "qty": "40 pak", "satuan": "pak"}], [40])]:
        h = draft(customer="Toko Murah Meriah", item=item)
        assert [i["qty"] for i in h["draft_so"]["item"]] == harap, item


def test_produk_dan_customer_tidak_persis_cocok_ditanyakan(butuh_db):
    # Untuk draft transaksi, pencocokan yang hanya mirip (mis. kata "keju") ditanyakan balik, bukan diganti diam-diam.
    h = draft(customer="Toko Murah Meriah", item=[{"produk": "Nastar Keju", "qty": 5}])
    assert h == {"error": "Produk 'Nastar Keju' tidak persis cocok dengan katalog. Yang paling mirip: Roti Keju. "
                          "Tanyakan ke user apakah ini yang dimaksud.", "kandidat": ["Roti Keju"]}
    assert draft(customer="Toko Murah Meriah", item=[{"produk": "Roti Keju", "qty": 5}])["status"] == "DRAFT_BELUM_DISIMPAN"
    for teks, nama in [("Wafer Vanila", "Wafer Vanila 150g"), ("Keripik Singkong Balado", "Keripik Singkong Balado 100g"),
                       ("Biskuit Kelapa", "Biskuit Kelapa 200g"), ("biskuit coklat", "Biskuit Cokelat 200g"),
                       ("Teh Melati", "Teh Melati Botol 350ml"), ("kopi susu botol", "Kopi Susu Botol 250ml"),
                       ("roti tawar", "Roti Tawar Gandum"), ("Biskuit Kelapa 200 gram", "Biskuit Kelapa 200g"),
                       ("BSK-001", "Biskuit Kelapa 200g")]:
        assert draft(customer="Toko Murah Meriah", item=[{"produk": teks, "qty": 5}])["draft_so"]["item"][0]["nama"] == nama
    h = draft(customer="Toko Nusantara Jaya", item=[{"produk": "Wafer Vanila", "qty": 5}])
    assert "tidak persis cocok" in h["error"] and h["kandidat"] == ["Toko Makmur Jaya"]
    for teks in ("Toko Murah", "CUS-031", "Swalayan Sentosa, Jl. Diponegoro No. 141, Jakarta", "Swalayan Sentosa Jakarta"):
        assert draft(customer=teks, item=[{"produk": "Wafer Vanila", "qty": 5}])["status"] == "DRAFT_BELUM_DISIMPAN", teks


def test_rapikan_argumen_number_enum_dan_array():
    skema = tools.REGISTRY["siapkan_draft_so"].parameter
    item = [{"produk": "Teh Melati", "qty": "5"}]
    h = agent._rapikan_argumen(skema, {"customer": "Toko Barokah", "item": item, "gudang": "surabaya",
                                       "diskon_tambahan": "2,5%", "tidak_dikenal": 1})
    assert h == {"customer": "Toko Barokah", "item": item, "gudang": "Gudang Surabaya", "diskon_tambahan": 2.5}
    assert "gudang" not in agent._rapikan_argumen(skema, {"gudang": "Gudang Bandung"})


def test_hanya_membaca_view_ai(monkeypatch, butuh_db):
    # Jaminan "tidak menulis": semua query berupa SELECT ke view schema ai, lewat koneksi read-only.
    pakai_admin, asli = [], db.query

    def pantau(sql, params=None, admin=False):
        pakai_admin.append(admin)
        return asli(sql, params)

    monkeypatch.setattr(db, "query", pantau)
    daftar_query: list[dict] = []
    hasil, status = agent.eksekusi_tool("siapkan_draft_so", {"customer": "Toko Berkah Abadi",
                                        "item": [{"produk": "Wafer Vanila", "qty": 10}]}, "andi", daftar_query)
    assert status == "ok" and hasil["status"] == "DRAFT_BELUM_DISIMPAN"
    assert daftar_query and all(q["sql"].startswith("SELECT ") for q in daftar_query)
    assert all(set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+)\.", q["sql"])) == {"ai"} for q in daftar_query)
    assert pakai_admin and not any(pakai_admin)
    kode = Path(transaksi.__file__).read_text(encoding="utf-8").upper()
    assert not any(k in kode for k in ("INSERT ", "UPDATE ", "DELETE ", "URLOPEN", "ERP_API", "DATABASE_URL_ADMIN"))


def test_izin_so_buat_dicek_oleh_kode():
    hasil, status = agent.eksekusi_tool("siapkan_draft_so", {"customer": "Toko Barokah",
                                        "item": [{"produk": "Teh Melati", "qty": 5}]}, "sari")
    assert status == "ditolak" and hasil["error"] == "AKSES_DITOLAK"


class ModelPencatat:
    """Model palsu yang juga mencatat pesan yang dikirim ke model."""

    def __init__(self, langkah):
        self.langkah, self.pesan = list(langkah), []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, messages, **_):
        self.pesan.append(json.loads(json.dumps(messages, default=str)))
        isi = self.langkah.pop(0)
        if isinstance(isi, tuple):
            tc = NS(id="c1", function=NS(name=isi[0], arguments=json.dumps(isi[1])))
            msg = NS(content="", tool_calls=[tc])
        else:
            msg = NS(content=isi, tool_calls=None)
        return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=10, completion_tokens=5))


def test_loop_mengeluarkan_event_draft_so(monkeypatch, butuh_db):
    model = ModelPencatat([("siapkan_draft_so", {"customer": "Toko Berkah Abadi",
                                                 "item": [{"produk": "Biskuit Kelapa", "qty": 50}]}),
                           "Draft sudah saya siapkan. Silakan periksa lalu tekan Simpan."])
    monkeypatch.setattr(llm, "buat_klien", lambda cfg: model)
    ev = list(agent.jalankan("Buatkan SO untuk Toko Berkah Abadi: 50 pak Biskuit Kelapa", "andi"))
    tipe = [e["tipe"] for e in ev]
    i = tipe.index("tool")
    assert tipe[i + 1] == "draft_so"
    assert ev[i + 1]["draft"]["customer"]["kode"] == "CUS-021"
    assert ev[i]["query"] and ev[i]["ringkas"].endswith("belum disimpan")
    # Model melihat seluruh hasil tool (termasuk draft), tetapi tidak melihat SQL yang dicatat.
    isi_tool = next(m["content"] for m in model.pesan[1] if m["role"] == "tool")
    assert "DRAFT_BELUM_DISIMPAN" in isi_tool and "ai.v_customer" not in isi_tool
    assert "siapkan_draft_so" in model.pesan[0][0]["content"]  # aturan di system prompt


def test_riwayat_memilih_kandidat(monkeypatch, butuh_db):
    model = ModelPencatat([("siapkan_draft_so", {"customer": "Toko Barokah",
                                                 "item": [{"produk": "Biskuit Kelapa", "qty": 30}]}), "Draft siap."])
    monkeypatch.setattr(llm, "buat_klien", lambda cfg: model)
    riwayat = [{"role": "user", "content": "Buatkan SO untuk Toko Barokah: 30 pak biskuit"},
               {"role": "assistant", "content": "Biskuit yang mana: Cokelat, Kelapa, atau Susu?", "draft": None}]
    ev = list(agent.jalankan("Biskuit Kelapa", "andi", riwayat=riwayat))
    assert "draft_so" in [e["tipe"] for e in ev]
    assert model.pesan[0][1:3] == [{"role": "user", "content": riwayat[0]["content"]},
                                   {"role": "assistant", "content": riwayat[1]["content"]}]
