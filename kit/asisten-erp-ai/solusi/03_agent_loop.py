"""
SOLUSI LATIHAN 3 — Agent loop                                                (±20 menit)

Tujuan
  Menyusun "loop" agent: model meminta tool → kode menjalankan → hasil dikirim
  balik ke model → diulang sampai model memberi jawaban akhir.
  Inilah inti agentic AI: LLM + tools + loop.

Jalankan:
  python latihan/03_agent_loop.py
  python latihan/03_agent_loop.py "Kenapa HPP Roti Cokelat naik bulan ini?"
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from asisten import config, db, llm
from asisten import format as fmt

klien = OpenAI(base_url=config.LOKAL.base_url, api_key=config.LOKAL.api_key)
# Opsi khusus penyedia, dari LOKAL_REASONING_EFFORT di .env: {"reasoning_effort": "none"} mematikan
# mode "berpikir" Qwen3 agar jawaban cepat; kosong ({}) untuk model lain, mis. Claude lewat API.
OPSI = llm.opsi_tambahan(config.LOKAL)
MAKS_LANGKAH = 5


# ----------------------------------------------------------------------------
# Tools (sudah jadi). Perhatikan: angka perubahan dihitung oleh SQL, bukan oleh model.
# ----------------------------------------------------------------------------
def tren_penjualan(produk: str, bulan_terakhir: int = 3) -> list[dict]:
    return db.query(
        """
        SELECT to_char(bulan, 'YYYY-MM') AS bulan, sum(qty) AS qty, round(sum(nilai)) AS nilai_rupiah
        FROM ai.v_penjualan
        WHERE produk ILIKE %(produk)s
          AND bulan > (SELECT tanggal_posisi FROM ai.v_info) - make_interval(months => %(n)s)
        GROUP BY bulan ORDER BY bulan
        """,
        {"produk": f"%{produk}%", "n": int(bulan_terakhir)},
    )


def komponen_hpp(produk: str) -> list[dict]:
    """Biaya bahan per unit bulan terakhir vs bulan sebelumnya, diurutkan dari kenaikan terbesar."""
    return db.query(
        """
        WITH b AS (SELECT date_trunc('month', tanggal_posisi)::date AS kini FROM ai.v_info)
        SELECT k.bahan,
               round(max(k.biaya_per_unit) FILTER (WHERE k.bulan = b.kini - interval '1 month')) AS biaya_bulan_lalu,
               round(max(k.biaya_per_unit) FILTER (WHERE k.bulan = b.kini)) AS biaya_bulan_ini,
               round(max(k.biaya_per_unit) FILTER (WHERE k.bulan = b.kini)
                   - max(k.biaya_per_unit) FILTER (WHERE k.bulan = b.kini - interval '1 month')) AS kenaikan
        FROM ai.v_hpp_komponen k, b
        WHERE k.produk ILIKE %(produk)s AND k.bulan >= b.kini - interval '1 month'
        GROUP BY k.bahan ORDER BY kenaikan DESC
        """,
        {"produk": f"%{produk}%"},
    )


def riwayat_harga_bahan(bahan: str) -> list[dict]:
    return db.query(
        """
        SELECT to_char(bulan, 'YYYY-MM') AS bulan, harga
        FROM ai.v_harga_bahan
        WHERE bahan ILIKE %(bahan)s
        ORDER BY bulan DESC LIMIT 6
        """,
        {"bahan": f"%{bahan}%"},
    )


FUNGSI = {"tren_penjualan": tren_penjualan, "komponen_hpp": komponen_hpp, "riwayat_harga_bahan": riwayat_harga_bahan}

TOOLS = [
    {"type": "function", "function": {
        "name": "tren_penjualan",
        "description": "Penjualan per bulan (qty & nilai rupiah) untuk satu produk.",
        "parameters": {"type": "object", "properties": {
            "produk": {"type": "string", "description": "Nama produk, mis. 'Biskuit Kelapa'"},
            "bulan_terakhir": {"type": "integer", "description": "Jumlah bulan ke belakang, default 3"}},
            "required": ["produk"]}}},
    {"type": "function", "function": {
        "name": "komponen_hpp",
        "description": "Biaya bahan baku per unit suatu produk, bulan ini vs bulan lalu. Untuk mencari penyebab HPP naik.",
        "parameters": {"type": "object", "properties": {
            "produk": {"type": "string", "description": "Nama produk, mis. 'Roti Cokelat'"}},
            "required": ["produk"]}}},
    {"type": "function", "function": {
        "name": "riwayat_harga_bahan",
        "description": "Harga bahan baku 6 bulan terakhir, mis. 'Kakao bubuk'.",
        "parameters": {"type": "object", "properties": {
            "bahan": {"type": "string", "description": "Nama bahan baku"}},
            "required": ["bahan"]}}},
]

# Tanggal posisi data dibaca dari database, bukan ditulis tetap di kode.
SYSTEM = (f"Kamu asisten ERP PT Nusantara Rasa. Data tersedia sampai {fmt.bulan(db.info()['bulan_terakhir'])}. "
          "Selalu gunakan tool untuk mendapatkan angka; jangan mengarang. "
          "Jawab ringkas dalam bahasa Indonesia dan sebutkan periodenya.")


def jalankan_agent(pertanyaan: str) -> str:
    pesan = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": pertanyaan}]

    for langkah in range(1, MAKS_LANGKAH + 1):
        resp = klien.chat.completions.create(
            model=config.LOKAL.model, messages=pesan, tools=TOOLS, **OPSI)
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content

        pesan.append(msg.model_dump(exclude_none=True))

        for tc in msg.tool_calls:
            nama = tc.function.name
            argumen = json.loads(tc.function.arguments or "{}")
            hasil = FUNGSI[nama](**argumen)
            print(f"  [{langkah}] tool {nama}({argumen}) → {len(hasil)} baris")
            pesan.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(hasil, default=str)})

    return "(batas langkah tercapai)"


if __name__ == "__main__":
    daftar = sys.argv[1:] or [
        "Bagaimana tren penjualan Biskuit Kelapa 3 bulan terakhir?",
        "Kenapa HPP Roti Cokelat naik bulan ini? Cek juga riwayat harga bahan penyebabnya.",
    ]
    for q in daftar:
        print(f"\nTanya: {q}")
        print("Jawab:", jalankan_agent(q))
