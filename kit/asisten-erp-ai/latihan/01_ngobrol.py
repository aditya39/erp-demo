"""
LATIHAN 1 — Ngobrol dengan model lokal                                 (±5 menit)

Tujuan
  1. Memanggil model lokal (Ollama) lewat API yang kompatibel OpenAI.
  2. Melihat bahwa model TIDAK mengetahui data perusahaan, dan bisa mengarang.

Jalankan dari folder utama proyek:
  python latihan/01_ngobrol.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from asisten import config, db, llm
from asisten import format as fmt

# Model lokal di Ollama bisa dipanggil dengan library "openai".
# Kode yang sama dapat dipakai untuk model cloud: cukup ganti base_url, api_key, dan model
# (di .env: LOKAL_BASE_URL, LOKAL_API_KEY, LOKAL_MODEL — lihat profil di .env.example).
klien = OpenAI(base_url=config.LOKAL.base_url, api_key=config.LOKAL.api_key)
# Opsi khusus penyedia, dari LOKAL_REASONING_EFFORT di .env: {"reasoning_effort": "none"} mematikan
# mode "berpikir" Qwen3 agar jawaban cepat; kosong ({}) untuk model lain, mis. Claude lewat API.
OPSI = llm.opsi_tambahan(config.LOKAL)


def tanya(pertanyaan: str) -> str:
    resp = klien.chat.completions.create(
        model=config.LOKAL.model,
        messages=[{"role": "user", "content": pertanyaan}],
        **OPSI,
    )
    return resp.choices[0].message.content


# Bulan terakhir data ERP (mis. "Oktober 2026"), dibaca dari database agar contoh selalu sesuai data.
BULAN_DATA = fmt.bulan(db.info()["bulan_terakhir"])

print(f"Model: {config.LOKAL.model} di {config.LOKAL.base_url}\n")

print("Tanya: Apa itu HPP?")
print(tanya("Jelaskan apa itu HPP (harga pokok produksi) dalam 2 kalimat."), "\n")

# TODO 1: tanyakan data perusahaan kepada model, misalnya:
#   f"Berapa penjualan Biskuit Kelapa 200g di PT Nusantara Rasa bulan {BULAN_DATA}?"
# Jalankan beberapa kali. Perhatikan: apakah model tahu? Apakah ia mengarang angka?
#
# print("Tanya: Data perusahaan")
# print(tanya("..."))

# Renungkan: bagaimana caranya agar model bisa menjawab dengan data ERP yang benar?
# → Latihan 2: memberi model "tool".
