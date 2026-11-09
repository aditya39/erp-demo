"""
Aplikasi web contoh: layar ERP sederhana + panel Asisten AI.

  python -m web                 # buka http://localhost:8000
  python -m web --host 0.0.0.0  # agar bisa dibuka dari laptop lain di jaringan yang sama
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from asisten import agent, config, db, pengguna, tools
from asisten import format as fmt

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Asisten AI untuk ERP — contoh workshop")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info() -> dict:
    i = db.info()
    return {
        "perusahaan": i["nama_perusahaan"],
        "tanggal_posisi": i["tanggal_posisi"].isoformat(),
        "bulan_terakhir": fmt.bulan(i["bulan_terakhir"]),
        "lokal": {"model": config.LOKAL.label, "aktif": config.LOKAL.aktif},
        "cloud": {"model": config.CLOUD.label, "aktif": config.CLOUD.aktif, "penyedia": config.CLOUD.penyedia},
        "pengguna": [{"kode": k, "nama": v["nama"], "jabatan": v["jabatan"],
                      "izin": [pengguna.NAMA_IZIN[x] for x in v["izin"]]} for k, v in pengguna.PENGGUNA.items()],
        "tools": [{"nama": t.nama, "izin": t.izin} for t in tools.REGISTRY.values()],
    }


@app.get("/api/dashboard")
def dashboard(pengguna_kode: str = "budi") -> dict:
    i = db.info()
    akhir = i["bulan_terakhir"]
    lalu = fmt.tambah_bulan(akhir, -1)
    awal12 = fmt.tambah_bulan(akhir, -11)
    bulanan = db.query(
        """SELECT bulan, sum(nilai) AS nilai, count(DISTINCT nomor_faktur) AS faktur
           FROM ai.v_penjualan WHERE bulan BETWEEN %(a)s AND %(b)s GROUP BY bulan ORDER BY bulan""",
        {"a": awal12, "b": akhir})
    per_bln = {b["bulan"]: b for b in bulanan}
    kini, sebelum = per_bln.get(akhir.isoformat(), {}), per_bln.get(lalu.isoformat(), {})
    produk = db.query(
        """SELECT produk, kategori,
                  sum(qty) FILTER (WHERE bulan = %(b)s) AS qty,
                  sum(nilai) FILTER (WHERE bulan = %(b)s) AS nilai,
                  sum(qty) FILTER (WHERE bulan = %(l)s) AS qty_lalu
           FROM ai.v_penjualan WHERE bulan IN (%(b)s, %(l)s)
           GROUP BY produk, kategori ORDER BY nilai DESC NULLS LAST""",
        {"b": akhir, "l": lalu})
    for p in produk:
        p["nilai_fmt"] = fmt.rupiah(p["nilai"] or 0)
        p["perubahan"] = fmt.persen(fmt.ubah_persen(p["qty_lalu"] or 0, p["qty"] or 0))
    kartu = [
        {"label": f"Omzet {fmt.bulan(akhir)}", "nilai": fmt.rupiah(kini.get("nilai", 0)),
         "catatan": f"{fmt.persen(fmt.ubah_persen(sebelum.get('nilai', 0), kini.get('nilai', 0)))} dari bulan lalu"},
        {"label": "Jumlah faktur", "nilai": fmt.angka(kini.get("faktur", 0)), "catatan": fmt.bulan(akhir)},
        {"label": "Produk terlaris (nilai)", "nilai": produk[0]["produk"] if produk else "-",
         "catatan": produk[0]["nilai_fmt"] if produk else ""},
    ]
    if pengguna.punya_izin(pengguna_kode, "piutang"):
        piutang = db.query("""SELECT coalesce(sum(sisa), 0) AS sisa, count(*) AS faktur
                              FROM ai.v_piutang WHERE hari_lewat_jatuh_tempo > 0""")[0]
        kartu.append({"label": "Piutang lewat jatuh tempo", "nilai": fmt.rupiah(piutang["sisa"]),
                      "catatan": f"{piutang['faktur']} faktur"})
    else:
        kartu.append({"label": "Piutang lewat jatuh tempo", "nilai": "—", "catatan": "tidak ada akses", "terkunci": True})
    return {
        "judul_bulan": fmt.bulan(akhir),
        "kartu": kartu,
        "grafik": {"label": [fmt.bulan_pendek(b["bulan"]) for b in bulanan],
                   "data": [round(b["nilai"] / 1e6) for b in bulanan]},
        "produk": produk,
    }


class Permintaan(BaseModel):
    pesan: str
    pengguna: str = "budi"
    mode: str = "lokal"
    riwayat: list[dict] = []


def _simpan_rekaman(permintaan: Permintaan, events: list[dict]) -> None:
    config.FOLDER_REKAMAN.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", permintaan.pesan.lower())[:40].strip("-")
    nama = f"{dt.datetime.now():%Y%m%d-%H%M%S}-{permintaan.mode}-{permintaan.pengguna}-{slug}.json"
    data = {"pesan": permintaan.pesan, "pengguna": permintaan.pengguna, "mode": permintaan.mode, "events": events}
    (config.FOLDER_REKAMAN / nama).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


@app.post("/api/chat")
def chat(p: Permintaan) -> StreamingResponse:
    if p.pengguna not in pengguna.PENGGUNA:
        raise HTTPException(400, "pengguna tidak dikenal")
    if p.mode not in ("lokal", "cloud"):
        raise HTTPException(400, "mode harus lokal atau cloud")

    def alir():
        t0 = time.perf_counter()
        rekam = []
        for ev in agent.jalankan(p.pesan, p.pengguna, p.mode, p.riwayat):
            ev = {**ev, "t": int((time.perf_counter() - t0) * 1000)}
            rekam.append(ev)
            yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        if config.REKAM:
            _simpan_rekaman(p, rekam)

    return StreamingResponse(alir(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/rekaman")
def daftar_rekaman() -> list[dict]:
    if not config.FOLDER_REKAMAN.exists():
        return []
    hasil = []
    for f in sorted(config.FOLDER_REKAMAN.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            hasil.append({"file": f.name, "pesan": d["pesan"], "pengguna": d["pengguna"], "mode": d["mode"]})
        except (ValueError, KeyError):
            continue
    return hasil


@app.get("/api/rekaman/{nama}")
def ambil_rekaman(nama: str) -> dict:
    path = (config.FOLDER_REKAMAN / nama).resolve()
    if path.parent != config.FOLDER_REKAMAN.resolve() or not path.exists():
        raise HTTPException(404, "rekaman tidak ditemukan")
    return json.loads(path.read_text(encoding="utf-8"))
