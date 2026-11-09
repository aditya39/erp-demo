"""Uji mode cloud lewat Claude Code tanpa menjalankan Claude Code (output stream-json palsu)."""
import json
import re

import anyio
import mcp_types as types

from asisten import agent, claude_code, mcp_server, tools

INIT = {"type": "system", "subtype": "init", "model": "claude-sonnet-5",
        "mcp_servers": [{"name": "erp", "status": "connected"}]}


def tool_use(id_, nama, argumen):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": id_, "name": f"mcp__erp__{nama}", "input": argumen}]}}


def tool_result(id_, hasil, is_error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": id_, "content": json.dumps(hasil), "is_error": is_error}]}}


def result(teks, subtype="success", is_error=False):
    return {"type": "result", "subtype": subtype, "is_error": is_error, "result": teks,
            "usage": {"input_tokens": 3, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 100,
                      "output_tokens": 20}}


def terjemahkan(events, pengguna="budi"):
    pemakaian = {}
    ev = list(claude_code.terjemahkan([json.dumps(e) for e in events], pengguna, pemakaian))
    return ev, pemakaian


def test_tool_grafik_lalu_jawaban(monkeypatch):
    monkeypatch.setattr(agent, "eksekusi_tool", lambda *a: ({"data": [], "grafik": {"judul": "G"}}, "ok"))
    ev, pakai = terjemahkan([INIT, tool_use("t1", "tren_penjualan", {"produk": "Biskuit Kelapa"}),
                             tool_result("t1", {"data": [1, 2, 3]}), result("Naik 36,4%.")])
    assert [e["tipe"] for e in ev] == ["mulai", "berpikir", "tool", "grafik", "berpikir", "jawaban"]
    assert ev[0]["model"] == "Claude Code · claude-sonnet-5"
    assert (ev[2]["nama"], ev[2]["status"], ev[2]["ringkas"]) == ("tren_penjualan", "ok", "3 baris data")
    assert ev[-1]["teks"] == "Naik 36,4%."
    assert pakai == {"masuk": 113, "keluar": 20}


def test_akses_ditolak_tanpa_grafik(monkeypatch):
    dipanggil = []
    monkeypatch.setattr(agent, "eksekusi_tool", lambda *a: dipanggil.append(a))
    ev, _ = terjemahkan([INIT, tool_use("t1", "rincian_hpp", {"produk": "Roti Cokelat"}),
                         tool_result("t1", {"error": "AKSES_DITOLAK", "pesan": "-"}, is_error=True),
                         result("Tidak ada akses.")], "andi")
    assert next(e for e in ev if e["tipe"] == "tool")["status"] == "ditolak"
    assert not dipanggil


def test_server_mcp_gagal_dan_belum_login():
    gagal = {**INIT, "mcp_servers": [{"name": "erp", "status": "failed"}]}
    assert [e["tipe"] for e in terjemahkan([gagal, result("x")])[0]] == ["mulai", "error"]
    ev, _ = terjemahkan([INIT, result("Not logged in · Please run /login", subtype="success", is_error=True)])
    assert "belum login" in ev[-1]["pesan"]


def test_batas_langkah():
    ev, _ = terjemahkan([INIT, result("", subtype="error_max_turns", is_error=True)])
    assert ev[-1] == {"tipe": "jawaban", "teks": claude_code.PESAN_BATAS_LANGKAH}


def test_mcp_server_memakai_tools_dan_hak_akses_yang_sama(monkeypatch):
    monkeypatch.setattr(mcp_server, "KODE_PENGGUNA", "andi")
    daftar = anyio.run(mcp_server.daftar_tool, None, None)
    assert {t.name for t in daftar.tools} == set(tools.REGISTRY)
    hasil = anyio.run(mcp_server.panggil_tool, None,
                      types.CallToolRequestParams(name="rincian_hpp", arguments={"produk": "Roti Cokelat"}))
    assert hasil.is_error and "AKSES_DITOLAK" in hasil.content[0].text


def test_perintah_hanya_tools_erp(butuh_db):
    cmd = claude_code.perintah("andi")
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in cmd
    mcp = json.loads(cmd[cmd.index("--mcp-config") + 1])
    assert mcp["mcpServers"]["erp"]["env"]["ASISTEN_PENGGUNA"] == "andi"
    assert "Andi Pratama" in cmd[cmd.index("--system-prompt") + 1]


def test_draft_so_dan_query_dari_hasil_mcp(monkeypatch):
    draft = {"customer": {"nama": "Toko Berkah Abadi"}, "item": [], "nilai_bruto_fmt": "Rp 0"}

    def ulang(nama, argumen, kode_pengguna, daftar_query=None):
        daftar_query.append({"sql": "SELECT 1 FROM ai.v_customer", "params": None})
        return {"status": "DRAFT_BELUM_DISIMPAN", "draft_so": draft}, "ok"

    monkeypatch.setattr(agent, "eksekusi_tool", ulang)
    ev, _ = terjemahkan([INIT, tool_use("t1", "siapkan_draft_so", {"customer": "Toko Berkah Abadi"}),
                         tool_result("t1", {"status": "DRAFT_BELUM_DISIMPAN", "draft_so": draft}),
                         result("Draft siap, silakan periksa.")], "andi")
    assert [e["tipe"] for e in ev] == ["mulai", "berpikir", "tool", "draft_so", "berpikir", "jawaban"]
    assert ev[2]["query"] == [{"sql": "SELECT 1 FROM ai.v_customer", "params": None}]
    assert ev[3] == {"tipe": "draft_so", "draft": draft}


def test_aturan_cloud_tidak_bentrok_dengan_aturan_asisten(butuh_db):
    prompt = claude_code.perintah("andi")
    teks = prompt[prompt.index("--system-prompt") + 1]
    nomor = [int(n) for n in re.findall(r"(?m)^(\d+)\. ", teks)]
    assert nomor == list(range(1, len(nomor) + 1))
