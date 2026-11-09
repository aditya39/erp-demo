#!/usr/bin/env python3
"""
Generator data dummy ERP untuk PT Nusantara Rasa (perusahaan fiktif).

Menghasilkan db/init/02_seed.sql. Hasilnya deterministik (seed acak tetap),
jadi semua laptop peserta mendapat data yang sama persis.

Pola yang sengaja ditanam supaya demo punya "cerita":
  - Biskuit Kelapa 200g  : penjualan naik tajam 3 bulan terakhir, terutama di
                           segmen Retail Modern; stok di Gudang Surabaya menipis.
  - Biskuit Susu 300g    : penjualan turun pelan 6 bulan terakhir.
  - Roti Cokelat         : HPP naik di bulan terakhir karena harga kakao bubuk
                           melonjak (+ gula naik sedikit).
  - Musim Lebaran        : biskuit, keripik, dan minuman naik di bulan Lebaran.
  - Piutang              : beberapa customer telat bayar (CV Laju Makmur Abadi
                           paling besar).

Pemakaian:
    python3 db/generate_seed.py --bulan-akhir 2026-10   # data workshop: Mei 2025 s.d. Oktober 2026, posisi 31-10-2026
    python3 db/generate_seed.py                         # tanpa argumen: bulan terakhir = bulan lalu dari hari ini
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import random
from pathlib import Path

JUMLAH_BULAN = 18
SKALA_VOLUME = 4          # pengali volume supaya omzet setara perusahaan menengah
RNG = random.Random(20261002)

KATEGORI = ["Biskuit", "Roti", "Keripik", "Minuman"]

# kode, nama, kategori, satuan, harga jual awal, volume dasar per bulan, TK/unit, overhead tetap/bulan
PRODUK = [
    ("BSK-001", "Biskuit Kelapa 200g", "Biskuit", "pak", 9500, 5200, 520, 2_600_000),
    ("BSK-002", "Biskuit Cokelat 200g", "Biskuit", "pak", 10500, 6100, 540, 3_000_000),
    ("BSK-003", "Wafer Vanila 150g", "Biskuit", "pak", 8000, 4800, 480, 2_300_000),
    ("BSK-004", "Biskuit Susu 300g", "Biskuit", "pak", 14500, 3900, 650, 2_400_000),
    ("ROT-001", "Roti Tawar Gandum", "Roti", "bungkus", 16000, 4200, 900, 3_200_000),
    ("ROT-002", "Roti Cokelat", "Roti", "pcs", 6500, 9800, 380, 3_400_000),
    ("ROT-003", "Roti Keju", "Roti", "pcs", 7000, 8200, 380, 3_000_000),
    ("ROT-004", "Roti Sobek Pandan", "Roti", "bungkus", 18000, 2600, 950, 2_000_000),
    ("KRP-001", "Keripik Singkong Balado 100g", "Keripik", "pak", 7500, 5600, 420, 2_100_000),
    ("KRP-002", "Keripik Pisang Manis 100g", "Keripik", "pak", 8500, 3300, 450, 1_500_000),
    ("MNM-001", "Teh Melati Botol 350ml", "Minuman", "botol", 5000, 12500, 160, 3_800_000),
    ("MNM-002", "Kopi Susu Botol 250ml", "Minuman", "botol", 9000, 7400, 220, 3_100_000),
]

# kode, nama, satuan, harga awal
BAHAN = [
    ("BHN-001", "Tepung terigu", "kg", 11000),
    ("BHN-002", "Gula pasir", "kg", 17000),
    ("BHN-003", "Minyak sawit", "liter", 16000),
    ("BHN-004", "Mentega", "kg", 65000),
    ("BHN-005", "Susu bubuk", "kg", 85000),
    ("BHN-006", "Kakao bubuk", "kg", 120000),
    ("BHN-007", "Kelapa parut kering", "kg", 40000),
    ("BHN-008", "Keju cheddar", "kg", 140000),
    ("BHN-009", "Telur", "kg", 28000),
    ("BHN-010", "Ragi", "kg", 90000),
    ("BHN-011", "Singkong", "kg", 6000),
    ("BHN-012", "Pisang", "kg", 12000),
    ("BHN-013", "Bumbu balado", "kg", 70000),
    ("BHN-014", "Daun teh melati", "kg", 95000),
    ("BHN-015", "Kopi bubuk", "kg", 150000),
    ("BHN-016", "Perisa pandan", "liter", 60000),
    ("BHN-017", "Kemasan plastik", "pcs", 450),
    ("BHN-018", "Botol PET", "pcs", 1200),
]

# kebutuhan bahan per 1 unit produk
RESEP = {
    "BSK-001": {"BHN-001": 0.090, "BHN-002": 0.030, "BHN-003": 0.020, "BHN-007": 0.030, "BHN-017": 1},
    "BSK-002": {"BHN-001": 0.090, "BHN-002": 0.035, "BHN-003": 0.020, "BHN-006": 0.015, "BHN-017": 1},
    "BSK-003": {"BHN-001": 0.060, "BHN-002": 0.040, "BHN-003": 0.025, "BHN-005": 0.008, "BHN-017": 1},
    "BSK-004": {"BHN-001": 0.140, "BHN-002": 0.040, "BHN-004": 0.020, "BHN-005": 0.030, "BHN-017": 1},
    "ROT-001": {"BHN-001": 0.300, "BHN-002": 0.015, "BHN-004": 0.012, "BHN-010": 0.004, "BHN-017": 1},
    "ROT-002": {"BHN-001": 0.050, "BHN-002": 0.014, "BHN-004": 0.006, "BHN-006": 0.013,
                "BHN-009": 0.010, "BHN-010": 0.001, "BHN-017": 1},
    "ROT-003": {"BHN-001": 0.050, "BHN-002": 0.010, "BHN-004": 0.006, "BHN-008": 0.012,
                "BHN-009": 0.010, "BHN-010": 0.001, "BHN-017": 1},
    "ROT-004": {"BHN-001": 0.250, "BHN-002": 0.030, "BHN-004": 0.020, "BHN-009": 0.030,
                "BHN-010": 0.004, "BHN-016": 0.003, "BHN-017": 1},
    "KRP-001": {"BHN-011": 0.250, "BHN-003": 0.030, "BHN-013": 0.008, "BHN-017": 1},
    "KRP-002": {"BHN-012": 0.300, "BHN-003": 0.030, "BHN-002": 0.012, "BHN-017": 1},
    "MNM-001": {"BHN-014": 0.004, "BHN-002": 0.025, "BHN-018": 1},
    "MNM-002": {"BHN-015": 0.008, "BHN-005": 0.015, "BHN-002": 0.020, "BHN-018": 1},
}

KOTA = ["Jakarta", "Bandung", "Surabaya", "Semarang", "Medan", "Makassar", "Denpasar", "Yogyakarta"]

# nama, kota, segmen, bobot pembelian
CUSTOMER = [
    ("CV Sinar Distribusi Pangan", "Jakarta", "Distributor", 9.0),
    ("PT Mitra Niaga Sejahtera", "Surabaya", "Distributor", 8.0),
    ("CV Andalan Logistik Boga", "Bandung", "Distributor", 6.5),
    ("PT Prima Sentosa Distribusi", "Medan", "Distributor", 6.0),
    ("CV Laju Makmur Abadi", "Semarang", "Distributor", 7.0),
    ("PT Samudra Boga Timur", "Makassar", "Distributor", 5.0),
    ("CV Dewata Niaga", "Denpasar", "Distributor", 4.5),
    ("PT Jogja Distribusi Utama", "Yogyakarta", "Distributor", 4.5),
    ("Swalayan Sentosa", "Jakarta", "Retail Modern", 3.6),
    ("Mart Harian Kita", "Bandung", "Retail Modern", 2.8),
    ("Pasar Swalayan Nusa", "Surabaya", "Retail Modern", 3.4),
    ("Toserba Mulia", "Semarang", "Retail Modern", 2.4),
    ("Swalayan Segar Jaya", "Medan", "Retail Modern", 2.6),
    ("Grand Swalayan Prima", "Jakarta", "Retail Modern", 3.2),
    ("Toserba Cahaya Baru", "Surabaya", "Retail Modern", 2.9),
    ("Swalayan Pelangi", "Yogyakarta", "Retail Modern", 2.1),
    ("Mart Sehati", "Denpasar", "Retail Modern", 2.0),
    ("Swalayan Anugerah", "Makassar", "Retail Modern", 2.2),
    ("Toserba Bintang", "Bandung", "Retail Modern", 2.3),
    ("Swalayan Keluarga", "Surabaya", "Retail Modern", 2.5),
    ("Toko Berkah Abadi", "Jakarta", "Toko", 1.2),
    ("Toko Sumber Rezeki", "Jakarta", "Toko", 0.9),
    ("Toko Makmur Jaya", "Bandung", "Toko", 0.8),
    ("Toko Barokah", "Surabaya", "Toko", 1.0),
    ("Toko Sinar Terang", "Surabaya", "Toko", 0.7),
    ("Toko Rejeki Lancar", "Semarang", "Toko", 0.8),
    ("Toko Maju Bersama", "Medan", "Toko", 0.9),
    ("Toko Sido Mulyo", "Yogyakarta", "Toko", 0.7),
    ("Toko Harapan Baru", "Makassar", "Toko", 1.1),
    ("Toko Cahaya Pagi", "Denpasar", "Toko", 0.6),
    ("Toko Murah Meriah", "Jakarta", "Toko", 0.8),
    ("Toko Sejahtera", "Bandung", "Toko", 0.6),
    ("Toko Mekar Sari", "Semarang", "Toko", 0.5),
    ("Toko Bintang Timur", "Makassar", "Toko", 0.6),
    ("Toko Lestari", "Yogyakarta", "Toko", 0.5),
    ("Toko Kencana", "Surabaya", "Toko", 0.7),
    ("Toko Amanah", "Medan", "Toko", 0.6),
    ("Toko Damai", "Denpasar", "Toko", 0.4),
    ("Toko Setia Kawan", "Jakarta", "Toko", 0.6),
    ("Toko Sentosa Abadi", "Bandung", "Toko", 0.5),
]

SEGMEN = {
    #               termin, diskon %, faktur/bulan, limit kredit
    "Distributor": (45, 12.0, 4, 900_000_000),
    "Retail Modern": (30, 6.0, 2, 300_000_000),
    "Toko": (14, 2.0, 1, 40_000_000),
}

PEMBAYAR_LAMBAT = {"CV Laju Makmur Abadi", "Toko Berkah Abadi", "Swalayan Segar Jaya", "Toko Harapan Baru"}

# Bulan Idulfitri (perkiraan) untuk efek musiman
BULAN_LEBARAN = {2025: 3, 2026: 3, 2027: 3, 2028: 2}

GAJI = [
    ("Rina Kartika", "Direktur Keuangan", 48_000_000),
    ("Hendra Wijaya", "Manajer Produksi", 27_500_000),
    ("Dewi Lestari", "Manajer Penjualan", 26_000_000),
    ("Agus Salim", "Supervisor Gudang", 11_800_000),
    ("Maya Putri", "Staf Akuntansi", 8_900_000),
    ("Joko Susilo", "Operator Produksi", 5_600_000),
]


# ---------------------------------------------------------------------------
def awal_bulan(d: dt.date) -> dt.date:
    return d.replace(day=1)


def tambah_bulan(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def akhir_bulan(d: dt.date) -> dt.date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def efek_lebaran(kategori: str, bulan: dt.date) -> float:
    bl = BULAN_LEBARAN.get(bulan.year)
    if bl is None or kategori == "Roti":
        return 1.0
    if bulan.month == bl:
        return 1.45
    if bulan.month == bl - 1:
        return 1.15
    if bulan.month == bl + 1:
        return 0.85
    return 1.0


def faktor_tren(kode: str, idx: int, n: int) -> float:
    """idx = 0..n-1 (n-1 = bulan terakhir)."""
    dari_akhir = n - 1 - idx
    if kode == "BSK-001":
        return {2: 1.18, 1: 1.38, 0: 1.62}.get(dari_akhir, 1.0)
    if kode == "BSK-004":
        return 0.96 ** max(0, 6 - dari_akhir) if dari_akhir < 6 else 1.0
    if kode == "KRP-001":
        return 1.02 ** idx
    if kode == "MNM-002":
        return 1.03 ** min(idx, 9)
    return 1.0


def faktor_musim(kode: str, bulan: dt.date) -> float:
    if kode == "MNM-001" and bulan.month in (6, 7, 8, 9):
        return 1.15
    return 1.0


def harga_jual_pada(harga_awal: float, bulan: dt.date) -> float:
    # kenaikan daftar harga 4% setiap Januari mulai 2026
    kenaikan = max(0, bulan.year - 2025)
    return round(harga_awal * (1.04 ** kenaikan) / 50) * 50


def sql_str(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, dt.date):
        return f"'{v.isoformat()}'"
    return "'" + str(v).replace("'", "''") + "'"


def insert(tabel: str, kolom: list[str], baris: list[tuple], per_batch: int = 500) -> str:
    out = []
    for i in range(0, len(baris), per_batch):
        chunk = baris[i:i + per_batch]
        values = ",\n".join("(" + ", ".join(sql_str(v) for v in r) + ")" for r in chunk)
        out.append(f"INSERT INTO {tabel} ({', '.join(kolom)}) VALUES\n{values};\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------
def generate(bulan_akhir: dt.date) -> str:
    bulan_akhir = awal_bulan(bulan_akhir)
    daftar_bulan = [tambah_bulan(bulan_akhir, -(JUMLAH_BULAN - 1 - i)) for i in range(JUMLAH_BULAN)]
    tanggal_posisi = akhir_bulan(bulan_akhir)
    n = len(daftar_bulan)

    out: list[str] = [
        "-- File ini DIHASILKAN oleh db/generate_seed.py. Jangan diedit manual.\n",
        f"-- Periode data: {daftar_bulan[0]:%Y-%m} s.d. {bulan_akhir:%Y-%m}; posisi {tanggal_posisi}\n",
        "BEGIN;\n",
    ]

    out.append(insert("erp.parameter", ["kunci", "nilai"], [
        ("nama_perusahaan", "PT Nusantara Rasa (fiktif)"),
        ("tanggal_posisi", tanggal_posisi.isoformat()),
    ]))

    kat_id = {nama: i + 1 for i, nama in enumerate(KATEGORI)}
    out.append(insert("erp.kategori", ["id", "nama"], [(i, nm) for nm, i in kat_id.items()]))

    produk_id = {p[0]: i + 1 for i, p in enumerate(PRODUK)}
    out.append(insert("erp.produk", ["id", "kode", "nama", "kategori_id", "satuan", "harga_jual"], [
        (produk_id[k], k, nm, kat_id[kat], sat, float(harga_jual_pada(h, bulan_akhir)))
        for k, nm, kat, sat, h, *_ in PRODUK
    ]))

    cust_rows = []
    for i, (nm, kota, seg, _w) in enumerate(CUSTOMER):
        termin, _d, _f, limit = SEGMEN[seg]
        cust_rows.append((i + 1, f"CUS-{i + 1:03d}", nm, kota, seg, termin, float(limit)))
    out.append(insert("erp.customer", ["id", "kode", "nama", "kota", "segmen", "termin_hari", "limit_kredit"], cust_rows))

    bahan_id = {b[0]: i + 1 for i, b in enumerate(BAHAN)}
    out.append(insert("erp.bahan_baku", ["id", "kode", "nama", "satuan"],
                      [(bahan_id[k], k, nm, sat) for k, nm, sat, _ in BAHAN]))

    out.append(insert("erp.resep", ["produk_id", "bahan_id", "qty_per_unit"], [
        (produk_id[p], bahan_id[b], q) for p, isi in RESEP.items() for b, q in isi.items()
    ]))

    # --- harga bahan per bulan --------------------------------------------
    harga_bahan: dict[tuple[str, dt.date], float] = {}
    for kode, _nm, _sat, harga in BAHAN:
        h = float(harga)
        for idx, bln in enumerate(daftar_bulan):
            dari_akhir = n - 1 - idx
            if idx > 0:
                h *= 1 + RNG.uniform(-0.012, 0.016)
            if kode == "BHN-006":            # kakao: naik 4% lalu melonjak 29%
                if dari_akhir == 1:
                    h *= 1.04
                if dari_akhir == 0:
                    h *= 1.29
            if kode == "BHN-002" and dari_akhir == 0:   # gula naik 5%
                h *= 1.05
            if kode == "BHN-009" and efek_lebaran("Biskuit", bln) > 1.3:  # telur naik saat Lebaran
                h_lebaran = h * 1.12
                harga_bahan[(kode, bln)] = h_lebaran
                continue
            if kode == "BHN-003" and 6 <= dari_akhir <= 9:   # minyak sawit sempat naik
                h *= 1.015
            harga_bahan[(kode, bln)] = h
    out.append(insert("erp.harga_bahan", ["bahan_id", "bulan", "harga"], [
        (bahan_id[k], bln, round(v, 0)) for (k, bln), v in harga_bahan.items()
    ]))

    # --- target penjualan per produk per bulan --------------------------------
    target: dict[tuple[str, dt.date], int] = {}
    for kode, _nm, kat, _sat, _h, vol, *_ in PRODUK:
        for idx, bln in enumerate(daftar_bulan):
            f = faktor_tren(kode, idx, n) * efek_lebaran(kat, bln) * faktor_musim(kode, bln)
            f *= 1 + RNG.uniform(-0.04, 0.04)
            target[(kode, bln)] = int(round(vol * SKALA_VOLUME * f))

    # --- biaya produksi per unit -------------------------------------------
    biaya_rows = []
    for kode, _nm, _kat, _sat, _h, _vol, tk, oh_tetap in PRODUK:
        for idx, bln in enumerate(daftar_bulan):
            unit = int(round(target[(kode, bln)] * RNG.uniform(0.98, 1.04)))
            tk_bln = tk * (1.06 ** max(0, bln.year - 2025))     # UMK naik tiap Januari
            if kode == "ROT-002" and n - 1 - idx <= 1:
                unit = int(round(target[(kode, daftar_bulan[-2])] * 1.01))  # volume stabil
            overhead = oh_tetap * SKALA_VOLUME / unit + 85
            biaya_rows.append((produk_id[kode], bln, unit, round(tk_bln, 2), round(overhead, 2)))
    out.append(insert("erp.biaya_produksi",
                      ["produk_id", "bulan", "unit_diproduksi", "tenaga_kerja_per_unit", "overhead_per_unit"],
                      biaya_rows))

    # --- faktur penjualan ----------------------------------------------------
    # produk yang dijual tiap customer
    semua_kode = [p[0] for p in PRODUK]
    afinitas: dict[int, dict[str, float]] = {}
    for i, (_nm, _kota, seg, _w) in enumerate(CUSTOMER):
        if seg == "Distributor":
            pilih = semua_kode
        elif seg == "Retail Modern":
            pilih = RNG.sample(semua_kode, 9)
            if "BSK-001" not in pilih:
                pilih[0] = "BSK-001"
        else:
            pilih = RNG.sample(semua_kode, RNG.randint(5, 7))
        afinitas[i] = {k: RNG.uniform(0.7, 1.3) for k in pilih}

    harga_awal = {p[0]: p[4] for p in PRODUK}
    faktur_rows, detail_rows, bayar_rows = [], [], []
    faktur_no = 0
    detail_id = 0

    for idx, bln in enumerate(daftar_bulan):
        dari_akhir = n - 1 - idx
        # alokasi qty per customer per produk
        alokasi: dict[int, dict[str, int]] = {i: {} for i in range(len(CUSTOMER))}
        for kode in semua_kode:
            bobot = {}
            for i, (_nm, _kota, seg, w) in enumerate(CUSTOMER):
                if kode not in afinitas[i]:
                    continue
                b = w * afinitas[i][kode]
                if kode == "BSK-001" and seg == "Retail Modern" and dari_akhir <= 2:
                    b *= {2: 1.5, 1: 2.0, 0: 2.6}[dari_akhir]
                bobot[i] = b
            total_b = sum(bobot.values())
            for i, b in bobot.items():
                q = int(round(target[(kode, bln)] * b / total_b))
                if q > 0:
                    alokasi[i][kode] = q

        hari_dalam_bulan = calendar.monthrange(bln.year, bln.month)[1]
        for i, (nm, _kota, seg, _w) in enumerate(CUSTOMER):
            termin, diskon, n_faktur, _limit = SEGMEN[seg]
            if seg == "Toko" and RNG.random() < 0.4:
                n_faktur = 2
            items = alokasi[i]
            if not items:
                continue
            # bagi qty tiap produk ke n_faktur faktur
            per_faktur: list[dict[str, int]] = [{} for _ in range(n_faktur)]
            for kode, q in items.items():
                porsi = [RNG.uniform(0.6, 1.4) for _ in range(n_faktur)]
                s = sum(porsi)
                sisa = q
                for j in range(n_faktur):
                    qq = q * porsi[j] / s if j < n_faktur - 1 else sisa
                    qq = max(0, int(round(qq)))
                    qq = min(qq, sisa)
                    sisa -= qq
                    if qq > 0:
                        per_faktur[j][kode] = qq
            hari = sorted(RNG.sample(range(1, hari_dalam_bulan + 1), n_faktur))
            for j in range(n_faktur):
                if not per_faktur[j]:
                    continue
                faktur_no += 1
                tgl = bln.replace(day=hari[j])
                total = 0.0
                for kode, q in per_faktur[j].items():
                    harga = float(harga_jual_pada(harga_awal[kode], bln))
                    subtotal = round(q * harga * (1 - diskon / 100), 2)
                    total += subtotal
                    detail_id += 1
                    detail_rows.append((detail_id, faktur_no, produk_id[kode], q, harga, diskon, subtotal))
                total = round(total, 2)
                jatuh_tempo = tgl + dt.timedelta(days=termin)
                faktur_rows.append((faktur_no, f"INV/{tgl:%Y/%m}/{faktur_no:05d}", tgl, i + 1, jatuh_tempo, total))

                # pembayaran
                lambat = nm in PEMBAYAR_LAMBAT and dari_akhir <= 4
                if jatuh_tempo > tanggal_posisi:
                    if RNG.random() < 0.25:
                        tgl_bayar = tgl + dt.timedelta(days=RNG.randint(3, max(4, termin - 3)))
                        if tgl_bayar <= tanggal_posisi:
                            bayar_rows.append((faktur_no, tgl_bayar, total))
                    continue
                if lambat:
                    r = RNG.random()
                    if r < 0.6:
                        continue                                   # belum dibayar
                    if r < 0.8:
                        tgl_bayar = min(jatuh_tempo + dt.timedelta(days=RNG.randint(10, 40)), tanggal_posisi)
                        bayar_rows.append((faktur_no, tgl_bayar, round(total * 0.5, 2)))  # bayar sebagian
                        continue
                tgl_bayar = jatuh_tempo + dt.timedelta(days=RNG.randint(-6, 12))
                if tgl_bayar <= tanggal_posisi:
                    bayar_rows.append((faktur_no, tgl_bayar, total))
                elif RNG.random() < 0.5:
                    bayar_rows.append((faktur_no, tanggal_posisi, total))

    out.append(insert("erp.faktur", ["id", "nomor", "tanggal", "customer_id", "jatuh_tempo", "total"], faktur_rows))
    out.append(insert("erp.faktur_detail",
                      ["id", "faktur_id", "produk_id", "qty", "harga", "diskon_persen", "subtotal"], detail_rows))
    out.append(insert("erp.pembayaran", ["faktur_id", "tanggal", "jumlah"], bayar_rows))

    # --- stok ----------------------------------------------------------------
    stok_rows = []
    menipis = {("BSK-001", "Gudang Surabaya"), ("ROT-004", "Gudang Jakarta"), ("KRP-002", "Gudang Surabaya")}
    for kode in semua_kode:
        jual = target[(kode, bulan_akhir)]
        for gudang, porsi in (("Gudang Jakarta", 0.55), ("Gudang Surabaya", 0.45)):
            minimum = int(round(jual * porsi * 0.25 / 10) * 10)
            if (kode, gudang) in menipis:
                qty = int(minimum * RNG.uniform(0.35, 0.7))
            else:
                qty = int(jual * porsi * RNG.uniform(0.4, 0.8))
            stok_rows.append((produk_id[kode], gudang, qty, minimum))
    out.append(insert("erp.stok", ["produk_id", "gudang", "qty", "stok_minimum"], stok_rows))

    out.append(insert("erp.gaji_karyawan", ["nama", "jabatan", "gaji"], [(a, b, float(c)) for a, b, c in GAJI]))

    for tabel in ("kategori", "produk", "customer", "bahan_baku", "faktur", "faktur_detail"):
        out.append(f"SELECT setval(pg_get_serial_sequence('erp.{tabel}', 'id'), (SELECT max(id) FROM erp.{tabel}));\n")
    out.append("COMMIT;\n")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bulan-akhir", help="bulan terakhir data, format YYYY-MM (default: bulan lalu)")
    ap.add_argument("--output", default=str(Path(__file__).parent / "init" / "02_seed.sql"))
    args = ap.parse_args()

    if args.bulan_akhir:
        bulan_akhir = dt.datetime.strptime(args.bulan_akhir, "%Y-%m").date()
    else:
        bulan_akhir = tambah_bulan(awal_bulan(dt.date.today()), -1)

    sql = generate(bulan_akhir)
    Path(args.output).write_text(sql, encoding="utf-8")
    print(f"Seed ditulis ke {args.output} (bulan terakhir {bulan_akhir:%Y-%m})")


if __name__ == "__main__":
    main()
