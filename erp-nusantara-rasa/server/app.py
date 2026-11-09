"""Aplikasi FastAPI: API ERP + Asisten AI + file Angular hasil build (satu port, bisa offline)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import config
from .routers import ai, dashboard, keuangan, penjualan, pengaturan, persediaan, produksi, sistem

app = FastAPI(title="ERP Nusantara Rasa (demo workshop)", docs_url="/api/docs", openapi_url="/api/openapi.json")

for r in (sistem, dashboard, penjualan, keuangan, persediaan, produksi, pengaturan, ai):
    app.include_router(r.router)


@app.exception_handler(HTTPException)
async def galat_http(_req: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"pesan": exc.detail}, status_code=exc.status_code)


FRONTEND = config.FOLDER_FRONTEND
if (FRONTEND / "index.html").exists():
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Endpoint tidak ditemukan.")
        berkas = (FRONTEND / path).resolve()
        if path and berkas.is_file() and FRONTEND.resolve() in berkas.parents:
            return FileResponse(berkas)
        return FileResponse(FRONTEND / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def belum_build() -> JSONResponse:
        return JSONResponse({"pesan": "Frontend belum di-build. Jalankan: cd frontend && npm install && npm run build"})
