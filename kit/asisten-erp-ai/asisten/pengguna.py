"""
Pengguna contoh dan hak aksesnya.

Di aplikasi ERP sungguhan, daftar izin ini diambil dari modul hak akses ERP
(user yang sedang login), BUKAN ditulis di kode. Prinsipnya sama: asisten AI
hanya boleh melakukan apa yang boleh dilakukan user tersebut di aplikasi.
"""
from __future__ import annotations

NAMA_IZIN = {
    "produk": "data produk",
    "penjualan": "data penjualan",
    "hpp": "HPP & harga bahan baku",
    "piutang": "data piutang",
    "stok": "data stok",
    "dokumen": "dokumen SOP & kebijakan",
    "so_buat": "membuat sales order",
}

PENGGUNA = {
    "andi": {
        "nama": "Andi Pratama",
        "jabatan": "Sales Supervisor",
        "izin": ["produk", "penjualan", "stok", "dokumen", "so_buat"],
    },
    "sari": {
        "nama": "Sari Wulandari",
        "jabatan": "Staf Finance & Accounting",
        "izin": ["produk", "penjualan", "hpp", "piutang", "dokumen"],
    },
    "budi": {
        "nama": "Budi Santoso",
        "jabatan": "Direktur Operasional",
        "izin": ["produk", "penjualan", "hpp", "piutang", "stok", "dokumen", "so_buat"],
    },
}


def ambil(kode: str) -> dict:
    if kode not in PENGGUNA:
        raise KeyError(f"Pengguna '{kode}' tidak dikenal. Pilihan: {', '.join(PENGGUNA)}")
    return {"kode": kode, **PENGGUNA[kode]}


def punya_izin(kode: str, izin: str) -> bool:
    return izin in PENGGUNA.get(kode, {}).get("izin", [])
