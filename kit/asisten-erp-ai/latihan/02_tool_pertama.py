"""
LATIHAN 2 — Tool pertama                                              (±15 menit)

Tujuan
  1. Menulis definisi tool (JSON Schema) supaya model tahu kapan & cara memakainya.
  2. Melihat bahwa model hanya MEMINTA tool dipanggil (nama + argumen).
     Yang menjalankan query adalah KODE KITA, bukan model.

Jalankan:
  python latihan/02_tool_pertama.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from asisten import config, db, llm

klien = OpenAI(base_url=config.LOKAL.base_url, api_key=config.LOKAL.api_key)
# Opsi khusus penyedia, dari LOKAL_REASONING_EFFORT di .env: {"reasoning_effort": "none"} mematikan
# mode "berpikir" Qwen3 agar jawaban cepat; kosong ({}) untuk model lain, mis. Claude lewat API.
OPSI = llm.opsi_tambahan(config.LOKAL)


def tren_penjualan(produk: str, bulan_terakhir: int = 3) -> list[dict]:
    """Penjualan per bulan untuk satu produk. Query BERPARAMETER → aman dari SQL injection."""
    return db.query(
        """
        SELECT to_char(bulan, 'YYYY-MM') AS bulan, sum(qty) AS qty, round(sum(nilai)) AS nilai_rupiah
        FROM ai.v_penjualan
        WHERE produk ILIKE %(produk)s
          AND bulan > (SELECT tanggal_posisi FROM ai.v_info) - make_interval(months => %(n)s)
        GROUP BY bulan
        ORDER BY bulan
        """,
        {"produk": f"%{produk}%", "n": int(bulan_terakhir)},
    )


# TODO 1: lengkapi definisi tool di bawah ini.
#   - "description": jelaskan KAPAN model harus memakai tool ini (model membaca teks ini!)
#   - "properties": tambahkan parameter
#        produk          → type "string",  description "Nama produk, mis. 'Biskuit Kelapa'"
#        bulan_terakhir  → type "integer", description "Jumlah bulan ke belakang, default 3"
#   - "required": parameter yang wajib diisi model → ["produk"]
TOOL_TREN = {
    "type": "function",
    "function": {
        "name": "tren_penjualan",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
        },
    },
}

pertanyaan = "Bagaimana tren penjualan Biskuit Kelapa 3 bulan terakhir?"
print("Tanya:", pertanyaan, "\n")

resp = klien.chat.completions.create(
    model=config.LOKAL.model,
    messages=[
        {"role": "system", "content": "Kamu asisten ERP. Gunakan tool untuk mendapatkan data. Jangan mengarang angka."},
        {"role": "user", "content": pertanyaan},
    ],
    tools=[TOOL_TREN],
    **OPSI,
)
msg = resp.choices[0].message

if not msg.tool_calls:
    print("Model TIDAK meminta tool. Jawabannya:\n", msg.content)
    print("\n→ Periksa lagi TODO 1: apakah deskripsi & parameter tool sudah jelas?")
    sys.exit()

for tc in msg.tool_calls:
    print("Model meminta tool :", tc.function.name)
    print("   dengan argumen     :", tc.function.arguments)

    # TODO 2: jalankan fungsi tren_penjualan dengan argumen dari model, lalu cetak hasilnya.
    # Petunjuk:
    #   argumen = json.loads(tc.function.arguments)
    #   hasil = tren_penjualan(**argumen)
    #   print(json.dumps(hasil, indent=2, ensure_ascii=False))

# Renungkan: model sudah memilih tool dan argumennya, kode kita sudah mengambil datanya.
# Tapi model belum MENJAWAB user. Bagaimana caranya? → Latihan 3: agent loop.
