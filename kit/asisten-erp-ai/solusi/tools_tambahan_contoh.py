"""
Contoh solusi Latihan 6 (dan cadangan Demo 5).

Cara pakai: salin isi file ini ke asisten/tools_tambahan.py
(atau salin hanya tool yang dibutuhkan).
"""
from __future__ import annotations

from asisten import db
from asisten import format as fmt
from asisten.tools import tool


@tool(
    nama="piutang_terbesar",
    deskripsi=("Daftar customer dengan sisa PIUTANG (tagihan yang belum dibayar) terbesar per tanggal posisi data, "
               "beserta jumlah faktur dan berapa hari paling lama lewat jatuh tempo. Gunakan untuk pertanyaan tentang "
               "piutang, tagihan, penagihan, atau customer yang telat bayar / lewat jatuh tempo."),
    parameter={
        "type": "object",
        "properties": {
            "jumlah": {"type": "integer", "description": "Jumlah customer (1-20). Default 5."},
            "min_hari_lewat_jatuh_tempo": {
                "type": "integer",
                "description": "Hanya hitung faktur yang sudah lewat jatuh tempo minimal sekian hari, mis. 60. Default 0 (semua piutang)."},
        },
        "required": [],
    },
    izin="piutang",
)
def piutang_terbesar(jumlah: int = 5, min_hari_lewat_jatuh_tempo: int = 0) -> dict:
    jumlah = max(1, min(int(jumlah or 5), 20))
    min_hari = max(0, int(min_hari_lewat_jatuh_tempo or 0))
    baris = db.query(
        """
        SELECT customer, kota, segmen,
               count(*)                    AS jumlah_faktur,
               sum(sisa)                   AS sisa_piutang,
               max(hari_lewat_jatuh_tempo) AS hari_terlama_lewat_jatuh_tempo
        FROM ai.v_piutang
        WHERE hari_lewat_jatuh_tempo >= %(min_hari)s
        GROUP BY customer, kota, segmen
        ORDER BY sisa_piutang DESC
        LIMIT %(n)s
        """,
        {"min_hari": min_hari, "n": jumlah},
    )
    for b in baris:
        b["sisa_piutang_fmt"] = fmt.rupiah(b["sisa_piutang"])
    posisi = db.info()["tanggal_posisi"]
    return {
        "posisi_per": f"{posisi:%d-%m-%Y}",
        "filter": f"faktur lewat jatuh tempo ≥ {min_hari} hari" if min_hari else "semua faktur belum lunas",
        "data": baris,
        "catatan": "Tidak ada customer yang memenuhi kriteria." if not baris else "",
        "grafik": {
            "tipe": "bar",
            "judul": "Customer dengan piutang terbesar (Rp juta)",
            "label": [b["customer"] for b in baris],
            "seri": [{"nama": "Sisa piutang (Rp juta)", "data": [round(b["sisa_piutang"] / 1e6, 1) for b in baris]}],
            "horizontal": True,
        },
    }


@tool(
    nama="stok_di_bawah_minimum",
    deskripsi="Daftar produk yang stoknya di bawah stok minimum per gudang. Gunakan untuk pertanyaan stok menipis.",
    parameter={
        "type": "object",
        "properties": {"jumlah": {"type": "integer", "description": "Jumlah baris (1-20). Default 5."}},
        "required": [],
    },
    izin="stok",
)
def stok_di_bawah_minimum(jumlah: int = 5) -> dict:
    baris = db.query(
        """
        SELECT produk, gudang, qty, stok_minimum, stok_minimum - qty AS kekurangan
        FROM ai.v_stok WHERE di_bawah_minimum ORDER BY kekurangan DESC
        LIMIT %(n)s
        """, {"n": max(1, min(int(jumlah or 5), 20))})
    return {"jumlah": len(baris), "data": baris}


@tool(
    nama="margin_produk",
    deskripsi="Margin kotor per produk bulan terakhir (harga jual dibanding HPP per unit), dari terendah.",
    parameter={
        "type": "object",
        "properties": {"jumlah": {"type": "integer", "description": "Jumlah produk. Default 5."}},
        "required": [],
    },
    izin="hpp",
)
def margin_produk(jumlah: int = 5) -> dict:
    baris = db.query(
        """
        SELECT h.produk, p.harga_jual, h.hpp_per_unit,
               round((p.harga_jual - h.hpp_per_unit) / p.harga_jual * 100, 1) AS margin_persen
        FROM ai.v_hpp_bulanan h
        JOIN ai.v_produk p ON p.id = h.produk_id
        WHERE h.bulan = (SELECT date_trunc('month', tanggal_posisi)::date FROM ai.v_info)
        ORDER BY margin_persen ASC
        LIMIT %(n)s
        """, {"n": max(1, min(int(jumlah or 5), 20))})
    for b in baris:
        b["harga_jual_fmt"] = fmt.rupiah(b["harga_jual"])
        b["hpp_per_unit_fmt"] = fmt.rupiah(b["hpp_per_unit"])
        b["margin_fmt"] = fmt.persen(b["margin_persen"], tanda=False)
    return {"data": baris}
