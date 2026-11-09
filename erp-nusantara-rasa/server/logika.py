"""
Aturan bisnis ERP. Mengikuti dokumen kebijakan di kit (folder dokumen/):
  - KBJ-PJL-002 Kebijakan Harga dan Diskon
  - KBJ-KEU-004 Kebijakan Kredit dan Penagihan
  - FAQ-TI-001  (sales order melebihi limit kredit berstatus "Ditahan")

Aturan ditegakkan oleh KODE aplikasi. Asisten AI hanya menjelaskan aturan dari
dokumen; AI tidak pernah menjadi penentu boleh/tidaknya transaksi.
"""
from __future__ import annotations

import datetime as dt
import json

import psycopg

from . import db

DISKON_SEGMEN = {"Distributor": 12.0, "Retail Modern": 6.0, "Toko": 2.0}
TERMIN_SEGMEN = {"Distributor": 45, "Retail Modern": 30, "Toko": 14}
LIMIT_SEGMEN = {"Distributor": 900_000_000, "Retail Modern": 300_000_000, "Toko": 40_000_000}
GUDANG = ["Gudang Jakarta", "Gudang Surabaya"]
METODE_BAYAR = ["Transfer Bank", "Giro", "Tunai"]

BATAS_DISKON_SUPERVISOR = 1.5
BATAS_DISKON_MAKS = 3.0
BATAS_LEWAT_DISKON = 30      # hari lewat jatuh tempo: tidak boleh diskon tambahan
BATAS_CREDIT_HOLD = 60       # hari lewat jatuh tempo: credit hold, eskalasi Direktur
MARGIN_MINIMUM_DISKON = 20.0


class AturanBisnis(Exception):
    """Pelanggaran aturan bisnis; pesannya ditampilkan ke user."""


def rp(n: float) -> str:
    return "Rp " + f"{n:,.0f}".replace(",", ".")


def tahap_penagihan(hari: int) -> str:
    if hari <= 0:
        return "Lancar"
    if hari <= 7:
        return "Pengingat otomatis"
    if hari <= 30:
        return "Kunjungan / panggilan penagihan"
    if hari <= 60:
        return "Surat teguran resmi"
    if hari <= 90:
        return "Credit hold"
    return "Keputusan Direktur"


def cek_tanggal(tanggal: dt.date) -> None:
    awal, akhir = db.periode_berjalan()
    if not (awal <= tanggal <= akhir):
        raise AturanBisnis(f"Tanggal transaksi harus di periode berjalan ({awal:%d-%m-%Y} s.d. {akhir:%d-%m-%Y}).")


def kondisi_kredit(conn: psycopg.Connection, customer_id: int) -> dict:
    r = conn.execute(
        """SELECT c.limit_kredit,
                  coalesce(sum(p.sisa), 0)                    AS piutang,
                  coalesce(max(p.hari_lewat_jatuh_tempo), 0)  AS hari_lewat,
                  coalesce(sum(p.sisa) FILTER (WHERE p.hari_lewat_jatuh_tempo > 0), 0) AS lewat_jatuh_tempo
           FROM erp.customer c
           LEFT JOIN ai.v_piutang p ON p.customer_id = c.id
           WHERE c.id = %s
           GROUP BY c.limit_kredit""", (customer_id,)).fetchone()
    if r is None:
        raise AturanBisnis("Customer tidak ditemukan.")
    limit, piutang, hari = float(r["limit_kredit"]), float(r["piutang"]), int(r["hari_lewat"])
    return {
        "limit_kredit": limit,
        "piutang": piutang,
        "lewat_jatuh_tempo": float(r["lewat_jatuh_tempo"]),
        "sisa_limit": limit - piutang,
        "pemakaian_persen": round(piutang / limit * 100, 1) if limit else 0,
        "hari_lewat_maks": hari,
        "tahap": tahap_penagihan(hari),
        "credit_hold": hari > BATAS_CREDIT_HOLD,
        "boleh_diskon_tambahan": hari <= BATAS_LEWAT_DISKON,
    }


def _margin_produk(conn: psycopg.Connection, produk_ids: list[int]) -> dict[int, float]:
    rows = conn.execute(
        """SELECT h.produk_id, round((p.harga_jual - h.hpp_per_unit) / p.harga_jual * 100, 1) AS margin
           FROM ai.v_hpp_bulanan h JOIN erp.produk p ON p.id = h.produk_id
           WHERE h.bulan = (SELECT max(bulan) FROM ai.v_hpp_bulanan) AND h.produk_id = ANY(%s)""",
        (produk_ids,)).fetchall()
    return {r["produk_id"]: float(r["margin"]) for r in rows}


def cek_stok(conn: psycopg.Connection, gudang: str, item: list[dict]) -> None:
    for it in item:
        r = conn.execute("""SELECT s.qty, p.nama, p.satuan FROM erp.stok s JOIN erp.produk p ON p.id = s.produk_id
                            WHERE s.produk_id = %s AND s.gudang = %s""", (it["produk_id"], gudang)).fetchone()
        tersedia = r["qty"] if r else 0
        if it["qty"] > tersedia:
            nama = r["nama"] if r else f"produk #{it['produk_id']}"
            ribuan = lambda n: f"{n:,}".replace(",", ".")  # noqa: E731
            raise AturanBisnis(f"Stok {nama} di {gudang} tidak cukup: diminta {ribuan(it['qty'])}, "
                               f"tersedia {ribuan(tersedia)} {r['satuan'] if r else ''}.".rstrip())


def hitung_so(conn: psycopg.Connection, customer_id: int, item: list[dict], diskon_tambahan: float) -> dict:
    """Hitung harga, diskon, subtotal, total dari harga daftar & segmen customer (bukan dari input user)."""
    c = conn.execute("SELECT id, nama, segmen, termin_hari FROM erp.customer WHERE id = %s", (customer_id,)).fetchone()
    if c is None:
        raise AturanBisnis("Customer tidak ditemukan.")
    if not item:
        raise AturanBisnis("Sales order minimal berisi satu produk.")
    ids = [int(i["produk_id"]) for i in item]
    if len(set(ids)) != len(ids):
        raise AturanBisnis("Produk yang sama tidak boleh muncul dua kali. Gabungkan qty-nya.")
    produk = {r["id"]: r for r in conn.execute(
        "SELECT id, kode, nama, satuan, harga_jual FROM erp.produk WHERE aktif AND id = ANY(%s)", (ids,)).fetchall()}
    diskon_std = DISKON_SEGMEN[c["segmen"]]
    diskon = round(diskon_std + diskon_tambahan, 2)
    baris, total = [], 0.0
    for it in item:
        p = produk.get(int(it["produk_id"]))
        qty = int(it["qty"])
        if p is None:
            raise AturanBisnis("Produk tidak ditemukan atau tidak aktif.")
        if qty <= 0:
            raise AturanBisnis(f"Qty {p['nama']} harus lebih dari 0.")
        harga = float(p["harga_jual"])
        subtotal = round(qty * harga * (1 - diskon / 100), 2)
        total += subtotal
        baris.append({"produk_id": p["id"], "kode": p["kode"], "nama": p["nama"], "satuan": p["satuan"],
                      "qty": qty, "harga": harga, "diskon_persen": diskon, "subtotal": subtotal})
    return {"customer": dict(c), "diskon_standar": diskon_std, "diskon_tambahan": diskon_tambahan,
            "item": baris, "total": round(total, 2)}


def evaluasi_so(conn: psycopg.Connection, customer_id: int, hitungan: dict) -> tuple[str, list[dict], list[str]]:
    """
    Kembalikan (status, daftar persetujuan yang dibutuhkan, peringatan).
    Melempar AturanBisnis untuk pelanggaran yang tidak bisa disetujui.
    """
    d = hitungan["diskon_tambahan"]
    if d < 0:
        raise AturanBisnis("Diskon tambahan tidak boleh negatif.")
    if d > BATAS_DISKON_MAKS:
        raise AturanBisnis("Diskon tambahan maksimal 3%. Di atas itu wajib persetujuan tertulis Direktur Operasional "
                           "di luar sistem (KBJ-PJL-002).")
    kredit = kondisi_kredit(conn, customer_id)
    if d > 0 and not kredit["boleh_diskon_tambahan"]:
        raise AturanBisnis(f"Diskon tambahan tidak boleh diberikan: customer memiliki faktur lewat jatuh tempo "
                           f"{kredit['hari_lewat_maks']} hari (batas {BATAS_LEWAT_DISKON} hari, KBJ-PJL-002).")
    if d > 0:
        margin = _margin_produk(conn, [i["produk_id"] for i in hitungan["item"]])
        rendah = [i["nama"] for i in hitungan["item"] if margin.get(i["produk_id"], 100) < MARGIN_MINIMUM_DISKON]
        if rendah:
            raise AturanBisnis(f"Diskon tambahan dihentikan sementara untuk produk dengan margin kotor < 20%: "
                               f"{', '.join(rendah)} (KBJ-PJL-002).")

    perlu: list[dict] = []
    if kredit["credit_hold"]:
        perlu.append({"jenis": "credit_hold", "judul": "Credit hold",
                      "alasan": f"Ada faktur lewat jatuh tempo {kredit['hari_lewat_maks']} hari (lebih dari H+60). "
                                "Pengiriman dihentikan sementara dan keputusan ada di Direktur Operasional (KBJ-KEU-004).",
                      "izin": "so_setujui_direksi", "peran": "Direktur Operasional"})
    if kredit["piutang"] + hitungan["total"] > kredit["limit_kredit"]:
        perlu.append({"jenis": "limit_kredit", "judul": "Melebihi limit kredit",
                      "alasan": f"Piutang {rp(kredit['piutang'])} + SO ini {rp(hitungan['total'])} = "
                                f"{rp(kredit['piutang'] + hitungan['total'])}, melebihi limit {rp(kredit['limit_kredit'])}. "
                                "Perlu persetujuan Divisi Finance (FAQ-TI-001).",
                      "izin": "so_setujui_kredit", "peran": "Divisi Finance"})
    if d > BATAS_DISKON_SUPERVISOR:
        perlu.append({"jenis": "diskon", "judul": f"Diskon tambahan {d:g}%".replace(".", ","),
                      "alasan": "Diskon tambahan di atas 1,5% sampai 3% wajib disetujui Manajer Penjualan (KBJ-PJL-002).",
                      "izin": "so_setujui_diskon", "peran": "Manajer Penjualan"})
    for p in perlu:
        p.update({"status": "menunggu", "oleh": None, "waktu": None, "catatan": ""})

    peringatan = []
    if 0 < kredit["hari_lewat_maks"] <= BATAS_CREDIT_HOLD:
        peringatan.append(f"Customer memiliki faktur lewat jatuh tempo {kredit['hari_lewat_maks']} hari "
                          f"(tahap: {kredit['tahap'].lower()}).")
    if any(p["jenis"] in ("credit_hold", "limit_kredit") for p in perlu):
        status = "Ditahan"
    elif perlu:
        status = "Menunggu Persetujuan"
    else:
        status = "Faktur Terbit"
    return status, perlu, peringatan


def _nomor(prefix: str, tanggal: dt.date, nomor_urut: int) -> str:
    return f"{prefix}/{tanggal:%Y/%m}/{nomor_urut:05d}"


def buat_so(conn: psycopg.Connection, data: dict, oleh: str) -> dict:
    """
    Simpan SO. Bila lolos semua aturan, faktur langsung diterbitkan.
    `sumber` = "asisten_ai" bila draft disiapkan Asisten AI; aturannya tetap sama, yang menyimpan tetap user (`oleh`).
    """
    tanggal = data["tanggal"]
    cek_tanggal(tanggal)
    if data["gudang"] not in GUDANG:
        raise AturanBisnis("Gudang tidak dikenal.")
    sumber = data.get("sumber") or "manual"
    if sumber not in ("manual", "asisten_ai"):
        raise AturanBisnis("Sumber sales order tidak dikenal.")
    hitungan = hitung_so(conn, data["customer_id"], data["item"], float(data.get("diskon_tambahan") or 0))
    status, perlu, peringatan = evaluasi_so(conn, data["customer_id"], hitungan)
    cek_stok(conn, data["gudang"], hitungan["item"])

    so_id = conn.execute("SELECT nextval(pg_get_serial_sequence('erp.sales_order', 'id')) AS id").fetchone()["id"]
    nomor = _nomor("SO", tanggal, so_id)
    conn.execute(
        """INSERT INTO erp.sales_order (id, nomor, tanggal, customer_id, gudang, diskon_tambahan, catatan, status,
                                        persetujuan, total, dibuat_oleh, sumber)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (so_id, nomor, tanggal, data["customer_id"], data["gudang"], hitungan["diskon_tambahan"],
         data.get("catatan") or "", "Menunggu Persetujuan" if status == "Faktur Terbit" else status,
         json.dumps(perlu), hitungan["total"], oleh, sumber))
    for it in hitungan["item"]:
        conn.execute(
            """INSERT INTO erp.sales_order_detail (so_id, produk_id, qty, harga, diskon_persen, subtotal)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (so_id, it["produk_id"], it["qty"], it["harga"], it["diskon_persen"], it["subtotal"]))
    ket = f"{hitungan['customer']['nama']} · {rp(hitungan['total'])}"
    if sumber == "asisten_ai":
        u = conn.execute("SELECT nama FROM erp.pengguna WHERE kode = %s", (oleh,)).fetchone()
        ket += f" · draft Asisten AI, dikonfirmasi {u['nama'] if u else oleh}"
    db.catat_audit(conn, oleh, "Penjualan", "Membuat sales order", nomor, ket)
    faktur = None
    if status == "Faktur Terbit":
        faktur = terbitkan_faktur(conn, so_id, oleh)
    else:
        db.catat_audit(conn, "sistem", "Penjualan", f"SO {status.lower()}", nomor, "; ".join(p["judul"] for p in perlu))
    return {"id": so_id, "nomor": nomor, "status": "Faktur Terbit" if faktur else status,
            "persetujuan": perlu, "peringatan": peringatan, "faktur": faktur, "sumber": sumber}


def terbitkan_faktur(conn: psycopg.Connection, so_id: int, oleh: str) -> dict:
    so = conn.execute(
        """SELECT so.*, c.termin_hari, c.nama AS customer FROM erp.sales_order so
           JOIN erp.customer c ON c.id = so.customer_id WHERE so.id = %s FOR UPDATE OF so""", (so_id,)).fetchone()
    item = conn.execute("SELECT * FROM erp.sales_order_detail WHERE so_id = %s ORDER BY id", (so_id,)).fetchall()
    cek_stok(conn, so["gudang"], [{"produk_id": i["produk_id"], "qty": i["qty"]} for i in item])

    faktur_id = conn.execute("SELECT nextval(pg_get_serial_sequence('erp.faktur', 'id')) AS id").fetchone()["id"]
    nomor = _nomor("INV", so["tanggal"], faktur_id)
    jatuh_tempo = so["tanggal"] + dt.timedelta(days=so["termin_hari"])
    conn.execute(
        """INSERT INTO erp.faktur (id, nomor, tanggal, customer_id, jatuh_tempo, total, gudang, so_id, dibuat_oleh)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (faktur_id, nomor, so["tanggal"], so["customer_id"], jatuh_tempo, so["total"], so["gudang"], so_id, oleh))
    for i in item:
        conn.execute(
            """INSERT INTO erp.faktur_detail (faktur_id, produk_id, qty, harga, diskon_persen, subtotal)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (faktur_id, i["produk_id"], i["qty"], i["harga"], i["diskon_persen"], i["subtotal"]))
        saldo = conn.execute(
            """UPDATE erp.stok SET qty = qty - %s WHERE produk_id = %s AND gudang = %s RETURNING qty""",
            (i["qty"], i["produk_id"], so["gudang"])).fetchone()["qty"]
        conn.execute(
            """INSERT INTO erp.mutasi_stok (tanggal, produk_id, gudang, jenis, qty, saldo, referensi, keterangan, pengguna)
               VALUES (%s, %s, %s, 'Penjualan', %s, %s, %s, %s, %s)""",
            (so["tanggal"], i["produk_id"], so["gudang"], -i["qty"], saldo, nomor, so["customer"], oleh))
    conn.execute("UPDATE erp.sales_order SET status = 'Faktur Terbit', faktur_id = %s WHERE id = %s", (faktur_id, so_id))
    db.catat_audit(conn, oleh, "Penjualan", "Menerbitkan faktur", nomor, f"{so['customer']} · {rp(float(so['total']))}")
    return {"id": faktur_id, "nomor": nomor, "jatuh_tempo": jatuh_tempo.isoformat()}


def putuskan_so(conn: psycopg.Connection, so_id: int, jenis: str, setuju: bool, catatan: str, user: dict) -> dict:
    so = conn.execute("SELECT * FROM erp.sales_order WHERE id = %s FOR UPDATE", (so_id,)).fetchone()
    if so is None:
        raise AturanBisnis("Sales order tidak ditemukan.")
    if so["status"] not in ("Ditahan", "Menunggu Persetujuan"):
        raise AturanBisnis(f"Sales order berstatus {so['status']}, tidak menunggu persetujuan.")
    perlu = so["persetujuan"]
    target = next((p for p in perlu if p["jenis"] == jenis and p["status"] == "menunggu"), None)
    if target is None:
        raise AturanBisnis("Persetujuan ini tidak ditemukan atau sudah diputuskan.")
    if target["izin"] not in user["izin"]:
        raise AturanBisnis(f"Persetujuan ini hanya dapat diberikan oleh {target['peran']}.")
    if not setuju and not catatan.strip():
        raise AturanBisnis("Tuliskan alasan penolakan.")
    target.update({"status": "disetujui" if setuju else "ditolak", "oleh": user["nama"],
                   "waktu": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "catatan": catatan.strip()})
    hasil = {"status": so["status"], "faktur": None}
    if not setuju:
        conn.execute("UPDATE erp.sales_order SET status = 'Ditolak', persetujuan = %s WHERE id = %s",
                     (json.dumps(perlu), so_id))
        db.catat_audit(conn, user["kode"], "Penjualan", "Menolak sales order", so["nomor"], f"{target['judul']}: {catatan}")
        hasil["status"] = "Ditolak"
        return hasil
    conn.execute("UPDATE erp.sales_order SET persetujuan = %s WHERE id = %s", (json.dumps(perlu), so_id))
    db.catat_audit(conn, user["kode"], "Penjualan", "Menyetujui sales order", so["nomor"], target["judul"])
    if all(p["status"] == "disetujui" for p in perlu):
        hasil["faktur"] = terbitkan_faktur(conn, so_id, user["kode"])
        hasil["status"] = "Faktur Terbit"
    return hasil


def batalkan_so(conn: psycopg.Connection, so_id: int, alasan: str, user: dict) -> None:
    so = conn.execute("SELECT * FROM erp.sales_order WHERE id = %s FOR UPDATE", (so_id,)).fetchone()
    if so is None:
        raise AturanBisnis("Sales order tidak ditemukan.")
    if so["status"] not in ("Ditahan", "Menunggu Persetujuan"):
        raise AturanBisnis("Hanya sales order yang belum diterbitkan fakturnya yang dapat dibatalkan.")
    conn.execute("UPDATE erp.sales_order SET status = 'Dibatalkan', catatan = trim(catatan || ' [Dibatalkan: ' || %s || ']') "
                 "WHERE id = %s", (alasan.strip() or "-", so_id))
    db.catat_audit(conn, user["kode"], "Penjualan", "Membatalkan sales order", so["nomor"], alasan)


def catat_pembayaran(conn: psycopg.Connection, data: dict, oleh: str) -> dict:
    """Pembayaran dialokasikan ke faktur tertua lebih dulu (KBJ-KEU-004), kecuali faktur dipilih."""
    cek_tanggal(data["tanggal"])
    jumlah = round(float(data["jumlah"]), 2)
    if jumlah <= 0:
        raise AturanBisnis("Jumlah pembayaran harus lebih dari 0.")
    if data.get("metode") not in METODE_BAYAR:
        raise AturanBisnis("Metode pembayaran tidak dikenal.")
    filter_faktur = "AND faktur_id = %(f)s" if data.get("faktur_id") else ""
    terbuka = conn.execute(
        f"""SELECT faktur_id, nomor_faktur, sisa FROM ai.v_piutang
            WHERE customer_id = %(c)s {filter_faktur} ORDER BY jatuh_tempo, tanggal, faktur_id""",
        {"c": data["customer_id"], "f": data.get("faktur_id")}).fetchall()
    total_sisa = sum(float(r["sisa"]) for r in terbuka)
    if not terbuka:
        raise AturanBisnis("Tidak ada faktur terbuka untuk dibayar.")
    if jumlah > total_sisa + 0.5:
        raise AturanBisnis(f"Jumlah melebihi sisa tagihan ({rp(total_sisa)}).")
    alokasi, sisa_bayar = [], jumlah
    for r in terbuka:
        if sisa_bayar <= 0:
            break
        bayar = round(min(sisa_bayar, float(r["sisa"])), 2)
        conn.execute(
            """INSERT INTO erp.pembayaran (faktur_id, tanggal, jumlah, metode, referensi, dibuat_oleh)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (r["faktur_id"], data["tanggal"], bayar, data["metode"], data.get("referensi") or "", oleh))
        alokasi.append({"faktur_id": r["faktur_id"], "nomor": r["nomor_faktur"], "jumlah": bayar,
                        "lunas": bayar >= float(r["sisa"]) - 0.5})
        sisa_bayar = round(sisa_bayar - bayar, 2)
    nama = conn.execute("SELECT nama FROM erp.customer WHERE id = %s", (data["customer_id"],)).fetchone()["nama"]
    db.catat_audit(conn, oleh, "Keuangan", "Mencatat pembayaran", nama,
                   f"{rp(jumlah)} · {data['metode']} · {len(alokasi)} faktur")
    return {"jumlah": jumlah, "alokasi": alokasi}


def sesuaikan_stok(conn: psycopg.Connection, data: dict, oleh: str) -> dict:
    cek_tanggal(data["tanggal"])
    r = conn.execute("""SELECT s.qty, p.nama FROM erp.stok s JOIN erp.produk p ON p.id = s.produk_id
                        WHERE s.produk_id = %s AND s.gudang = %s FOR UPDATE OF s""",
                     (data["produk_id"], data["gudang"])).fetchone()
    if r is None:
        raise AturanBisnis("Stok produk di gudang ini tidak ditemukan.")
    fisik = int(data["qty_fisik"])
    if fisik < 0:
        raise AturanBisnis("Qty fisik tidak boleh negatif.")
    if not (data.get("alasan") or "").strip():
        raise AturanBisnis("Alasan penyesuaian wajib diisi.")
    selisih = fisik - int(r["qty"])
    conn.execute("UPDATE erp.stok SET qty = %s WHERE produk_id = %s AND gudang = %s",
                 (fisik, data["produk_id"], data["gudang"]))
    if data.get("stok_minimum") is not None:
        conn.execute("UPDATE erp.stok SET stok_minimum = %s WHERE produk_id = %s AND gudang = %s",
                     (int(data["stok_minimum"]), data["produk_id"], data["gudang"]))
    conn.execute(
        """INSERT INTO erp.mutasi_stok (tanggal, produk_id, gudang, jenis, qty, saldo, referensi, keterangan, pengguna)
           VALUES (%s, %s, %s, 'Penyesuaian', %s, %s, 'Stock opname', %s, %s)""",
        (data["tanggal"], data["produk_id"], data["gudang"], selisih, fisik, data["alasan"].strip(), oleh))
    db.catat_audit(conn, oleh, "Persediaan", "Penyesuaian stok", f"{r['nama']} · {data['gudang']}",
                   f"{r['qty']} → {fisik} ({selisih:+d}) · {data['alasan'].strip()}")
    return {"qty_lama": r["qty"], "qty_baru": fisik, "selisih": selisih}
