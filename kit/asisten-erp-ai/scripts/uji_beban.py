#!/usr/bin/env python3
"""
Uji beban server model bersama: N peserta simulasi mengirim permintaan BERSAMAAN.
Jalankan sebelum kelas (dari laptop mentor atau laptop peserta) untuk memutuskan berapa
peserta per server, atau kapan memakai cadangan cloud.

  python scripts/uji_beban.py                                   # 5 peserta × 2 permintaan, model di .env
  python scripts/uji_beban.py --peserta 15 --ulang 3
  python scripts/uji_beban.py --base-url http://192.168.1.20:11434/v1 --model qwen3:8b
  python scripts/uji_beban.py --agent --peserta 5               # agent loop lengkap (tool sungguhan)

Mode default: satu langkah keputusan agent (system prompt + skema semua tool asli), tanpa
menjalankan tool. Langkah inilah yang paling sering dikirim ke model saat praktik.
Mode --agent: agent.jalankan penuh (tool ke database, beberapa langkah model) sebagai budi.
"""
from __future__ import annotations

import argparse
import dataclasses
import math
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

from asisten import agent, config, llm, tools  # noqa: E402

PERTANYAAN = [
    "Bagaimana tren penjualan Biskuit Kelapa 3 bulan terakhir?",
    "Kenapa HPP Roti Cokelat naik bulan ini?",
    "Siapa 5 customer dengan penjualan terbesar 3 bulan terakhir?",
    "Customer mana yang piutangnya lewat jatuh tempo lebih dari 60 hari?",
    "Siapa yang menyetujui diskon tambahan 2%?",
    "Berapa lama batas waktu retur roti yang rusak?",
    "Produk apa yang stoknya di bawah minimum?",
    # Produk non-demo: SO latihan di ERP bersama tidak boleh menggeser angka Biskuit Kelapa / Teh Melati.
    "Buatkan SO untuk Toko Murah Meriah: 40 pak Wafer Vanila dan 30 pak Keripik Singkong Balado",
]


def persentil(data: list[float], p: float) -> float:
    urut = sorted(data)
    return urut[max(0, math.ceil(p * len(urut)) - 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--peserta", type=int, default=5, help="jumlah peserta simulasi bersamaan (default 5)")
    ap.add_argument("--ulang", type=int, default=2, help="permintaan per peserta, berurutan (default 2)")
    ap.add_argument("--model", default=config.LOKAL.model, help=f"default dari .env: {config.LOKAL.model}")
    ap.add_argument("--base-url", default=config.LOKAL.base_url, help=f"default dari .env: {config.LOKAL.base_url}")
    ap.add_argument("--agent", action="store_true", help="jalankan agent loop lengkap (butuh database)")
    args = ap.parse_args()

    # API key dari .env hanya dikirim ke endpoint .env itu sendiri (mis. cadangan cloud), tidak ke server lain.
    api_key = config.LOKAL.api_key if args.base_url == config.LOKAL.base_url else "ollama"
    cfg = dataclasses.replace(config.LOKAL, base_url=args.base_url, model=args.model, api_key=api_key)
    suhu = getattr(cfg, "suhu", None)
    opsi = llm.opsi_tambahan(cfg) | ({"temperature": suhu} if suhu is not None else {})
    klien = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key or "kosong", timeout=300, max_retries=0)

    try:
        system = agent.system_prompt("budi")
    except Exception as e:  # noqa: BLE001
        if args.agent:
            raise SystemExit(f"Mode --agent butuh database: {str(e).splitlines()[0]}")
        print(f"(Database tidak terhubung, memakai system prompt pengganti: {str(e).splitlines()[0][:80]})")
        system = "Kamu adalah Asisten AI di aplikasi ERP. Gunakan tool untuk data dan kebijakan. " * 20
    skema = tools.semua_skema()
    if args.agent:
        config.LOKAL = cfg  # agent.jalankan(mode="lokal") membaca config.LOKAL: arahkan ke server yang diuji

    total = args.peserta * args.ulang
    mode = "agent loop lengkap" if args.agent else f"langkah keputusan ({len(skema)} tool)"
    print(f"Uji beban: {args.peserta} peserta × {args.ulang} permintaan = {total} · model {cfg.model} "
          f"di {cfg.base_url} · {mode}\n")

    hasil: list[dict] = []
    kunci = threading.Lock()
    mulai_bersama = threading.Barrier(args.peserta)

    def satu_permintaan(pertanyaan: str) -> dict:
        t0 = time.perf_counter()
        if args.agent:
            r = {"token_masuk": 0, "token_keluar": 0, "tool": []}
            for ev in agent.jalankan(pertanyaan, "budi", "lokal"):
                if ev["tipe"] == "tool":
                    r["tool"].append(ev["nama"])
                elif ev["tipe"] == "error":
                    r["error"] = ev["pesan"]
                elif ev["tipe"] == "selesai":
                    r.update(token_masuk=ev["token_masuk"], token_keluar=ev["token_keluar"])
        else:
            resp = klien.chat.completions.create(
                model=cfg.model, tools=skema, **opsi,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": pertanyaan}])
            msg = resp.choices[0].message
            r = {"token_masuk": getattr(resp.usage, "prompt_tokens", 0) or 0,
                 "token_keluar": getattr(resp.usage, "completion_tokens", 0) or 0,
                 "tool": [tc.function.name for tc in (msg.tool_calls or [])]}
        r["detik"] = time.perf_counter() - t0
        return r

    def peserta(no: int) -> None:
        mulai_bersama.wait()
        for i in range(args.ulang):
            q = PERTANYAAN[(no * args.ulang + i) % len(PERTANYAAN)]
            try:
                r = satu_permintaan(q)
            except Exception as e:  # noqa: BLE001  (timeout, koneksi, error model)
                r = {"detik": None, "error": f"{type(e).__name__}: {str(e).splitlines()[0][:100]}"}
            with kunci:
                hasil.append(r)
                status = f"✗ {r['error']}" if r.get("error") else \
                    ("✓ tool " + ", ".join(r["tool"]) if r["tool"] else "✓ tanpa tool")
                waktu = f"{r['detik']:6.1f} dtk" if r.get("detik") is not None else "      -   "
                print(f"  [{len(hasil):>3}/{total}] peserta {no + 1:>2} #{i + 1} {waktu}  {status}")

    t_mulai = time.perf_counter()
    utas = [threading.Thread(target=peserta, args=(n,)) for n in range(args.peserta)]
    for t in utas:
        t.start()
    for t in utas:
        t.join()
    durasi = time.perf_counter() - t_mulai

    berhasil = [r for r in hasil if not r.get("error")]
    gagal = len(hasil) - len(berhasil)
    print(f"\nHasil: {len(berhasil)} berhasil, {gagal} gagal · durasi total {durasi:.1f} dtk")
    if not berhasil:
        print("Rekomendasi: semua permintaan gagal. Periksa alamat server (--base-url), model, dan jaringan.")
        sys.exit(1)

    lat = [r["detik"] for r in berhasil]
    rata = sum(lat) / len(lat)
    p50, p95 = persentil(lat, 0.5), persentil(lat, 0.95)
    print(f"Latensi per permintaan: p50 {p50:.1f} dtk · p95 {p95:.1f} dtk · maks {max(lat):.1f} dtk · rata-rata {rata:.1f} dtk")
    keluar = sum(r["token_keluar"] for r in berhasil)
    if keluar:
        masuk = sum(r["token_masuk"] for r in berhasil)
        print(f"Token: masuk {masuk:,} · keluar {keluar:,} · keluaran gabungan {keluar / durasi:.1f} token/dtk "
              f"· per permintaan {sum(r['token_keluar'] / r['detik'] for r in berhasil) / len(berhasil):.1f} "
              "token/dtk (termasuk antre)")
    if not args.agent:
        print(f"Model memilih tool pada {sum(1 for r in berhasil if r['tool'])}/{len(berhasil)} permintaan")

    # Mode default mengukur SATU langkah; satu jawaban agent biasanya 2-3 langkah.
    skala = 1 if args.agent else 3
    perkiraan = rata * skala
    if gagal:
        saran = (f"{gagal} permintaan gagal (biasanya timeout saat antre): kurangi peserta per server "
                 "atau pindahkan sebagian kelompok ke cadangan cloud.")
    elif rata > 60:
        saran = "rata-rata > 60 dtk: kurangi peserta per server / pakai cadangan cloud."
    elif perkiraan > 90:
        saran = (f"lambat (satu jawaban agent ±{perkiraan:.0f} dtk): jalankan praktik bergiliran per kelompok, "
                 "naikkan OLLAMA_NUM_PARALLEL bila RAM cukup, atau pakai cadangan cloud untuk sebagian kelompok.")
    elif perkiraan > 45:
        saran = f"masih wajar (satu jawaban agent ±{perkiraan:.0f} dtk); beri tahu peserta agar menunggu, jangan mengirim ulang."
    else:
        saran = f"lancar untuk {args.peserta} peserta bersamaan (satu jawaban agent ±{perkiraan:.0f} dtk)."
    print(f"Rekomendasi: {saran}")


if __name__ == "__main__":
    main()
