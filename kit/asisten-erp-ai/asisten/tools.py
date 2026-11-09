"""
Tools yang boleh dipakai asisten AI.

Pola setiap tool:
  1. Deskripsi + skema parameter (JSON Schema) -> dibaca model untuk memilih tool.
  2. Izin yang dibutuhkan -> dicek oleh kode sebelum tool dijalankan.
  3. Fungsi Python yang menjalankan query BERPARAMETER ke view schema "ai".
  4. Hasil berisi angka yang sudah dihitung & diformat oleh kode (field *_fmt),
     sehingga model cukup menjelaskan, bukan menghitung.
  5. Field "grafik" (opsional) dikirim ke layar, tidak dikirim ke model.

Menambah tool baru: tulis di asisten/tools_tambahan.py dengan dekorator @tool.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from . import db
from . import format as fmt


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
@dataclass
class Tool:
    nama: str
    deskripsi: str
    parameter: dict
    izin: str
    fungsi: Callable[..., dict]

    def skema(self) -> dict:
        """Format definisi tool untuk API Chat Completions (OpenAI-compatible)."""
        return {
            "type": "function",
            "function": {"name": self.nama, "description": self.deskripsi, "parameters": self.parameter},
        }


REGISTRY: dict[str, Tool] = {}


def tool(nama: str, deskripsi: str, parameter: dict, izin: str):
    """Dekorator untuk mendaftarkan fungsi sebagai tool."""
    def daftar(fungsi: Callable[..., dict]) -> Callable[..., dict]:
        REGISTRY[nama] = Tool(nama, deskripsi, parameter, izin, fungsi)
        return fungsi
    return daftar


def semua_skema() -> list[dict]:
    return [t.skema() for t in REGISTRY.values()]


def skema_untuk(izin_user: list[str]) -> list[dict]:
    """Alternatif: hanya tool yang diizinkan untuk user ini yang diperlihatkan ke model."""
    return [t.skema() for t in REGISTRY.values() if t.izin in izin_user]


# ---------------------------------------------------------------------------
# Pencarian nama produk / bahan yang toleran ejaan
# ---------------------------------------------------------------------------
SINONIM = {"coklat": "cokelat", "choco": "cokelat", "chocolate": "cokelat", "tawar": "tawar",
           "biscuit": "biskuit", "biskut": "biskuit", "kripik": "keripik", "kopsus": "kopi susu"}
SINONIM_BAHAN = {"cokelat": "kakao", "coklat": "kakao", "cocoa": "kakao", "terigu": "tepung", "sawit": "minyak"}


def _kata(teks: str, sinonim: dict[str, str]) -> list[str]:
    teks = teks.lower()
    for a, b in sinonim.items():
        teks = re.sub(rf"\b{a}\b", b, teks)
    return [k for k in re.split(r"[^a-z0-9]+", teks) if len(k) > 1]


def _cocokkan(teks: str, kandidat: list[dict], sinonim: dict[str, str]) -> list[dict]:
    """Pilih kandidat yang paling banyak cocok kata-katanya dengan teks."""
    kata = _kata(teks, sinonim)
    if not kata:
        return []
    skor = []
    for k in kandidat:
        nama = " ".join(_kata(k["nama"], {})) + " " + k.get("kode", "").lower()
        s = sum(1 for w in kata if w in nama)
        if s:
            skor.append((s, k))
    if not skor:
        return []
    terbaik = max(s for s, _ in skor)
    return [k for s, k in skor if s == terbaik]


def _resolve_produk(teks: str) -> tuple[dict | None, dict | None]:
    """Kembalikan (produk, error). Error berisi saran bila tidak ketemu / ambigu."""
    semua = db.query("SELECT id, kode, nama, kategori, satuan, harga_jual FROM ai.v_produk ORDER BY nama")
    cocok = _cocokkan(teks, semua, SINONIM)
    if len(cocok) == 1:
        return cocok[0], None
    if not cocok:
        return None, {"error": f"Produk '{teks}' tidak ditemukan.",
                      "produk_tersedia": [p["nama"] for p in semua]}
    return None, {"error": f"Ada {len(cocok)} produk yang cocok dengan '{teks}'. Tanyakan ke user produk yang dimaksud.",
                  "kandidat": [p["nama"] for p in cocok]}


def _rentang_bulan(bulan_terakhir: int) -> tuple:
    bulan_terakhir = max(1, min(int(bulan_terakhir or 6), 18))
    akhir = db.info()["bulan_terakhir"]
    awal = fmt.tambah_bulan(akhir, -(bulan_terakhir - 1))
    return awal, akhir, bulan_terakhir


def _periode(awal, akhir) -> str:
    return fmt.bulan(akhir) if awal == akhir else f"{fmt.bulan(awal)} s.d. {fmt.bulan(akhir)}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@tool(
    nama="cari_produk",
    deskripsi="Mencari produk berdasarkan nama atau kode. Mengembalikan kode, nama, kategori, dan harga jual.",
    parameter={
        "type": "object",
        "properties": {
            "kata_kunci": {"type": "string", "description": "Nama atau kode produk, mis. 'roti cokelat'. Kosongkan untuk semua produk."},
        },
        "required": [],
    },
    izin="produk",
)
def cari_produk(kata_kunci: str = "") -> dict:
    semua = db.query("SELECT kode, nama, kategori, satuan, harga_jual FROM ai.v_produk ORDER BY kategori, nama")
    hasil = _cocokkan(kata_kunci, semua, SINONIM) if kata_kunci.strip() else semua
    for p in hasil:
        p["harga_jual_fmt"] = fmt.rupiah(p["harga_jual"])
    return {"jumlah": len(hasil), "produk": hasil}


@tool(
    nama="tren_penjualan",
    deskripsi=("Data penjualan per bulan (qty dan nilai rupiah) untuk satu produk atau seluruh produk, "
               "beserta perubahan dari bulan pertama ke bulan terakhir. Bisa dirinci per segmen customer atau per kota."),
    parameter={
        "type": "object",
        "properties": {
            "produk": {"type": "string", "description": "Nama produk, mis. 'Biskuit Kelapa'. Kosongkan untuk total semua produk."},
            "bulan_terakhir": {"type": "integer", "description": "Jumlah bulan ke belakang (1-18). Default 6."},
            "rincian": {"type": "string", "enum": ["total", "segmen", "kota"],
                        "description": "'segmen' atau 'kota' untuk melihat asal kenaikan/penurunan. Default 'total'."},
        },
        "required": [],
    },
    izin="penjualan",
)
def tren_penjualan(produk: str = "", bulan_terakhir: int = 6, rincian: str = "total") -> dict:
    awal, akhir, n = _rentang_bulan(bulan_terakhir)
    produk_id, nama = None, "Semua produk"
    if produk and produk.strip().lower() not in ("semua", "semua produk", "total", "all"):
        p, err = _resolve_produk(produk)
        if err:
            return err
        produk_id, nama = p["id"], p["nama"]

    baris = db.query(
        """
        SELECT bulan, sum(qty) AS qty, sum(nilai) AS nilai
        FROM ai.v_penjualan
        WHERE bulan BETWEEN %(awal)s AND %(akhir)s
          AND (%(pid)s::int IS NULL OR produk_id = %(pid)s::int)
        GROUP BY bulan ORDER BY bulan
        """,
        {"awal": awal, "akhir": akhir, "pid": produk_id},
    )
    if not baris:
        return {"produk": nama, "periode": _periode(awal, akhir), "data": [],
                "catatan": "Tidak ada data penjualan pada periode ini."}

    data = [{"bulan": fmt.bulan(b["bulan"]), "qty": b["qty"], "nilai": round(b["nilai"]),
             "nilai_fmt": fmt.rupiah(b["nilai"])} for b in baris]
    pertama, terakhir = baris[0], baris[-1]
    tertinggi = max(baris, key=lambda b: b["qty"])
    hasil: dict[str, Any] = {
        "produk": nama,
        "periode": _periode(awal, akhir),
        "data": data,
        "ringkasan": {
            "perubahan_qty_persen": fmt.persen(fmt.ubah_persen(pertama["qty"], terakhir["qty"])),
            "perubahan_nilai_persen": fmt.persen(fmt.ubah_persen(pertama["nilai"], terakhir["nilai"])),
            "dibandingkan": f"{fmt.bulan(pertama['bulan'])} vs {fmt.bulan(terakhir['bulan'])}",
            "total_nilai_periode_fmt": fmt.rupiah(sum(b["nilai"] for b in baris)),
            "bulan_qty_tertinggi": fmt.bulan(tertinggi["bulan"]),
        },
    }
    seri = [{"nama": "Qty (unit)", "data": [b["qty"] for b in baris]}]

    if rincian in ("segmen", "kota"):
        kolom = rincian  # nilai sudah dibatasi oleh enum; tetap dipetakan eksplisit
        kolom_sql = {"segmen": "segmen", "kota": "kota"}[kolom]
        per_dim = db.query(
            f"""
            SELECT {kolom_sql} AS dimensi, bulan, sum(qty) AS qty
            FROM ai.v_penjualan
            WHERE bulan BETWEEN %(awal)s AND %(akhir)s
              AND (%(pid)s::int IS NULL OR produk_id = %(pid)s::int)
            GROUP BY 1, 2 ORDER BY 1, 2
            """,
            {"awal": awal, "akhir": akhir, "pid": produk_id},
        )
        tabel: dict[str, dict] = {}
        for r in per_dim:
            tabel.setdefault(r["dimensi"], {})[r["bulan"]] = r["qty"]
        rinci = []
        for dim, nilai in tabel.items():
            q_awal, q_akhir = nilai.get(pertama["bulan"], 0), nilai.get(terakhir["bulan"], 0)
            rinci.append({kolom: dim, f"qty_{fmt.bulan_pendek(pertama['bulan'])}": q_awal,
                          f"qty_{fmt.bulan_pendek(terakhir['bulan'])}": q_akhir,
                          "selisih_qty": q_akhir - q_awal,
                          "perubahan_persen": fmt.persen(fmt.ubah_persen(q_awal, q_akhir))})
        rinci.sort(key=lambda r: -abs(r["selisih_qty"]))
        hasil["rincian_per_" + kolom] = rinci
        seri = [{"nama": dim, "data": [tabel[dim].get(b["bulan"], 0) for b in baris]}
                for dim in sorted(tabel, key=lambda d: -sum(tabel[d].values()))[:6]]

    hasil["grafik"] = {
        "tipe": "line",
        "judul": f"Penjualan {nama} (unit)" + ("" if rincian == "total" else f" per {rincian}"),
        "label": [fmt.bulan_pendek(b["bulan"]) for b in baris],
        "seri": seri,
    }
    return hasil


@tool(
    nama="penjualan_teratas",
    deskripsi=("Peringkat NILAI PENJUALAN (omzet) atau qty terjual teratas berdasarkan produk, customer, kota, segmen, "
               "atau kategori dalam beberapa bulan terakhir. Hanya untuk data penjualan, BUKAN untuk piutang atau tagihan."),
    parameter={
        "type": "object",
        "properties": {
            "dimensi": {"type": "string", "enum": ["produk", "customer", "kota", "segmen", "kategori"],
                        "description": "Dasar peringkat. Default 'produk'."},
            "bulan_terakhir": {"type": "integer", "description": "Jumlah bulan ke belakang (1-18). Default 3."},
            "urut": {"type": "string", "enum": ["nilai", "qty"], "description": "Urutkan berdasarkan nilai rupiah atau qty. Default 'nilai'."},
            "jumlah": {"type": "integer", "description": "Jumlah baris (1-20). Default 5."},
        },
        "required": [],
    },
    izin="penjualan",
)
def penjualan_teratas(dimensi: str = "produk", bulan_terakhir: int = 3, urut: str = "nilai", jumlah: int = 5) -> dict:
    kolom = {"produk": "produk", "customer": "customer", "kota": "kota", "segmen": "segmen", "kategori": "kategori"}.get(dimensi)
    if not kolom:
        return {"error": f"Dimensi '{dimensi}' tidak dikenal. Pilihan: produk, customer, kota, segmen, kategori."}
    urut_sql = "qty" if urut == "qty" else "nilai"
    jumlah = max(1, min(int(jumlah or 5), 20))
    awal, akhir, _ = _rentang_bulan(bulan_terakhir)
    baris = db.query(
        f"""
        SELECT {kolom} AS nama, sum(qty) AS qty, sum(nilai) AS nilai
        FROM ai.v_penjualan
        WHERE bulan BETWEEN %(awal)s AND %(akhir)s
        GROUP BY 1 ORDER BY {urut_sql} DESC LIMIT %(n)s
        """,
        {"awal": awal, "akhir": akhir, "n": jumlah},
    )
    total = db.query("SELECT sum(nilai) AS nilai FROM ai.v_penjualan WHERE bulan BETWEEN %(awal)s AND %(akhir)s",
                     {"awal": awal, "akhir": akhir})[0]["nilai"] or 0
    for i, b in enumerate(baris, 1):
        b["peringkat"] = i
        b["nilai"] = round(b["nilai"])
        b["nilai_fmt"] = fmt.rupiah(b["nilai"])
        b["porsi_dari_total"] = fmt.persen(b["nilai"] / total * 100 if total else None, tanda=False)
    return {
        "periode": _periode(awal, akhir),
        "dimensi": dimensi,
        "urut": urut_sql,
        "data": baris,
        "total_penjualan_periode_fmt": fmt.rupiah(total),
        "grafik": {
            "tipe": "bar",
            "judul": f"{jumlah} {dimensi} teratas ({'qty' if urut_sql == 'qty' else 'Rp juta'})",
            "label": [b["nama"] for b in baris],
            "seri": [{"nama": "Qty" if urut_sql == "qty" else "Nilai (Rp juta)",
                      "data": [b["qty"] if urut_sql == "qty" else round(b["nilai"] / 1e6, 1) for b in baris]}],
            "horizontal": True,
        },
    }


@tool(
    nama="rincian_hpp",
    deskripsi=("Rincian HPP (harga pokok produksi) per unit satu produk pada suatu bulan dibandingkan bulan sebelumnya: "
               "bahan baku per jenis bahan, tenaga kerja, overhead, dan margin. Gunakan untuk menjawab 'kenapa HPP naik/turun'."),
    parameter={
        "type": "object",
        "properties": {
            "produk": {"type": "string", "description": "Nama produk, mis. 'Roti Cokelat'."},
            "bulan": {"type": "string", "description": "Bulan format YYYY-MM. Kosongkan untuk bulan terakhir data."},
        },
        "required": ["produk"],
    },
    izin="hpp",
)
def rincian_hpp(produk: str, bulan: str = "") -> dict:
    p, err = _resolve_produk(produk)
    if err:
        return err
    akhir = db.info()["bulan_terakhir"]
    if bulan:
        try:
            tahun, bln = (int(x) for x in bulan[:7].split("-"))
            akhir = akhir.replace(year=tahun, month=bln)
        except ValueError:
            return {"error": f"Format bulan '{bulan}' tidak valid. Gunakan YYYY-MM."}
    sebelum = fmt.tambah_bulan(akhir, -1)

    hpp = {r["bulan"]: r for r in db.query(
        "SELECT * FROM ai.v_hpp_bulanan WHERE produk_id = %(pid)s AND bulan IN (%(a)s, %(b)s)",
        {"pid": p["id"], "a": sebelum, "b": akhir})}
    kini, lalu = hpp.get(akhir.isoformat()), hpp.get(sebelum.isoformat())
    if not kini or not lalu:
        return {"produk": p["nama"], "error": f"Data HPP untuk {fmt.bulan(akhir)} atau bulan sebelumnya tidak tersedia."}

    komp = db.query(
        """
        SELECT bahan, bulan, harga_bahan, biaya_per_unit
        FROM ai.v_hpp_komponen WHERE produk_id = %(pid)s AND bulan IN (%(a)s, %(b)s)
        """, {"pid": p["id"], "a": sebelum, "b": akhir})
    per_bahan: dict[str, dict] = {}
    for k in komp:
        key = "kini" if k["bulan"] == akhir.isoformat() else "lalu"
        per_bahan.setdefault(k["bahan"], {})[key] = k

    total_selisih = kini["hpp_per_unit"] - lalu["hpp_per_unit"]
    rinci = []
    for nama_bahan, v in per_bahan.items():
        if "kini" not in v or "lalu" not in v:
            continue
        selisih = v["kini"]["biaya_per_unit"] - v["lalu"]["biaya_per_unit"]
        rinci.append({
            "komponen": f"Bahan: {nama_bahan}",
            "biaya_per_unit_lalu": round(v["lalu"]["biaya_per_unit"]),
            "biaya_per_unit_kini": round(v["kini"]["biaya_per_unit"]),
            "selisih_fmt": fmt.rupiah_selisih(selisih),
            "perubahan_harga_bahan": fmt.persen(fmt.ubah_persen(v["lalu"]["harga_bahan"], v["kini"]["harga_bahan"])),
            "kontribusi_ke_kenaikan": fmt.persen(selisih / total_selisih * 100 if total_selisih else None, tanda=False),
            "_selisih": selisih,
        })
    for label, kol in (("Tenaga kerja", "tenaga_kerja_per_unit"), ("Overhead", "overhead_per_unit")):
        selisih = kini[kol] - lalu[kol]
        rinci.append({
            "komponen": label,
            "biaya_per_unit_lalu": round(lalu[kol]),
            "biaya_per_unit_kini": round(kini[kol]),
            "selisih_fmt": fmt.rupiah_selisih(selisih),
            "kontribusi_ke_kenaikan": fmt.persen(selisih / total_selisih * 100 if total_selisih else None, tanda=False),
            "_selisih": selisih,
        })
    rinci.sort(key=lambda r: -abs(r["_selisih"]))
    for r in rinci:
        r.pop("_selisih")

    harga_jual = p["harga_jual"]
    margin = lambda h: round((harga_jual - h) / harga_jual * 100, 1)  # noqa: E731
    utama = [r for r in rinci if r["selisih_fmt"] != "Rp 0"][:5]
    tetap = [r["komponen"].replace("Bahan: ", "") for r in rinci if r["selisih_fmt"] == "Rp 0"]
    return {
        "produk": p["nama"],
        "dibandingkan": f"{fmt.bulan(sebelum)} vs {fmt.bulan(akhir)}",
        "hpp_per_unit_lalu_fmt": fmt.rupiah(lalu["hpp_per_unit"]),
        "hpp_per_unit_kini_fmt": fmt.rupiah(kini["hpp_per_unit"]),
        "perubahan_hpp_persen": fmt.persen(fmt.ubah_persen(lalu["hpp_per_unit"], kini["hpp_per_unit"])),
        "harga_jual_fmt": fmt.rupiah(harga_jual),
        "margin_kotor_lalu": fmt.persen(margin(lalu["hpp_per_unit"]), tanda=False),
        "margin_kotor_kini": fmt.persen(margin(kini["hpp_per_unit"]), tanda=False),
        "komponen_terbesar_perubahannya": utama,
        "komponen_tidak_berubah": tetap,
        "grafik": {
            "tipe": "bar",
            "judul": f"Komponen HPP per unit {p['nama']} (Rp)",
            "label": [r["komponen"].replace("Bahan: ", "") for r in utama],
            "seri": [{"nama": fmt.bulan_pendek(sebelum), "data": [r["biaya_per_unit_lalu"] for r in utama]},
                     {"nama": fmt.bulan_pendek(akhir), "data": [r["biaya_per_unit_kini"] for r in utama]}],
        },
    }


@tool(
    nama="riwayat_harga_bahan",
    deskripsi="Riwayat harga rata-rata pembelian satu bahan baku per bulan, mis. kakao bubuk, gula pasir, tepung terigu.",
    parameter={
        "type": "object",
        "properties": {
            "bahan": {"type": "string", "description": "Nama bahan baku, mis. 'kakao bubuk'."},
            "bulan_terakhir": {"type": "integer", "description": "Jumlah bulan ke belakang (1-18). Default 6."},
        },
        "required": ["bahan"],
    },
    izin="hpp",
)
def riwayat_harga_bahan(bahan: str, bulan_terakhir: int = 6) -> dict:
    semua = db.query("SELECT DISTINCT bahan_id AS id, kode, bahan AS nama, satuan FROM ai.v_harga_bahan ORDER BY nama")
    cocok = _cocokkan(bahan, semua, SINONIM_BAHAN)
    if len(cocok) != 1:
        return {"error": f"Bahan '{bahan}' tidak ditemukan atau ambigu.",
                "bahan_tersedia": [b["nama"] for b in (cocok or semua)]}
    b = cocok[0]
    awal, akhir, _ = _rentang_bulan(bulan_terakhir)
    baris = db.query(
        """
        SELECT bulan, harga FROM ai.v_harga_bahan
        WHERE bahan_id = %(id)s AND bulan BETWEEN %(awal)s AND %(akhir)s ORDER BY bulan
        """, {"id": b["id"], "awal": awal, "akhir": akhir})
    data, sebelumnya = [], None
    for r in baris:
        data.append({"bulan": fmt.bulan(r["bulan"]), "harga_fmt": fmt.rupiah(r["harga"]) + f"/{b['satuan']}",
                     "perubahan_dari_bulan_sebelumnya": fmt.persen(fmt.ubah_persen(sebelumnya, r["harga"])) if sebelumnya else "-"})
        sebelumnya = r["harga"]
    return {
        "bahan": b["nama"],
        "periode": _periode(awal, akhir),
        "data": data,
        "perubahan_total": fmt.persen(fmt.ubah_persen(baris[0]["harga"], baris[-1]["harga"])) if baris else "-",
        "grafik": {
            "tipe": "line",
            "judul": f"Harga {b['nama']} (Rp/{b['satuan']})",
            "label": [fmt.bulan_pendek(r["bulan"]) for r in baris],
            "seri": [{"nama": b["nama"], "data": [r["harga"] for r in baris]}],
        },
    }


@tool(
    nama="produk_pengguna_bahan",
    deskripsi=("Daftar produk yang memakai satu bahan baku beserta porsi bahan itu dalam HPP-nya bulan terakhir. "
               "Gunakan untuk melihat produk lain yang ikut terdampak kenaikan harga suatu bahan."),
    parameter={
        "type": "object",
        "properties": {
            "bahan": {"type": "string", "description": "Nama bahan baku, mis. 'kakao bubuk'."},
        },
        "required": ["bahan"],
    },
    izin="hpp",
)
def produk_pengguna_bahan(bahan: str) -> dict:
    semua = db.query("SELECT DISTINCT bahan_id AS id, bahan AS nama FROM ai.v_harga_bahan ORDER BY nama")
    cocok = _cocokkan(bahan, semua, SINONIM_BAHAN)
    if len(cocok) != 1:
        return {"error": f"Bahan '{bahan}' tidak ditemukan atau ambigu.",
                "bahan_tersedia": [b["nama"] for b in (cocok or semua)]}
    b = cocok[0]
    akhir = db.info()["bulan_terakhir"]
    baris = db.query(
        """
        SELECT k.produk, k.biaya_per_unit, h.hpp_per_unit
        FROM ai.v_hpp_komponen k
        JOIN ai.v_hpp_bulanan h ON h.produk_id = k.produk_id AND h.bulan = k.bulan
        WHERE k.bahan_id = %(id)s AND k.bulan = %(bln)s
        ORDER BY k.biaya_per_unit / h.hpp_per_unit DESC
        """, {"id": b["id"], "bln": akhir})
    return {
        "bahan": b["nama"],
        "bulan": fmt.bulan(akhir),
        "produk": [{"produk": r["produk"], "biaya_bahan_per_unit_fmt": fmt.rupiah(r["biaya_per_unit"]),
                    "porsi_dalam_hpp": fmt.persen(r["biaya_per_unit"] / r["hpp_per_unit"] * 100, tanda=False)}
                   for r in baris],
    }


@tool(
    nama="cari_dokumen",
    deskripsi=("Mencari isi dokumen internal perusahaan (SOP, kebijakan, panduan, FAQ aplikasi). Isi dokumen "
               "TIDAK diketahui sebelum tool ini dipanggil. Wajib dipakai untuk pertanyaan tentang aturan, prosedur, "
               "batas waktu, persetujuan, wewenang, atau kebijakan."),
    parameter={
        "type": "object",
        "properties": {
            "pertanyaan": {"type": "string", "description": "Pertanyaan atau kata kunci yang dicari di dokumen."},
        },
        "required": ["pertanyaan"],
    },
    izin="dokumen",
)
def cari_dokumen(pertanyaan: str) -> dict:
    from . import rag  # impor di sini agar tools lain tetap jalan walau RAG belum disiapkan
    try:
        potongan = rag.cari(pertanyaan, k=4)  # + koleksi peserta bila RAG_KOLEKSI diisi (Sesi 2.4)
    except ValueError as e:
        return {"error": str(e)}
    if not potongan:
        return {"hasil": [], "catatan": "Tidak ada dokumen yang relevan."}
    hasil = []
    for p in potongan:
        h = {"sumber": p["sumber"]}
        if p.get("nomor"):
            h["nomor_dokumen"] = p["nomor"]
        if p.get("berlaku"):
            h["berlaku"] = p["berlaku"]
        h.update({"bagian": p["bagian"], "isi": p["isi"], "skor_kemiripan": round(p["skor"], 2)})
        if "koleksi" in p:
            h["koleksi"] = p["koleksi"]
        hasil.append(h)
    return {
        "hasil": hasil,
        "catatan": "Jawab hanya berdasarkan isi di atas dan sebutkan sumbernya (judul dan nomor dokumen).",
    }


# Tool tambahan (latihan peserta / demo live) dimuat otomatis bila ada.
try:
    from . import tools_tambahan  # noqa: F401,E402
except ImportError as e:  # pragma: no cover
    if "tools_tambahan" not in str(e):
        raise
