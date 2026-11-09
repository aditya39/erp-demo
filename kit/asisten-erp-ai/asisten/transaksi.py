"""
Tool transaksi: menyiapkan DRAFT sales order dari permintaan user.

Pembagian peran saat asisten AI membantu membuat transaksi:
  1. AI hanya MENGISI FORMULIR: siapkan_draft_so mencocokkan customer, produk,
     qty, dan gudang, lalu mengembalikan draft (belum disimpan).
  2. SISTEM ERP menghitung harga akhir, diskon segmen, dan persetujuan (simulasi).
  3. MANUSIA memeriksa draft lalu menekan Simpan (atau menjawab "ya").
  4. KODE aplikasi (bukan model) yang memanggil POST /api/sales-order.

Model TIDAK pernah diberi tool untuk menyimpan. Tool di sini hanya membaca view
schema "ai" lewat role read-only: tidak menulis ke database dan tidak memanggil
API ERP. Hasilnya memuat "payload" yang siap dikirim aplikasi ke ERP setelah
user mengonfirmasi.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import db
from . import format as fmt
from .tools import SINONIM, _cocokkan, _kata, _resolve_produk, tool

GUDANG = ["Gudang Jakarta", "Gudang Surabaya"]
# Customer di kota ini dilayani Gudang Surabaya; kota lain dari Gudang Jakarta.
KOTA_GUDANG_SURABAYA = {"surabaya", "makassar", "denpasar"}
# Satuan produk di ERP beserta variasi penulisannya. Qty selalu dalam satuan produk.
SATUAN_PRODUK = {
    "pak": ("pak", "paks"),
    "botol": ("botol", "btl", "bottle", "bottles"),
    "pcs": ("pcs", "pc", "buah", "biji", "piece", "pieces"),
    "bungkus": ("bungkus", "bks", "bungkusan"),
}
# Kemasan lain yang sering disebut user, tetapi konversinya belum ada di sistem: jangan ditebak.
SATUAN_LAIN = ("karton", "kardus", "dus", "dos", "box", "boks", "kotak", "lusin", "krat", "pack", "packs",
               "bal", "renteng", "slop", "ikat", "sak", "kodi", "pallet", "palet")
SATUAN_NETRAL = ("unit", "x", "×")            # tidak menyebut kemasan apa pun
KATA_SATUAN = ({k: s for s, daftar in SATUAN_PRODUK.items() for k in daftar}
               | {k: k for k in SATUAN_LAIN} | {k: "" for k in SATUAN_NETRAL})
SATUAN = "|".join(sorted(map(re.escape, KATA_SATUAN), key=len, reverse=True))
POLA_SATUAN = rf"(?<![^\W\d_])(?:{SATUAN})(?![^\W\d_])"   # kata utuh; boleh menempel angka ("50pak")
# Angka qty dalam teks bebas: "50 pak", "50pak", "1.000" — bukan bagian nama seperti "200g" atau "350ml".
ANGKA_QTY = rf"(?<![\w.,])-?\d[\d.,]*(?=\s|$|[;:)]|{POLA_SATUAN})"
# Nama field yang kadang dipakai model kecil selain "produk", "qty", dan "satuan".
KUNCI_PRODUK = ("produk", "nama", "nama_produk", "product", "name", "kode")
KUNCI_QTY = ("qty", "jumlah", "quantity", "kuantitas")
KUNCI_SATUAN = ("satuan", "unit", "uom")
# Kata permintaan yang boleh tidak ada di nama katalog (bukan pembeda produk / customer).
KATA_PENGISI = {"rasa", "ukuran", "isi", "produk", "merk", "merek", "varian", "dan", "yang", "untuk",
                "customer", "pelanggan", "cabang"}
POLA_UKURAN = r"\d+(?:[.,]\d+)?(?:g|gr|gram|kg|ml|l|lt|liter|cc)?|g|gr|gram|kg|ml|l|lt|liter|cc"


# ---------------------------------------------------------------------------
# Merapikan argumen dari model (model kecil kadang mengirim bentuk yang berbeda)
# ---------------------------------------------------------------------------
def _qty(nilai: Any) -> int | None:
    """'50', '50 pak', '1.000' (format Indonesia), 20.0 -> int. None bila bukan bilangan bulat."""
    if isinstance(nilai, bool) or nilai is None:
        return None
    if isinstance(nilai, (int, float)):
        return int(nilai) if float(nilai).is_integer() else None
    cocok = re.search(r"-?\d[\d.,]*", str(nilai))
    if not cocok:
        return None
    teks = cocok.group().rstrip(".,")
    if re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", teks):    # pemisah ribuan: 1.000 / 1,000
        teks = re.sub(r"[.,]", "", teks)
    try:
        angka = float(teks.replace(",", "."))
    except ValueError:
        return None
    return int(angka) if angka.is_integer() else None


def _persen(nilai: Any) -> float | None:
    """2, '2', '2%', '2,5 %' -> float. Kosong -> 0. None bila tidak valid."""
    if nilai is None or (isinstance(nilai, str) and not nilai.strip()):
        return 0.0
    if isinstance(nilai, bool):
        return None
    try:
        return float(str(nilai).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def _kata_satuan(teks: Any) -> list[str]:
    """Kata satuan yang disebut di teks: '5 karton' -> ['karton'], '50pak' -> ['pak']."""
    return [k.lower() for k in re.findall(POLA_SATUAN, str(teks or ""), flags=re.I)]


def _item_dari_teks(teks: str) -> list[dict]:
    """
    '50 pak Biskuit Kelapa dan 20 botol Teh Melati'
      -> [{'produk': 'Biskuit Kelapa', 'qty': '50', 'satuan': 'pak'}, ...]
    Kata satuan dibuang dari nama produk tetapi disimpan di 'satuan' (dicek setelah produk dikenali).
    """
    hasil = []
    for bagian in re.split(r",|;|\n|\+|&|\bdan\b", teks):
        bagian = bagian.strip(" .:-")
        if not bagian:
            continue
        cocok = re.search(ANGKA_QTY, bagian, flags=re.I)
        qty = cocok.group() if cocok else None
        nama = bagian[:cocok.start()] + " " + bagian[cocok.end():] if cocok else bagian
        x = {"produk": " ".join(re.sub(POLA_SATUAN, " ", nama, flags=re.I).split()).strip(" .:-"), "qty": qty}
        if _kata_satuan(bagian):
            x["satuan"] = " ".join(_kata_satuan(bagian))
        hasil.append(x)
    return hasil


def _rapikan_item(item: Any) -> list[dict]:
    """
    Terima beberapa bentuk 'item' lalu ubah ke [{'produk': str, 'qty': nilai mentah}]:
    list of dict (bentuk baku), satu dict, dict {'nama produk': qty}, teks bebas,
    teks JSON, atau list of [produk, qty].
    """
    if isinstance(item, str):
        try:
            return _rapikan_item(json.loads(item))
        except (json.JSONDecodeError, RecursionError):
            return _item_dari_teks(item)
    if isinstance(item, dict):
        if set(KUNCI_PRODUK + KUNCI_QTY + KUNCI_SATUAN) & set(item):
            item = [item]
        else:  # {"Biskuit Kelapa": 50, "Teh Melati": 20}
            item = [{"produk": k, "qty": v} for k, v in item.items()]
    if not isinstance(item, (list, tuple)):
        return []
    hasil = []
    for x in item:
        if isinstance(x, dict):
            produk = next((x[k] for k in KUNCI_PRODUK if x.get(k)), "")
            qty = next((x[k] for k in KUNCI_QTY if x.get(k) is not None), None)
            satuan = next((str(x[k]).strip() for k in KUNCI_SATUAN if x.get(k)), "")
            hasil.append({"produk": str(produk).strip(), "qty": qty, **({"satuan": satuan} if satuan else {})})
        elif isinstance(x, (list, tuple)) and len(x) == 2:
            a, b = x
            hasil.append({"produk": str(b), "qty": a} if _qty(a) is not None and _qty(b) is None
                         else {"produk": str(a), "qty": b})
        elif isinstance(x, str):
            hasil += _item_dari_teks(x)
    return hasil


def _kata_tidak_cocok(teks: str, nama: str, tambahan: str = "", sinonim: dict | None = None) -> list[str]:
    """
    Kata permintaan (3+ huruf) yang tidak ada di nama katalog, mis. 'Nastar Keju' vs 'Roti Keju' -> ['nastar'].
    Satuan, ukuran (200g, 350ml), angka, dan kata pengisi diabaikan. `tambahan`: kata lain yang sah (kode, kota).
    """
    def token(t: str, sin: dict) -> list[str]:
        return [k for w in _kata(t, sin) for k in re.findall(r"[a-z]+|\d+[a-z]*", w)]

    ada = set(token(f"{nama} {tambahan}", {}))
    return [w for w in token(teks, SINONIM if sinonim is None else sinonim)
            if len(w) >= 3 and w not in ada and w not in KATA_SATUAN and w not in KATA_PENGISI
            and not re.fullmatch(POLA_UKURAN, w)]


def _cek_satuan(x: dict, p: dict) -> dict | None:
    """
    Error bila user menyebut satuan selain satuan produk (mis. 'karton', atau 'botol' untuk produk 'pak').
    Tanpa satuan, atau satuan yang sama dengan satuan produk, dianggap benar. Kata yang memang bagian
    nama produk (mis. 'Botol' di 'Teh Melati Botol 350ml') tidak dihitung sebagai satuan.
    """
    satuan_produk = str(p["satuan"]).lower()
    nama_produk = set(re.findall(r"[^\W_]+", p["nama"].lower()))
    sebut = _kata_satuan(x.get("satuan")) + [k for k in _kata_satuan(x["produk"]) if k not in nama_produk]
    for kata in sebut:
        if KATA_SATUAN.get(kata, kata) not in ("", satuan_produk):
            return {"error": f"Satuan '{kata}' belum dikenal sistem untuk {p['nama']} (satuan: {p['satuan']}). "
                             f"Tanyakan ke user jumlahnya dalam {p['satuan']}.", "kandidat": []}
    return None


def _gudang(teks: str) -> str | None:
    """'surabaya' / 'Gudang Surabaya' -> 'Gudang Surabaya'. None bila tidak dikenal."""
    rendah = " ".join(str(teks).lower().split())
    return next((g for g in GUDANG if rendah in (g.lower(), g.lower().removeprefix("gudang "))), None)


def _resolve_customer(teks: str) -> tuple[dict | None, dict | None]:
    """Kembalikan (customer, error). Nama/kode persis diutamakan, lalu pencocokan kata."""
    semua = db.query("SELECT id, kode, nama, segmen, kota, termin_hari FROM ai.v_customer ORDER BY nama")
    rendah = " ".join(teks.lower().split())
    cocok = [c for c in semua if rendah in (c["nama"].lower(), c["kode"].lower())] or _cocokkan(teks, semua, {})
    if len(cocok) == 1:
        c = cocok[0]
        # "Toko Nusantara Jaya" tidak boleh diam-diam menjadi "Toko Makmur Jaya". Teks setelah koma/kurung
        # (mis. alamat dari email) tidak ikut diperiksa; kode dan kota customer boleh disebut.
        if _kata_tidak_cocok(re.split(r"[,(]| - ", teks)[0], c["nama"], f"{c['kode']} {c['kota']}", {}):
            return None, {"error": f"Customer '{teks}' tidak persis cocok dengan data customer. Yang paling mirip: "
                                   f"{c['nama']}. Tanyakan ke user apakah ini yang dimaksud.", "kandidat": [c["nama"]]}
        return c, None
    if not cocok:
        return None, {"error": f"Customer '{teks}' tidak ditemukan. Tanyakan ke user nama customer yang benar.",
                      "kandidat": []}
    return None, {"error": f"Ada {len(cocok)} customer yang cocok dengan '{teks}'. Tanyakan ke user customer yang dimaksud.",
                  "kandidat": [c["nama"] for c in cocok[:10]]}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------
@tool(
    nama="siapkan_draft_so",
    deskripsi=("Menyiapkan DRAFT sales order (SO) dari permintaan user, mis. 'buatkan SO untuk Toko Murah Meriah: "
               "50 pak Biskuit Kelapa dan 20 botol Teh Melati'. Mencocokkan customer, produk, dan stok gudang. "
               "Tool ini TIDAK menyimpan SO: draft diperiksa dan disimpan sendiri oleh user di aplikasi ERP."),
    parameter={
        "type": "object",
        "properties": {
            "customer": {"type": "string", "description": "Nama atau kode customer, mis. 'Toko Murah Meriah'."},
            "item": {
                "type": "array",
                "description": "Daftar produk yang dipesan, mis. [{\"produk\": \"Biskuit Kelapa\", \"qty\": 50}].",
                "items": {
                    "type": "object",
                    "properties": {
                        "produk": {"type": "string", "description": "Nama produk, mis. 'Biskuit Kelapa'."},
                        "qty": {"type": "integer", "description": "Jumlah dalam satuan produk (pak/botol/pcs/bungkus)."},
                        "satuan": {"type": "string",
                                   "description": "Satuan yang disebut user, salin apa adanya (mis. 'pak', 'karton'). "
                                                  "Kosongkan bila user tidak menyebut satuan. Jangan dikonversi sendiri."},
                    },
                    "required": ["produk", "qty"],
                },
            },
            "gudang": {"type": "string", "enum": GUDANG,
                       "description": "Gudang pengirim. Kosongkan bila user tidak menyebutkan (dipilih dari kota customer)."},
            "diskon_tambahan": {"type": "number",
                                "description": "Diskon tambahan di luar diskon segmen, dalam persen (2 berarti 2%). Default 0."},
            "catatan": {"type": "string", "description": "Catatan untuk SO, mis. 'kirim sebelum Jumat'. Opsional."},
        },
        "required": ["customer", "item"],
    },
    izin="so_buat",
)
def siapkan_draft_so(customer: str, item: Any, gudang: str = "", diskon_tambahan: Any = 0,
                     catatan: str = "") -> dict:
    # 1. Periksa isian dulu (tanpa query) agar model bisa langsung bertanya balik ke user.
    daftar = _rapikan_item(item)
    if not daftar:
        return {"error": "Daftar item kosong. Tanyakan ke user produk dan qty yang dipesan.", "kandidat": []}
    for x in daftar:
        if not x["produk"]:
            return {"error": "Ada item tanpa nama produk. Tanyakan ke user produk yang dimaksud.", "kandidat": []}
        qty = _qty(x["qty"])
        if qty is None or qty <= 0:
            return {"error": f"Qty untuk '{x['produk']}' tidak valid ({x['qty']}). Qty harus bilangan bulat lebih "
                             "dari 0. Tanyakan ke user jumlah yang dipesan.", "kandidat": []}
        if isinstance(x["qty"], str) and _kata_satuan(x["qty"]):   # "5 karton": satuannya diperiksa di langkah 2
            x["satuan"] = " ".join([x.get("satuan", "")] + _kata_satuan(x["qty"])).strip()
        x["qty"] = qty
    diskon = _persen(diskon_tambahan)
    if diskon is None or not 0 <= diskon < 100:
        return {"error": f"Diskon tambahan '{diskon_tambahan}' tidak valid. Isi dalam persen, mis. 2 untuk 2%.",
                "kandidat": []}
    gudang_pilihan = _gudang(gudang) if gudang else None
    if gudang and not gudang_pilihan:
        return {"error": f"Gudang '{gudang}' tidak dikenal.", "kandidat": GUDANG}

    # 2. Cocokkan customer dan produk (hanya SELECT ke view schema "ai").
    cust, err = _resolve_customer(str(customer))
    if err:
        return err
    baris: list[dict] = []
    for x in daftar:
        p, err = _resolve_produk(x["produk"])
        if err:
            return {"error": err["error"], "kandidat": err.get("kandidat") or err.get("produk_tersedia", [])}
        if _kata_tidak_cocok(x["produk"], p["nama"], p["kode"]):    # "Nastar Keju" bukan "Roti Keju"
            return {"error": f"Produk '{x['produk']}' tidak persis cocok dengan katalog. Yang paling mirip: "
                             f"{p['nama']}. Tanyakan ke user apakah ini yang dimaksud.", "kandidat": [p["nama"]]}
        err = _cek_satuan(x, p)      # "5 karton" tidak boleh diam-diam menjadi 5 pak
        if err:
            return err
        sama =next((b for b in baris if b["produk"]["id"] == p["id"]), None)
        if sama:
            sama["qty"] += x["qty"]
        else:
            baris.append({"produk": p, "qty": x["qty"]})

    gudang_otomatis = gudang_pilihan is None
    if gudang_otomatis:
        gudang_pilihan = GUDANG[1] if cust["kota"].lower() in KOTA_GUDANG_SURABAYA else GUDANG[0]
    stok = {r["produk_id"]: r["qty"] for r in db.query(
        "SELECT produk_id, qty FROM ai.v_stok WHERE gudang = %(gudang)s AND produk_id = ANY(%(ids)s)",
        {"gudang": gudang_pilihan, "ids": [b["produk"]["id"] for b in baris]})}

    # 3. Susun draft. Angka dihitung kode; harga akhir & persetujuan dihitung sistem ERP saat simulasi.
    peringatan, item_draft = [], []
    if len(baris) < len(daftar):
        peringatan.append("Ada produk yang disebut lebih dari sekali; qty-nya digabung.")
    for b in baris:
        p, qty = b["produk"], b["qty"]
        ada = stok.get(p["id"])
        if ada is None:
            peringatan.append(f"Stok {p['nama']} di {gudang_pilihan} tidak tercatat.")
        elif ada < qty:
            peringatan.append(f"Stok {p['nama']} di {gudang_pilihan} {fmt.angka(ada)} {p['satuan']}, kurang dari "
                              f"qty yang diminta ({fmt.angka(qty)} {p['satuan']}).")
        item_draft.append({"produk_id": p["id"], "kode": p["kode"], "nama": p["nama"], "satuan": p["satuan"],
                           "qty": qty, "harga_daftar": p["harga_jual"], "harga_daftar_fmt": fmt.rupiah(p["harga_jual"]),
                           "stok_gudang": ada})
    bruto = float(sum(i["qty"] * i["harga_daftar"] for i in item_draft))
    catatan = str(catatan or "").strip()
    return {
        "status": "DRAFT_BELUM_DISIMPAN",
        "draft_so": {
            "customer": {k: cust[k] for k in ("id", "kode", "nama", "segmen", "kota", "termin_hari")},
            "gudang": gudang_pilihan,
            "gudang_otomatis": gudang_otomatis,
            "diskon_tambahan": diskon,
            "catatan": catatan,
            "item": item_draft,
            "nilai_bruto": bruto,
            "nilai_bruto_fmt": f"Rp {fmt.angka(bruto)}",   # persis (bukan "Rp 29,7 juta"): ini isian formulir
            # Body untuk POST /api/sales-order (tanpa "tanggal"). Dikirim oleh KODE aplikasi setelah user setuju.
            "payload": {"customer_id": cust["id"], "gudang": gudang_pilihan, "diskon_tambahan": diskon,
                        "catatan": catatan, "item": [{"produk_id": i["produk_id"], "qty": i["qty"]} for i in item_draft]},
        },
        "peringatan": peringatan,
        # Kalimat ini aman bila diulang model ke user (model kecil kadang menyalinnya apa adanya).
        "catatan": ("Draft BELUM disimpan. Rangkum draft ini untuk user, lalu minta user memeriksa kartu draft dan "
                    "menekan Simpan (atau menjawab 'ya' bila diminta konfirmasi). Harga akhir, diskon segmen, dan "
                    "persetujuan dihitung oleh sistem ERP; nilai_bruto hanya perkiraan dari harga daftar sebelum diskon."
                    + (" Gudang dipilih otomatis dari kota customer." if gudang_otomatis else "")),
    }
