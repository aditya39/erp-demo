"""
Katalog hak akses ERP dan pengguna contoh.

Enam izin baca pertama (produk ... dokumen) juga dipakai asisten AI: tool AI hanya
boleh dijalankan bila user yang login memiliki izin yang sama di ERP. Mengubah hak
akses di menu Pengaturan langsung berlaku juga untuk asisten AI.
"""
from __future__ import annotations

KATALOG = [
    # kode, label, kelompok
    ("produk", "Data produk", "Akses data"),
    ("penjualan", "Data penjualan", "Akses data"),
    ("hpp", "HPP & harga bahan baku", "Akses data"),
    ("piutang", "Data piutang", "Akses data"),
    ("stok", "Data stok", "Akses data"),
    ("dokumen", "Dokumen SOP & kebijakan", "Akses data"),
    ("ai", "Memakai Asisten AI", "Asisten AI"),
    ("so_buat", "Membuat sales order", "Transaksi"),
    ("so_setujui_diskon", "Menyetujui diskon tambahan > 1,5%", "Persetujuan"),
    ("so_setujui_kredit", "Menyetujui SO melebihi limit kredit", "Persetujuan"),
    ("so_setujui_direksi", "Memutuskan SO credit hold (> H+60)", "Persetujuan"),
    ("customer_kelola", "Menambah & mengubah customer", "Master data"),
    ("limit_kredit", "Mengubah limit kredit customer", "Master data"),
    ("produk_kelola", "Mengubah harga jual produk", "Master data"),
    ("pembayaran_catat", "Mencatat penerimaan pembayaran", "Transaksi"),
    ("stok_sesuaikan", "Penyesuaian stok (stock opname)", "Transaksi"),
    ("pengaturan", "Pengguna & hak akses", "Administrasi"),
]
KODE_IZIN = [k for k, _, _ in KATALOG]
LABEL_IZIN = {k: label for k, label, _ in KATALOG}

PASSWORD_DEMO = "demo123"

# kode, nama, jabatan, divisi, izin
PENGGUNA_AWAL = [
    ("budi", "Budi Santoso", "Direktur Operasional", "Direksi", KODE_IZIN),
    ("dewi", "Dewi Lestari", "Manajer Penjualan", "Penjualan",
     ["produk", "penjualan", "piutang", "stok", "dokumen", "ai", "so_buat", "so_setujui_diskon", "customer_kelola"]),
    ("andi", "Andi Pratama", "Sales Supervisor", "Penjualan",
     ["produk", "penjualan", "stok", "dokumen", "ai", "so_buat", "customer_kelola"]),
    ("sari", "Sari Wulandari", "Staf Finance & Accounting", "Finance",
     ["produk", "penjualan", "hpp", "piutang", "dokumen", "ai", "so_setujui_kredit", "limit_kredit", "pembayaran_catat"]),
    ("agus", "Agus Salim", "Supervisor Gudang", "Gudang",
     ["produk", "stok", "dokumen", "ai", "stok_sesuaikan"]),
    ("rudi", "Rudi Hartono", "Administrator Sistem", "Teknologi Informasi",
     ["dokumen", "ai", "pengaturan"]),
]
