"""
Menjalankan ERP Nusantara Rasa.

  python -m server                  # http://localhost:8080
  python -m server --host 0.0.0.0   # bisa dibuka dari laptop lain di jaringan yang sama

ERP_AUTO_INGEST=1 (dipakai di Docker): indeks dokumen RAG diisi otomatis di latar belakang
bila belum ada, menunggu sampai model embedding di Ollama siap.
"""
import argparse
import os
import threading
import time

import psycopg
import uvicorn

from . import config, migrasi


def _ingest_otomatis() -> None:
    from asisten import config as ai_config, rag  # noqa: E402  (path dari config.ASISTEN_PATH)

    for _ in range(180):                      # coba sampai ±1 jam (model mungkin masih diunduh)
        try:
            with psycopg.connect(ai_config.DATABASE_URL_ADMIN, connect_timeout=5) as conn:
                ada = conn.execute("SELECT to_regclass('rag.dokumen_chunk') IS NOT NULL").fetchone()[0]
                if ada and conn.execute("SELECT count(*) FROM rag.dokumen_chunk").fetchone()[0] > 0:
                    print("Indeks dokumen RAG sudah ada.")
                    return
            n = rag.ingest()
            print(f"Indeks dokumen RAG diisi: {n} potongan.")
            return
        except Exception as e:  # noqa: BLE001  model embedding belum siap / Ollama belum jalan
            print(f"Menunggu model embedding untuk RAG… ({str(e).splitlines()[0][:90]})")
            time.sleep(20)


ap = argparse.ArgumentParser()
ap.add_argument("--host", default=config.HOST)
ap.add_argument("--port", type=int, default=config.PORT)
ap.add_argument("--reload", action="store_true", help="muat ulang otomatis saat kode berubah (pengembangan)")
args = ap.parse_args()

for percobaan in range(30):                   # database mungkin belum siap (mis. baru dibuat di Docker)
    try:
        migrasi.jalankan()
        break
    except psycopg.OperationalError as e:
        print(f"Menunggu database… ({str(e).splitlines()[0][:90]})")
        time.sleep(2)
else:
    raise SystemExit("Database tidak dapat dihubungi.")

if os.getenv("ERP_AUTO_INGEST") == "1":
    threading.Thread(target=_ingest_otomatis, daemon=True).start()

print(f"ERP Nusantara Rasa: http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}", flush=True)
uvicorn.run("server.app:app", host=args.host, port=args.port, reload=args.reload, log_level="warning")
