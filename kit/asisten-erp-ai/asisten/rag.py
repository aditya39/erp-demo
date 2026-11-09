"""
RAG (Retrieval-Augmented Generation) untuk dokumen internal.

Alur:
  INGEST  : dokumen .md -> dipotong per bagian -> embedding -> disimpan di pgvector
  CARI    : pertanyaan -> embedding -> cari potongan paling mirip (cosine) -> konteks

Setiap potongan membawa metadata dokumennya (judul, nomor dokumen, tanggal berlaku), sehingga
jawaban bisa menyebut sumber lengkap, mis. "Kebijakan Harga dan Diskon (KBJ-PJL-002)".

Tempat penyimpanan:
  rag.dokumen_chunk         indeks bersama (folder dokumen/), diisi admin/mentor
  latihan.dokumen_<nama>    koleksi milik peserta (Sesi 2.4), diisi dengan role erp_peserta

Pemakaian:
  python -m asisten.rag ingest                          # folder dokumen/ -> rag.dokumen_chunk (koneksi admin)
  python -m asisten.rag ingest --koleksi andi           # folder dokumen-latihan/ -> latihan.dokumen_andi
  python -m asisten.rag ingest --koleksi andi --timpa   # ingest ulang koleksi yang sudah ada
  python -m asisten.rag ingest --koleksi andi --folder dokumen-latihan
  python -m asisten.rag cari "batas retur"              # uji pencarian (+ koleksi RAG_KOLEKSI bila diisi)
  python -m asisten.rag cari --koleksi andi "jadwal kirim ke Medan"
  python -m asisten.rag hapus --koleksi andi            # hapus koleksi sendiri

Koleksi peserta ikut dicari oleh tool cari_dokumen bila environment variable RAG_KOLEKSI=<nama> diisi.
"""
from __future__ import annotations

import argparse
import os
import re
from functools import lru_cache
from pathlib import Path

from openai import OpenAI
from psycopg import sql

from . import config, db

MAKS_KARAKTER = 1200
FOLDER_LATIHAN = config.ROOT / "dokumen-latihan"
# Nama koleksi menjadi bagian nama tabel, jadi dibatasi whitelist: huruf kecil, angka, garis bawah.
POLA_KOLEKSI = re.compile(r"[a-z][a-z0-9_]{0,29}")


class KoleksiSudahAda(ValueError):
    """Koleksi peserta sudah ada; ingest ulang hanya dengan timpa=True (--timpa)."""


def metadata_dokumen(teks: str) -> dict:
    """
    Baca baris metadata di bawah judul, mis.
    "Nomor dokumen: KBJ-PJL-002 · Berlaku sejak: 2 Januari 2026 · Pemilik: Direktur Operasional"
    -> {"nomor": "KBJ-PJL-002", "berlaku": "berlaku sejak 2 Januari 2026"}. Field kosong bila tidak ada.
    """
    meta = {"nomor": "", "berlaku": ""}
    for baris in teks.splitlines():
        if baris.startswith("## "):
            break
        for bagian in baris.split("·"):
            kunci, _, nilai = bagian.partition(":")
            kunci, nilai = kunci.strip().lower(), nilai.strip()
            if kunci == "nomor dokumen" and nilai:
                meta["nomor"] = nilai
            elif kunci in ("berlaku sejak", "diperbarui") and nilai:
                meta["berlaku"] = f"{kunci} {nilai}"
    return meta


def potong_dokumen(path: Path) -> list[dict]:
    """Potong dokumen Markdown per heading '##'. Bagian panjang dipecah per paragraf."""
    teks = path.read_text(encoding="utf-8")
    judul = next((b[2:].strip() for b in teks.splitlines() if b.startswith("# ")), path.stem)
    dokumen = {"sumber": judul, **metadata_dokumen(teks)}   # ikut disimpan di setiap potongan
    bagian = re.split(r"(?m)^## ", teks)
    hasil = []
    for blok in bagian[1:]:
        baris = blok.splitlines()
        nama_bagian = baris[0].strip()
        isi = "\n".join(baris[1:]).strip()
        paragraf, buffer = re.split(r"\n\s*\n", isi), ""
        for p in paragraf:
            if buffer and len(buffer) + len(p) > MAKS_KARAKTER:
                hasil.append({**dokumen, "bagian": nama_bagian, "isi": buffer.strip()})
                buffer = ""
            buffer += p + "\n\n"
        if buffer.strip():
            hasil.append({**dokumen, "bagian": nama_bagian, "isi": buffer.strip()})
    return hasil


def kumpulkan_potongan(folder: Path) -> list[dict]:
    """Potongan semua dokumen .md di folder (README.md tidak ikut)."""
    potongan = []
    for path in sorted(folder.glob("*.md")):
        if path.name.lower() != "readme.md":
            potongan += potong_dokumen(path)
    return potongan


def teks_untuk_embedding(p: dict) -> str:
    """Judul + nomor dokumen + bagian ikut di-embed, agar pertanyaan "KBJ-PJL-002 ..." juga ketemu."""
    judul = f"{p['sumber']} ({p['nomor']})" if p.get("nomor") else p["sumber"]
    return f"{judul} — {p['bagian']}\n{p['isi']}"


def embed(teks: list[str]) -> list[list[float]]:
    # Embedding selalu ke Ollama (EMBED_BASE_URL), juga saat model chat memakai cloud.
    klien = OpenAI(base_url=config.EMBED_BASE_URL, api_key=config.EMBED_API_KEY)
    resp = klien.embeddings.create(model=config.EMBED_MODEL, input=teks)
    return [d.embedding for d in resp.data]


def _vektor(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


# ---------------------------------------------------------------------------
# Koleksi peserta
# ---------------------------------------------------------------------------
def nama_koleksi(nama: str) -> str:
    """Validasi nama koleksi, mis. 'andi' atau 'tim_2'. Melempar ValueError bila tidak valid."""
    nama = (nama or "").strip().lower()
    if not POLA_KOLEKSI.fullmatch(nama):
        raise ValueError(f"Nama koleksi '{nama}' tidak valid. Gunakan 1-30 karakter: diawali huruf, "
                         "lalu huruf kecil, angka, atau garis bawah (mis. andi atau tim_2).")
    return nama


def tabel_koleksi(nama: str | None = None) -> tuple[str, str]:
    """(schema, tabel): tanpa nama -> indeks bersama; dengan nama -> latihan.dokumen_<nama>."""
    return ("latihan", f"dokumen_{nama_koleksi(nama)}") if nama else ("rag", "dokumen_chunk")


def koleksi_aktif() -> str:
    """Koleksi peserta yang ikut dicari (environment variable RAG_KOLEKSI); "" bila tidak diisi."""
    nama = os.getenv("RAG_KOLEKSI", "").strip()
    return nama_koleksi(nama) if nama else ""


def url_ingest(koleksi: str | None = None) -> str:
    """Indeks bersama: koneksi admin. Koleksi peserta: DATABASE_URL_PESERTA (cadangan: admin, mode laptop sendiri)."""
    if not koleksi:
        return config.DATABASE_URL_ADMIN
    return os.getenv("DATABASE_URL_PESERTA", "").strip() or config.DATABASE_URL_ADMIN


def koleksi_ada(koleksi: str) -> bool:
    schema, tabel = tabel_koleksi(koleksi)
    return db.query("SELECT to_regclass(%(t)s) IS NOT NULL AS ada", {"t": f"{schema}.{tabel}"})[0]["ada"]


@lru_cache(maxsize=64)
def punya_metadata(schema: str, tabel: str) -> bool:
    """Indeks lama (dibuat sebelum ada kolom nomor/berlaku) tetap bisa dicari; ingest ulang untuk melengkapinya."""
    return bool(db.query(
        """SELECT 1 FROM information_schema.columns
           WHERE table_schema = %(s)s AND table_name = %(t)s AND column_name = 'nomor'""",
        {"s": schema, "t": tabel}))


def _kolom_metadata(ada: bool) -> str:
    return "nomor, berlaku" if ada else "'' AS nomor, '' AS berlaku"


def sql_cari(koleksi: str = "", meta_bersama: bool = True, meta_koleksi: bool = True) -> str:
    """
    Query vector search: indeks bersama, ditambah koleksi peserta (UNION ALL) bila ada, diurutkan
    menurut jarak. Nama tabel aman disisipkan karena sudah lolos whitelist nama_koleksi().
    Parameter: %(v)s vektor pertanyaan, %(k)s jumlah potongan, %(koleksi)s label koleksi peserta.
    """
    def satu(tabel: tuple[str, str], label: str, meta: bool) -> str:
        return (f"(SELECT sumber, {_kolom_metadata(meta)}, bagian, isi, embedding <=> %(v)s::vector AS jarak, "
                f'{label} AS koleksi FROM "{tabel[0]}"."{tabel[1]}" ORDER BY embedding <=> %(v)s::vector LIMIT %(k)s)')

    bagian = [satu(tabel_koleksi(), "'bersama'", meta_bersama)]
    if koleksi:
        bagian.append(satu(tabel_koleksi(koleksi), "%(koleksi)s", meta_koleksi))
    return (f"SELECT sumber, nomor, berlaku, bagian, isi, 1 - jarak AS skor, koleksi "
            f"FROM ({' UNION ALL '.join(bagian)}) AS t ORDER BY jarak LIMIT %(k)s")


# ---------------------------------------------------------------------------
# Ingest & cari
# ---------------------------------------------------------------------------
def ingest(folder: Path = config.FOLDER_DOKUMEN, koleksi: str | None = None, timpa: bool = False) -> int:
    """
    Simpan dokumen .md di folder ke indeks bersama (tanpa koleksi) atau ke koleksi peserta.
    Koleksi yang sudah ada tidak ditimpa kecuali timpa=True: semua peserta memakai role yang sama,
    jadi nama yang sama bisa berarti koleksi milik pasangan lain.
    """
    import psycopg

    schema, tabel = tabel_koleksi(koleksi)
    if koleksi and not timpa and koleksi_ada(koleksi):
        raise KoleksiSudahAda(
            f"Koleksi '{koleksi}' sudah ada ({schema}.{tabel}) dan mungkin milik pasangan lain. "
            f"Pakai nama lain (mis. {koleksi[:28]}_2), atau tambahkan --timpa bila koleksi itu memang milik Anda.")
    potongan = kumpulkan_potongan(Path(folder))
    if not potongan:
        raise SystemExit(f"Tidak ada dokumen .md di {folder}")
    nama_tabel = sql.Identifier(schema, tabel)

    url = url_ingest(koleksi)
    # Sambung ke database dulu: IP atau password yang salah langsung ketahuan, sebelum embedding yang lama.
    with psycopg.connect(url, connect_timeout=10) as conn:
        vektor = embed([teks_untuk_embedding(p) for p in potongan])
        dimensi = len(vektor[0])
        if koleksi and url == config.DATABASE_URL_ADMIN:
            # Mode laptop sendiri (tanpa role peserta): pastikan schema latihan ada.
            conn.execute("CREATE SCHEMA IF NOT EXISTS latihan")
            conn.execute("GRANT USAGE ON SCHEMA latihan TO erp_ai_readonly")
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(nama_tabel))
        conn.execute(sql.SQL("""
            CREATE TABLE {} (
                id         SERIAL PRIMARY KEY,
                sumber     TEXT NOT NULL,
                nomor      TEXT NOT NULL DEFAULT '',
                berlaku    TEXT NOT NULL DEFAULT '',
                bagian     TEXT NOT NULL,
                isi        TEXT NOT NULL,
                embedding  vector({}) NOT NULL
            )""").format(nama_tabel, sql.Literal(dimensi)))
        for p, v in zip(potongan, vektor):
            conn.execute(
                sql.SQL("INSERT INTO {} (sumber, nomor, berlaku, bagian, isi, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s::vector)").format(nama_tabel),
                (p["sumber"], p["nomor"], p["berlaku"], p["bagian"], p["isi"], _vektor(v)))
        conn.execute(sql.SQL("CREATE INDEX ON {} USING hnsw (embedding vector_cosine_ops)").format(nama_tabel))
        conn.execute(sql.SQL("GRANT SELECT ON {} TO erp_ai_readonly").format(nama_tabel))
    punya_metadata.cache_clear()
    return len(potongan)


def hapus(koleksi: str) -> None:
    """Hapus koleksi peserta (indeks bersama tidak bisa dihapus dari sini)."""
    import psycopg

    with psycopg.connect(url_ingest(koleksi)) as conn:
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(*tabel_koleksi(koleksi))))


def cari(pertanyaan: str, k: int = 4, koleksi: str | None = None) -> list[dict]:
    """
    Potongan dokumen paling mirip dengan pertanyaan, beserta metadata dokumennya (nomor, berlaku).
      koleksi=None : indeks bersama + koleksi RAG_KOLEKSI bila diisi (dipakai tool cari_dokumen)
      koleksi=""   : hanya indeks bersama
      koleksi="x"  : indeks bersama + koleksi latihan.dokumen_x
    Dengan koleksi, setiap baris juga berisi field "koleksi" ("bersama" atau nama koleksi peserta).
    """
    nama = koleksi_aktif() if koleksi is None else (nama_koleksi(koleksi) if koleksi else "")
    v = _vektor(embed([pertanyaan])[0])
    meta = punya_metadata(*tabel_koleksi())
    if not nama:
        return db.query(
            f"""
            SELECT sumber, {_kolom_metadata(meta)}, bagian, isi, 1 - (embedding <=> %(v)s::vector) AS skor
            FROM rag.dokumen_chunk
            ORDER BY embedding <=> %(v)s::vector
            LIMIT %(k)s
            """,
            {"v": v, "k": k},
        )
    # Koleksi belum di-ingest: cari di indeks bersama saja (scripts/cek_setup.py memberi peringatan).
    ada = koleksi_ada(nama)
    return db.query(sql_cari(nama if ada else "", meta, ada and punya_metadata(*tabel_koleksi(nama))),
                    {"v": v, "k": k, "koleksi": nama})


def _folder(teks: str | None, koleksi: str | None) -> Path:
    if not teks:
        return FOLDER_LATIHAN if koleksi else config.FOLDER_DOKUMEN
    p = Path(teks)
    return p if p.is_absolute() or p.exists() else config.ROOT / p


def main() -> None:
    import openai
    import psycopg

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perintah", choices=["ingest", "cari", "hapus"])
    ap.add_argument("pertanyaan", nargs="*", help="untuk 'cari'")
    ap.add_argument("--koleksi", help="nama koleksi peserta, mis. andi -> tabel latihan.dokumen_andi")
    ap.add_argument("--folder", help="folder dokumen .md (default: dokumen/, atau dokumen-latihan/ bila --koleksi)")
    ap.add_argument("--timpa", action="store_true", help="ingest ulang koleksi peserta yang sudah ada")
    args = ap.parse_args()

    try:
        koleksi = nama_koleksi(args.koleksi) if args.koleksi else None
        if args.perintah == "ingest":
            folder = _folder(args.folder, koleksi)
            n = ingest(folder, koleksi, timpa=args.timpa)
            schema, tabel = tabel_koleksi(koleksi)
            print(f"{n} potongan dokumen dari {folder.name}/ tersimpan di {schema}.{tabel} "
                  f"(model embedding: {config.EMBED_MODEL})")
            if koleksi:
                print(f"Agar ikut dicari asisten, isi RAG_KOLEKSI={koleksi} di .env (atau environment variable).")
        elif args.perintah == "hapus":
            if not koleksi:
                raise SystemExit("Gunakan --koleksi <nama>. Indeks bersama hanya diisi ulang dengan 'ingest'.")
            hapus(koleksi)
            print(f"Koleksi {'.'.join(tabel_koleksi(koleksi))} dihapus.")
        else:
            if not args.pertanyaan:
                raise SystemExit('Contoh: python -m asisten.rag cari "batas waktu retur roti"')
            for h in cari(" ".join(args.pertanyaan), koleksi=koleksi):
                label = f"({h['koleksi']}) " if "koleksi" in h else ""
                nomor = f" ({h['nomor']})" if h.get("nomor") else ""
                print(f"[{h['skor']:.2f}] {label}{h['sumber']}{nomor} › {h['bagian']}\n"
                      f"    {h['isi'][:160].replace(chr(10), ' ')}…")
    except ValueError as e:
        raise SystemExit(str(e)) from None
    except psycopg.errors.InvalidSchemaName:
        raise SystemExit("Schema 'latihan' belum ada di database. Mentor: jalankan scripts/server_bersama.sh "
                         "(atau db/init/04_latihan.sql).") from None
    except psycopg.errors.InsufficientPrivilege as e:
        raise SystemExit(f"Akses ditolak database: {str(e).splitlines()[0]}\n"
                         "Untuk koleksi peserta, periksa DATABASE_URL_PESERTA di .env.") from None
    except psycopg.OperationalError as e:
        teks = " ".join(str(e).split())
        if "password authentication failed" in teks or ("role" in teks and "does not exist" in teks):
            raise SystemExit(f"Akses ditolak database: user atau password salah ({teks[:160]})\n"
                             "Untuk koleksi peserta, salin ulang DATABASE_URL_PESERTA dari profil server workshop.") from None
        raise SystemExit(f"Database tidak dapat dihubungi ({teks[:160]})\n"
                         "Periksa IP di DATABASE_URL / DATABASE_URL_PESERTA di .env, lalu jalankan "
                         "python scripts/cek_setup.py.") from None
    except openai.APIConnectionError:
        raise SystemExit(f"Server embedding tidak dapat dihubungi di {config.EMBED_BASE_URL} (model {config.EMBED_MODEL}).\n"
                         "Periksa EMBED_BASE_URL di .env (profil b dan c: http://<IP server>:11434/v1), "
                         "lalu jalankan python scripts/cek_setup.py.") from None
    except openai.APIStatusError as e:
        raise SystemExit(f"Server embedding menolak permintaan (HTTP {e.status_code}) di {config.EMBED_BASE_URL}. "
                         f"Pastikan model {config.EMBED_MODEL} sudah diunduh di server itu.") from None


if __name__ == "__main__":
    main()
