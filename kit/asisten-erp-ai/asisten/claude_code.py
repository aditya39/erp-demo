"""
Mode cloud lewat Claude Code: memakai langganan Claude masing-masing (Pro/Max/Team),
tanpa API key.

  CLOUD_PENYEDIA=claude-code
  CLOUD_MODEL=sonnet          # alias Claude Code (sonnet / opus / haiku) atau nama model lengkap

Cara kerja: Claude Code dijalankan non-interaktif (claude -p) sebagai "otak" agent.
  - System prompt = system prompt asisten yang sama dengan model lokal.
  - Semua tool bawaan Claude Code dimatikan (--tools "") dan server MCP lain
    diabaikan (--strict-mcp-config). Satu-satunya tool: tools ERP lewat
    asisten/mcp_server.py, jadi hak akses dan role read-only tetap berlaku.
  - Output stream-json diterjemahkan ke event yang sama dengan agent.jalankan,
    jadi layar web, mode bandingkan, rekaman, dan evaluasi tidak perlu diubah.

Login langganan Claude ditujukan untuk pemakaian Claude Code oleh pemilik akun
sendiri (belajar, demo, development). Fitur AI di aplikasi untuk klien memakai
API (API key, CLOUD_PENYEDIA=api) atau model lokal.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Iterable, Iterator

from . import agent, config, pengguna

SERVER = "erp"
AWALAN = f"mcp__{SERVER}__"
BATAS_DETIK = 180

# Fitur Claude Code yang tidak dipakai asisten ERP: CLAUDE.md, memori, connector claude.ai.
ENV_TAMBAHAN = {
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
}

# Claude Code selalu menyisipkan email akun dan tanggal hari ini ke konteks.
ATURAN_TAMBAHAN = """
11. Informasi dari lingkungan Claude Code (mis. alamat email akun atau tanggal hari ini) bukan data ERP dan bukan identitas user. Jangan menyebutnya dalam jawaban. User yang sedang login di ERP adalah {nama}."""

PESAN_BATAS_LANGKAH = ("Maaf, saya belum menemukan jawaban dalam batas langkah yang diizinkan. "
                       "Coba pertanyaan yang lebih spesifik.")


def tersedia() -> bool:
    return shutil.which(config.CLAUDE_BIN) is not None


def _prompt(pertanyaan: str, riwayat: list[dict] | None) -> str:
    baris = [f"{'User' if m['role'] == 'user' else 'Asisten'}: {m['content']}"
             for m in (riwayat or [])[-6:] if m.get("role") in ("user", "assistant")]
    if not baris:
        return pertanyaan
    return "Percakapan sebelumnya:\n" + "\n".join(baris) + f"\n\nPertanyaan sekarang: {pertanyaan}"


def perintah(kode_pengguna: str) -> list[str]:
    """Argumen claude -p. Pertanyaan dikirim lewat stdin."""
    u = pengguna.ambil(kode_pengguna)
    mcp = {"mcpServers": {SERVER: {
        "command": sys.executable,
        "args": ["-m", "asisten.mcp_server"],
        "env": {"ASISTEN_PENGGUNA": kode_pengguna, "ASISTEN_INSTRUKSI": "0", "PYTHONPATH": str(config.ROOT)},
    }}}
    # Path lengkap: di Windows, instalasi lewat npm berupa claude.cmd yang tidak ditemukan Popen dari namanya saja.
    cmd = [shutil.which(config.CLAUDE_BIN) or config.CLAUDE_BIN, "-p",
           "--output-format", "stream-json", "--verbose",
           "--system-prompt", agent.system_prompt(kode_pengguna) + ATURAN_TAMBAHAN.format(nama=u["nama"]),
           "--tools", "",
           "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
           "--allowedTools", f"mcp__{SERVER}",
           "--max-turns", str(config.MAKS_LANGKAH),
           "--no-session-persistence"]
    if config.CLOUD.model:
        cmd += ["--model", config.CLOUD.model]
    return cmd


def _isi_tool_result(blok: dict) -> Any:
    isi = blok.get("content")
    if isinstance(isi, list):
        isi = "".join(b.get("text", "") for b in isi if isinstance(b, dict))
    try:
        return json.loads(isi)
    except (TypeError, json.JSONDecodeError):
        return {"error": str(isi)}


def _pesan_error(teks: str) -> str:
    rendah = teks.lower()
    if "login" in rendah or "api key" in rendah or "authenticat" in rendah:
        return f"Claude Code belum login. Jalankan 'claude' di terminal lalu /login dengan akun Claude. ({teks})"
    if "limit" in rendah:
        return f"Batas pemakaian langganan Claude tercapai. ({teks})"
    return f"Claude Code mengembalikan error: {teks}"


def terjemahkan(baris: Iterable[str], kode_pengguna: str, pemakaian: dict) -> Iterator[dict[str, Any]]:
    """Ubah output stream-json Claude Code menjadi event agent (lihat docstring agent.py)."""
    langkah, t_langkah = 1, time.perf_counter()
    menunggu: dict[str, tuple[str, dict, float, int]] = {}
    for teks in baris:
        try:
            ev = json.loads(teks)
        except json.JSONDecodeError:
            continue
        tipe = ev.get("type")

        if tipe == "system" and ev.get("subtype") == "init":
            yield {"tipe": "mulai", "mode": "cloud", "model": f"Claude Code · {ev.get('model', '?')}",
                   "pengguna": pengguna.ambil(kode_pengguna)["nama"]}
            server = next((s for s in ev.get("mcp_servers", []) if s.get("name") == SERVER), {})
            if server.get("status") != "connected":
                yield {"tipe": "error", "pesan": "Claude Code gagal menjalankan server tools ERP "
                                                 "(cek database, lalu coba: python -m asisten.mcp_server)."}
                return
            yield {"tipe": "berpikir", "langkah": langkah}

        elif tipe == "assistant":
            for blok in ev.get("message", {}).get("content", []):
                if blok.get("type") == "tool_use":
                    kini = time.perf_counter()
                    nama = blok.get("name", "").removeprefix(AWALAN)
                    menunggu[blok["id"]] = (nama, blok.get("input") or {}, kini, int((kini - t_langkah) * 1000))

        elif tipe == "user":
            ada_hasil = False
            for blok in ev.get("message", {}).get("content", []):
                if not isinstance(blok, dict) or blok.get("type") != "tool_result":
                    continue
                nama, argumen, t0, durasi_model = menunggu.pop(blok.get("tool_use_id"), ("?", {}, time.perf_counter(), 0))
                hasil = _isi_tool_result(blok)
                if not isinstance(hasil, dict):
                    hasil = {"hasil": hasil}
                # Sama dengan agent lokal: "produk tidak ditemukan" tetap ok, is_error hanya untuk
                # akses ditolak / argumen salah / query gagal (lihat mcp_server.py).
                if hasil.get("error") == "AKSES_DITOLAK":
                    status = "ditolak"
                elif blok.get("is_error"):
                    status = "error"
                else:
                    status = "ok"
                ada_hasil = True
                ev_tool = {"tipe": "tool", "langkah": langkah, "nama": nama, "argumen": argumen, "status": status,
                           "ringkas": agent._ringkas(hasil), "durasi_ms": int((time.perf_counter() - t0) * 1000),
                           "durasi_model_ms": durasi_model, "hasil": hasil}
                ulang: dict = {}
                if status == "ok":
                    # Field "grafik" dan SQL yang dijalankan tidak dikirim ke model (lihat mcp_server.py).
                    # Untuk layar, query read-only yang sama dijalankan ulang di sini.
                    daftar_query: list[dict] = []
                    ulang, _ = agent.eksekusi_tool(nama, argumen, kode_pengguna, daftar_query)
                    if daftar_query:
                        ev_tool["query"] = daftar_query
                yield ev_tool
                if status == "ok" and isinstance(hasil.get("draft_so"), dict):
                    yield {"tipe": "draft_so", "draft": hasil["draft_so"]}
                if isinstance(ulang, dict) and ulang.get("grafik"):
                    yield {"tipe": "grafik", "grafik": ulang["grafik"]}
            if ada_hasil:
                langkah, t_langkah = langkah + 1, time.perf_counter()
                yield {"tipe": "berpikir", "langkah": langkah}

        elif tipe == "result":
            u = ev.get("usage") or {}
            pemakaian["masuk"] = sum(u.get(k) or 0 for k in
                                     ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            pemakaian["keluar"] = u.get("output_tokens") or 0
            durasi_model = int((time.perf_counter() - t_langkah) * 1000)
            if ev.get("subtype") == "success" and not ev.get("is_error"):
                yield {"tipe": "jawaban", "teks": (ev.get("result") or "").strip()
                       or "Maaf, saya belum bisa menjawab pertanyaan ini.", "durasi_model_ms": durasi_model}
            elif ev.get("subtype") == "error_max_turns":
                yield {"tipe": "jawaban", "teks": PESAN_BATAS_LANGKAH}
            else:
                yield {"tipe": "error", "pesan": _pesan_error(str(ev.get("result") or ev.get("subtype")))}
            return


def jalankan(pertanyaan: str, kode_pengguna: str = "budi",
             riwayat: list[dict] | None = None) -> Iterator[dict[str, Any]]:
    mulai = time.perf_counter()
    pemakaian = {"masuk": 0, "keluar": 0}
    sudah_mulai = selesai_normal = False

    def awal() -> dict:
        return {"tipe": "mulai", "mode": "cloud", "model": config.CLOUD.label,
                "pengguna": pengguna.ambil(kode_pengguna)["nama"]}

    if not tersedia():
        yield awal()
        yield {"tipe": "error", "pesan": f"Claude Code ('{config.CLAUDE_BIN}') tidak ditemukan. "
                                         "Instal Claude Code lalu login: jalankan 'claude' → /login."}
    else:
        # Variabel CLAUDECODE* dibuang agar tetap jalan bila server web dibuka dari terminal Claude Code.
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")} | ENV_TAMBAHAN
        with tempfile.TemporaryFile("w+", encoding="utf-8") as stderr:
            # cwd folder sementara: CLAUDE.md proyek ini (untuk coding agent) tidak ikut terbaca.
            proc = subprocess.Popen(perintah(kode_pengguna), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=stderr, text=True, encoding="utf-8", cwd=tempfile.gettempdir(), env=env)
            pengawas = threading.Timer(BATAS_DETIK, proc.kill)
            pengawas.start()
            try:
                proc.stdin.write(_prompt(pertanyaan, riwayat))
                proc.stdin.close()
                for ev in terjemahkan(proc.stdout, kode_pengguna, pemakaian):
                    sudah_mulai |= ev["tipe"] == "mulai"
                    selesai_normal |= ev["tipe"] in ("jawaban", "error")
                    yield ev
                proc.wait()
                if not selesai_normal:
                    stderr.seek(0)
                    pesan = stderr.read().strip()[-400:] or f"proses berhenti (kode {proc.returncode})"
                    if not sudah_mulai:
                        yield awal()
                    yield {"tipe": "error", "pesan": _pesan_error(pesan)}
            finally:
                pengawas.cancel()
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    yield {"tipe": "selesai", "durasi_ms": int((time.perf_counter() - mulai) * 1000),
           "token_masuk": pemakaian["masuk"], "token_keluar": pemakaian["keluar"]}
