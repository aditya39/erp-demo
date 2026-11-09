"""
Server MCP: tools asisten ERP yang sama, dipakai oleh agent lain (mis. Claude Code).

  python -m asisten.mcp_server                       # user login: budi
  ASISTEN_PENGGUNA=andi python -m asisten.mcp_server

Agent lain menjadi "otak" (memilih tool dan menyusun jawaban), sedangkan tools,
hak akses, dan koneksi read-only tetap sama dengan agent lokal karena setiap
panggilan lewat agent.eksekusi_tool. Field "grafik" tidak dikirim ke model.
Hasil siapkan_draft_so (draft_so) dikirim utuh agar model bisa merangkumnya;
server ini tidak punya tool untuk menyimpan transaksi.

Dipakai oleh asisten/claude_code.py (mode cloud lewat Claude Code), dan bisa
juga dihubungkan ke Claude Code interaktif (lihat README › Model cloud).
"""
from __future__ import annotations

import json
import os

import anyio
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import agent, pengguna, tools

KODE_PENGGUNA = os.getenv("ASISTEN_PENGGUNA", "budi")


async def daftar_tool(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=[
        types.Tool(name=t.nama, description=t.deskripsi, input_schema=t.parameter)
        for t in tools.REGISTRY.values()
    ])


async def panggil_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    # Query database bersifat blocking; jalankan di thread agar server tetap responsif.
    hasil, status = await anyio.to_thread.run_sync(
        agent.eksekusi_tool, params.name, params.arguments or {}, KODE_PENGGUNA)
    hasil.pop("grafik", None)
    return types.CallToolResult(
        content=[types.TextContent(text=json.dumps(hasil, ensure_ascii=False, default=str))],
        is_error=status != "ok",
    )


def buat_server() -> Server:
    # ASISTEN_INSTRUKSI=0: aturan asisten sudah dikirim sebagai system prompt (claude_code.py).
    instruksi = agent.system_prompt(KODE_PENGGUNA) if os.getenv("ASISTEN_INSTRUKSI", "1") == "1" else None
    return Server("erp", version="1.0", instructions=instruksi,
                  on_list_tools=daftar_tool, on_call_tool=panggil_tool)


async def main() -> None:
    pengguna.ambil(KODE_PENGGUNA)  # gagal cepat jika kode pengguna salah
    server = buat_server()
    async with stdio_server() as (baca, tulis):
        await server.run(baca, tulis, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
