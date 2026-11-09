"""
Tempat menambahkan tool baru (Latihan 6 dan Demo 5).

Tool yang ditulis di sini otomatis terdaftar dan langsung bisa dipakai
asisten di CLI maupun di aplikasi web. Contoh pola lengkap ada di
asisten/tools.py (lihat tren_penjualan atau penjualan_teratas).

View yang tersedia untuk dibaca (schema "ai"):
  ai.v_produk, ai.v_customer, ai.v_penjualan, ai.v_hpp_bulanan,
  ai.v_hpp_komponen, ai.v_harga_bahan, ai.v_piutang, ai.v_stok, ai.v_info
"""
from __future__ import annotations

from . import db
from . import format as fmt
from .tools import tool

# Contoh kerangka (hapus tanda komentar lalu lengkapi):
#
# @tool(
#     nama="nama_tool_anda",
#     deskripsi="Jelaskan KAPAN model harus memakai tool ini.",
#     parameter={
#         "type": "object",
#         "properties": {
#             "jumlah": {"type": "integer", "description": "Jumlah baris. Default 5."},
#         },
#         "required": [],
#     },
#     izin="penjualan",   # produk | penjualan | hpp | piutang | stok | dokumen
# )
# def nama_tool_anda(jumlah: int = 5) -> dict:
#     baris = db.query("SELECT ... FROM ai.v_... LIMIT %(n)s", {"n": jumlah})
#     return {"data": baris}
