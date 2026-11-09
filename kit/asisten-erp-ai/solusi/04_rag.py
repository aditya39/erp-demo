"""
SOLUSI LATIHAN 4 — RAG: menjawab dari dokumen perusahaan                     (±20 menit)

Tujuan
  A. Melihat bagaimana dokumen dipotong (chunking).
  B. Menulis query pencarian kemiripan (vector search) di pgvector.
  C. Menyusun prompt: pertanyaan + potongan dokumen → jawaban beserta sumbernya.
  D. (Sesi 2.4) Menambah dokumen baru ke koleksi milik sendiri, lalu membandingkan
     jawaban sebelum dan sesudah dokumen itu di-ingest.

Prasyarat: dokumen sudah di-ingest ke database (biasanya sudah disiapkan mentor):
  python -m asisten.rag ingest

Jalankan:
  python latihan/04_rag.py
  python latihan/04_rag.py "Siapa yang menyetujui diskon tambahan 2%?"
  python latihan/04_rag.py --koleksi andi      # bagian A–C lalu D, koleksi latihan.dokumen_andi
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from asisten import config, db, llm, rag

klien = OpenAI(base_url=config.LOKAL.base_url, api_key=config.LOKAL.api_key)
# Opsi khusus penyedia, dari LOKAL_REASONING_EFFORT di .env: {"reasoning_effort": "none"} mematikan
# mode "berpikir" Qwen3 agar jawaban cepat; kosong ({}) untuk model lain, mis. Claude lewat API.
OPSI = llm.opsi_tambahan(config.LOKAL)

# Argumen: pertanyaan untuk bagian B–C, atau --koleksi <nama> untuk menjalankan bagian D juga.
KOLEKSI = rag.nama_koleksi(sys.argv[2]) if sys.argv[1:2] == ["--koleksi"] and len(sys.argv) > 2 else ""
ARGUMEN = [] if KOLEKSI else sys.argv[1:]

# ---------------------------------------------------------------------------
# A. Chunking: satu dokumen dipotong per bagian (heading "##")
# ---------------------------------------------------------------------------
potongan = rag.potong_dokumen(config.FOLDER_DOKUMEN / "01-SOP-Retur-Barang.md")
print(f"A. SOP Retur Barang dipotong menjadi {len(potongan)} bagian:")
for p in potongan:
    print(f"   - {p['bagian']} ({len(p['isi'])} karakter)")

# ---------------------------------------------------------------------------
# B. Vector search
# ---------------------------------------------------------------------------
pertanyaan = " ".join(ARGUMEN) or "Berapa lama batas waktu retur untuk roti yang rusak?"
vektor = rag.embed([pertanyaan])[0]
print(f"\nB. Pertanyaan diubah menjadi vektor berdimensi {len(vektor)}: [{vektor[0]:.3f}, {vektor[1]:.3f}, …]")

# TODO 1: lengkapi query agar mengambil 3 potongan yang PALING MIRIP dengan pertanyaan.
# Petunjuk:
#   - operator jarak cosine di pgvector:  embedding <=> %(v)s::vector   (semakin kecil = semakin mirip)
#   - urutkan berdasarkan jarak tersebut (ORDER BY ...), lalu batasi 3 baris (LIMIT 3)
SQL_CARI = """
    SELECT sumber, nomor, bagian, isi, 1 - (embedding <=> %(v)s::vector) AS skor
    FROM rag.dokumen_chunk
    ORDER BY embedding <=> %(v)s::vector
    LIMIT 3
"""
hasil = db.query(SQL_CARI, {"v": "[" + ",".join(map(str, vektor)) + "]"})
print(f"   Ditemukan {len(hasil)} potongan:")
for h in hasil[:3]:
    print(f"   [{h['skor']:.2f}] {h['sumber']} ({h['nomor']}) › {h['bagian']}")

# ---------------------------------------------------------------------------
# C. Augmented generation: jawab hanya dari konteks
# ---------------------------------------------------------------------------
# Nomor dokumen ikut di konteks, mis. "[Kebijakan Harga dan Diskon (KBJ-PJL-002) › Diskon tambahan]".
konteks = "\n\n".join(f"[{h['sumber']} ({h['nomor']}) › {h['bagian']}]\n{h['isi']}" for h in hasil[:3])

# TODO 2: lengkapi instruksi sistem agar model:
#   - menjawab HANYA berdasarkan konteks,
#   - mengatakan "tidak ditemukan di dokumen" jika jawabannya tidak ada,
#   - menyebutkan nama dan nomor dokumen sumbernya.
SYSTEM = ("Kamu asisten dokumen perusahaan. Jawab HANYA berdasarkan konteks yang diberikan. "
          "Jika jawabannya tidak ada di konteks, katakan 'tidak ditemukan di dokumen'. "
          "Sebutkan nama dan nomor dokumen sumbernya. Jawab ringkas dalam bahasa Indonesia.")

resp = klien.chat.completions.create(
    model=config.LOKAL.model,
    messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Konteks:\n{konteks}\n\nPertanyaan: {pertanyaan}"},
    ],
    **OPSI,
)
print(f"\nC. Tanya: {pertanyaan}\nJawab: {resp.choices[0].message.content}")

# BONUS: coba pertanyaan yang jawabannya TIDAK ada di dokumen,
#   mis. "Berapa gaji minimum karyawan?" — apakah model jujur mengatakan tidak ditemukan?

# ---------------------------------------------------------------------------
# D. Koleksi dokumen milik Anda (Sesi 2.4)
#    dokumen-latihan/06-SOP-Pengiriman-Barang.md BELUM ada di indeks bersama (rag.dokumen_chunk).
#    Anda memasukkannya ke koleksi sendiri (tabel latihan.dokumen_<nama>) tanpa mengubah indeks bersama.
#    Jalankan: python latihan/04_rag.py --koleksi <nama>      (pastikan TODO 2 sudah diisi)
# ---------------------------------------------------------------------------
def jawab_dokumen(pertanyaan: str, koleksi: str = "") -> str:
    """Bagian B + C dalam satu fungsi. koleksi="" → hanya indeks bersama; "andi" → + latihan.dokumen_andi."""
    hasil = rag.cari(pertanyaan, k=3, koleksi=koleksi)
    for h in hasil:
        print(f"   [{h['skor']:.2f}] ({h.get('koleksi', 'bersama')}) {h['sumber']} {h['nomor']} › {h['bagian']}")
    # Nomor dokumen ikut di konteks, agar jawaban bisa menyebut sumber lengkap (mis. SOP-GDG-003).
    konteks = "\n\n".join(f"[{h['sumber']} ({h['nomor']}) › {h['bagian']}]\n{h['isi']}" for h in hasil)
    resp = klien.chat.completions.create(
        model=config.LOKAL.model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Konteks:\n{konteks}\n\nPertanyaan: {pertanyaan}"},
        ],
        **OPSI,
    )
    return resp.choices[0].message.content


if KOLEKSI:
    tanya_kirim = "Jam berapa batas order agar barang dikirim besok ke Bandung?"
    print(f"\nD1. SEBELUM ingest — Tanya: {tanya_kirim}")
    print("Jawab:", jawab_dokumen(tanya_kirim))   # hanya indeks bersama → seharusnya "tidak ditemukan"

    if rag.koleksi_ada(KOLEKSI):   # dijalankan ulang: koleksi dipakai apa adanya, tidak ditimpa
        print(f"\nD2. Koleksi latihan.dokumen_{KOLEKSI} sudah ada, dipakai apa adanya. Ingest ulang: "
              f"python -m asisten.rag ingest --koleksi {KOLEKSI} --timpa")
    else:
        n = rag.ingest(rag.FOLDER_LATIHAN, koleksi=KOLEKSI)
        print(f"\nD2. {n} potongan dokumen tersimpan di latihan.dokumen_{KOLEKSI}")

    print(f"\nD3. SESUDAH ingest — Tanya: {tanya_kirim}")
    print("Jawab:", jawab_dokumen(tanya_kirim, koleksi=KOLEKSI))   # sumber: SOP Pengiriman Barang

    print(f"\nAgar asisten lengkap (tool cari_dokumen) ikut mencari koleksi ini, isi RAG_KOLEKSI={KOLEKSI} di .env,")
    print(f'lalu: python -m asisten --pengguna andi --detail "{tanya_kirim}"')

# BONUS D: coba pertanyaan lain tentang pengiriman, mis. "Berapa minimum order gratis ongkos kirim untuk
#   segmen Toko?", "Siapa yang menyetujui pengiriman ekspres?", atau "Apa yang dilakukan bila barang rusak
#   saat diterima?" (jawabannya menggabungkan SOP Pengiriman dan SOP Retur). Hapus koleksi setelah latihan:
#   python -m asisten.rag hapus --koleksi <nama>
