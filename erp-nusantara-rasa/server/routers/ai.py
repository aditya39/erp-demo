"""
Asisten AI di dalam ERP.

Alur keamanan:
  1. Identitas user diambil dari SESI LOGIN ERP (cookie), bukan dari isi request.
  2. Hak akses user di ERP disalin ke agent sebelum dijalankan, sehingga tool AI
     mengikuti izin yang sama (mis. izin "hpp" dicabut di menu Pengaturan -> tool HPP ditolak).
  3. Agent memakai koneksi database read-only miliknya sendiri (role erp_ai_readonly),
     bukan koneksi ERP (erp_app).
  4. Setiap pertanyaan dicatat di log aktivitas (siapa, kapan, tool apa).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import config, db
from ..sesi import wajib

from asisten import agent, pengguna as ai_pengguna, tools as ai_tools  # noqa: E402  (path dari config.ASISTEN_PATH)
from asisten import config as ai_config  # noqa: E402

router = APIRouter(prefix="/api/ai")
REKAM = os.getenv("ERP_REKAM", "1") == "1"
FOLDER_DEMO = ai_config.FOLDER_REKAMAN      # rekaman demo bawaan kit


def _selaraskan(u: dict) -> None:
    """Hak akses ERP -> hak akses agent (dict pengguna di paket asisten)."""
    ai_pengguna.PENGGUNA[u["kode"]] = {"nama": u["nama"], "jabatan": u["jabatan"], "izin": list(u["izin"])}


def _alasan_cloud() -> str:
    """Kenapa tombol Cloud tidak aktif (ditampilkan sebagai tooltip di panel)."""
    c = ai_config.CLOUD
    if c.aktif:
        return ""
    if c.penyedia == "claude-code":
        return ("Claude Code (perintah 'claude') tidak ada di server ERP ini, mis. di Docker. Isi CLOUD_PENYEDIA=api, "
                "CLOUD_BASE_URL, CLOUD_MODEL, dan CLOUD_API_KEY di kit/asisten-erp-ai/.env, atau jalankan ERP tanpa Docker.")
    return "CLOUD_BASE_URL dan CLOUD_MODEL belum diisi di kit/asisten-erp-ai/.env."


@router.get("/info")
def info(u: dict = Depends(wajib("ai"))) -> dict:
    return {
        "lokal": {"model": ai_config.LOKAL.model, "aktif": ai_config.LOKAL.aktif},
        "cloud": {"model": ai_config.CLOUD.model or "-", "aktif": ai_config.CLOUD.aktif, "alasan": _alasan_cloud()},
        "tools": [{"nama": t.nama, "izin": t.izin, "label_izin": ai_pengguna.NAMA_IZIN.get(t.izin, t.izin),
                   "boleh": t.izin in u["izin"], "deskripsi": t.deskripsi} for t in ai_tools.REGISTRY.values()],
        "maks_langkah": ai_config.MAKS_LANGKAH,
    }


class Permintaan(BaseModel):
    pesan: str
    mode: str = "lokal"
    riwayat: list[dict] = []


def _simpan_rekaman(u: dict, p: Permintaan, events: list[dict]) -> None:
    config.FOLDER_REKAMAN.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", p.pesan.lower())[:40].strip("-")
    nama = f"{dt.datetime.now():%Y%m%d-%H%M%S}-{p.mode}-{u['kode']}-{slug}.json"
    data = {"pesan": p.pesan, "pengguna": u["kode"], "mode": p.mode, "events": events}
    (config.FOLDER_REKAMAN / nama).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


@router.post("/chat")
def chat(p: Permintaan, u: dict = Depends(wajib("ai"))) -> StreamingResponse:
    if p.mode not in ("lokal", "cloud"):
        raise HTTPException(400, "mode harus lokal atau cloud")
    if not p.pesan.strip():
        raise HTTPException(400, "pertanyaan kosong")
    _selaraskan(u)

    def alir():
        t0 = time.perf_counter()
        rekam = []
        for ev in agent.jalankan(p.pesan.strip(), u["kode"], p.mode, p.riwayat):
            ev = {**ev, "t": int((time.perf_counter() - t0) * 1000)}
            rekam.append(ev)
            yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        tool = [f"{e['nama']}{'' if e['status'] == 'ok' else ' (' + e['status'] + ')'}" for e in rekam if e["tipe"] == "tool"]
        with db.koneksi() as conn:
            db.catat_audit(conn, u["kode"], "Asisten AI", f"Bertanya ({p.mode})", p.pesan.strip()[:120],
                           ", ".join(tool) or "tanpa tool")
        if REKAM:
            _simpan_rekaman(u, p, rekam)

    return StreamingResponse(alir(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _folder(sumber: str):
    return {"erp": config.FOLDER_REKAMAN, "demo": FOLDER_DEMO}.get(sumber)


@router.get("/rekaman")
def daftar_rekaman(u: dict = Depends(wajib("ai"))) -> list[dict]:
    hasil = []
    for sumber, pola in (("demo", "demo-*.json"), ("erp", "*.json")):
        folder = _folder(sumber)
        if not folder.exists():
            continue
        for f in sorted(folder.glob(pola), reverse=(sumber == "erp")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                durasi = next((e["durasi_ms"] for e in d["events"] if e["tipe"] == "selesai"), 0)
                hasil.append({"sumber": sumber, "file": f.name, "pesan": d["pesan"], "pengguna": d["pengguna"],
                              "mode": d["mode"], "durasi_ms": durasi})
            except (ValueError, KeyError):
                continue
    return hasil


@router.get("/rekaman/{sumber}/{nama}")
def ambil_rekaman(sumber: str, nama: str, u: dict = Depends(wajib("ai"))) -> dict:
    folder = _folder(sumber)
    if folder is None:
        raise HTTPException(404, "rekaman tidak ditemukan")
    path = (folder / nama).resolve()
    if path.parent != folder.resolve() or not path.exists():
        raise HTTPException(404, "rekaman tidak ditemukan")
    return json.loads(path.read_text(encoding="utf-8"))
