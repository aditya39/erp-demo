import argparse

import uvicorn

ap = argparse.ArgumentParser(description="Jalankan aplikasi web Asisten ERP")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=8000)
args = ap.parse_args()
print(f"Buka http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}")
uvicorn.run("web.app:app", host=args.host, port=args.port, log_level="warning")
