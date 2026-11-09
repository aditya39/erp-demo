"""Uji agent loop tanpa model sungguhan (model palsu yang jawabannya sudah ditentukan)."""
import dataclasses
import json
from types import SimpleNamespace as NS

from asisten import agent, config, db, llm


class ModelPalsu:
    def __init__(self, langkah):
        self.langkah = list(langkah)
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **_):
        isi = self.langkah.pop(0)
        if isinstance(isi, tuple):
            nama, argumen = isi
            tc = NS(id="c1", function=NS(name=nama, arguments=json.dumps(argumen)))
            msg = NS(content="", tool_calls=[tc])
        else:
            msg = NS(content=isi, tool_calls=None)
        return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=10, completion_tokens=5))


def jalankan(monkeypatch, langkah, pengguna="budi"):
    monkeypatch.setattr(llm, "buat_klien", lambda cfg: ModelPalsu(langkah))
    return list(agent.jalankan("pertanyaan uji", pengguna))


def test_loop_tool_lalu_jawaban(monkeypatch, butuh_db):
    ev = jalankan(monkeypatch, [("tren_penjualan", {"produk": "Biskuit Kelapa"}), "Naik 36,4%."])
    tipe = [e["tipe"] for e in ev]
    assert tipe.count("tool") == 1 and "grafik" in tipe
    assert next(e for e in ev if e["tipe"] == "jawaban")["teks"] == "Naik 36,4%."


def test_akses_ditolak_terlihat_di_langkah(monkeypatch, butuh_db):
    ev = jalankan(monkeypatch, [("rincian_hpp", {"produk": "Roti Cokelat"}), "Tidak ada akses."], "andi")
    assert next(e for e in ev if e["tipe"] == "tool")["status"] == "ditolak"


def test_tool_call_dalam_teks():
    teks = '<cari_dokumen>\n{"name": "cari_dokumen", "arguments": {"pertanyaan": "batas retur"}}\n</cari_dokumen>'
    assert agent._tool_call_dari_teks(teks)[0]["nama"] == "cari_dokumen"
    assert agent._tool_call_dari_teks("jawaban biasa") == []


def test_tool_call_dalam_teks_bersarang():
    teks = ('{"name": "siapkan_draft_so", "arguments": {"customer": "Toko Barokah", '
            '"item": [{"produk": "Teh Melati", "qty": 5}]}}')
    p = agent._tool_call_dari_teks(teks)[0]
    assert p["nama"] == "siapkan_draft_so" and json.loads(p["argumen"])["item"][0]["qty"] == 5


def test_pencatat_query_meringkas_parameter():
    assert db._ringkas_param({"v": "[" + ",".join(["0.1"] * 1024) + "]", "k": 4}) == {"v": "[…1024 dimensi]", "k": 4}
    assert db._ringkas_param("x" * 300).endswith("…") and db._ringkas_param(list(range(50))) == "[…50 nilai]"
    with db.catat_query() as luar:
        assert db._PENCATAT.get() is luar
    assert db._PENCATAT.get() is None


def test_event_tool_berisi_query_yang_tidak_dikirim_ke_model(monkeypatch, butuh_db):
    ev = jalankan(monkeypatch, [("tren_penjualan", {"produk": "Biskuit Kelapa", "bulan_terakhir": "3"}), "Naik."])
    tool = next(e for e in ev if e["tipe"] == "tool")
    assert tool["query"] and all(q["sql"].startswith("SELECT") and "  " not in q["sql"] for q in tool["query"])
    assert "query" not in tool["hasil"]
    ditolak = next(e for e in jalankan(monkeypatch, [("rincian_hpp", {"produk": "Roti Cokelat"}), "x"], "andi")
                   if e["tipe"] == "tool")
    assert "query" not in ditolak  # izin ditolak sebelum query apa pun dijalankan


def test_suhu_kosong_tidak_dikirim(monkeypatch):
    dikirim = []

    class Klien:
        chat = NS(completions=NS(create=lambda **kw: dikirim.append(kw) or NS(
            choices=[NS(message=NS(content="Halo.", tool_calls=None))], usage=None)))

    monkeypatch.setattr(llm, "buat_klien", lambda cfg: Klien())
    monkeypatch.setattr(agent, "system_prompt", lambda kode: "uji")
    for suhu in (None, 1.0):
        monkeypatch.setattr(config, "LOKAL", dataclasses.replace(config.LOKAL, suhu=suhu))
        list(agent.jalankan("halo", "budi"))
    assert "temperature" not in dikirim[0] and dikirim[1]["temperature"] == 1.0


def test_suhu_dari_environment(monkeypatch):
    for nama in ("LOKAL_SUHU", "SUHU", "CLOUD_SUHU"):
        monkeypatch.delenv(nama, raising=False)
    assert config._suhu("LOKAL_SUHU", "0.2", cadangan="SUHU") == 0.2
    monkeypatch.setenv("SUHU", "0.5")
    assert config._suhu("LOKAL_SUHU", "0.2", cadangan="SUHU") == 0.5
    monkeypatch.setenv("LOKAL_SUHU", "")
    assert config._suhu("LOKAL_SUHU", "0.2", cadangan="SUHU") is None
    assert config._suhu("CLOUD_SUHU") is None
    monkeypatch.setenv("CLOUD_SUHU", "1")
    assert config._suhu("CLOUD_SUHU") == 1.0


def test_suhu_lokal_default_mengikuti_endpoint(monkeypatch):
    for nama in ("LOKAL_SUHU", "SUHU"):
        monkeypatch.delenv(nama, raising=False)
    assert config._suhu_lokal("http://localhost:11434/v1") == 0.2
    assert config._suhu_lokal("https://api.anthropic.com/v1/") is None   # profil (c) tanpa LOKAL_SUHU
    monkeypatch.setenv("SUHU", "0.2")       # nama lama tetap dipakai apa adanya (cek_setup memberi tanda ✗)
    assert config._suhu_lokal("https://api.anthropic.com/v1/") == 0.2
    monkeypatch.setenv("LOKAL_SUHU", "1")
    assert config._suhu_lokal("https://api.anthropic.com/v1/") == 1.0
