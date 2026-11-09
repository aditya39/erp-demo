"""Hash password dan token sesi bertanda tangan (HMAC). Hanya pustaka standar Python."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from . import config

ITERASI = 200_000


def hash_password(password: str) -> str:
    garam = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), garam.encode(), ITERASI).hex()
    return f"pbkdf2_sha256${ITERASI}${garam}${h}"


def cek_password(password: str, tersimpan: str) -> bool:
    try:
        _algo, iterasi, garam, h = tersimpan.split("$")
    except ValueError:
        return False
    hitung = hashlib.pbkdf2_hmac("sha256", password.encode(), garam.encode(), int(iterasi)).hex()
    return hmac.compare_digest(hitung, h)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(teks: str) -> bytes:
    return base64.urlsafe_b64decode(teks + "=" * (-len(teks) % 4))


def buat_token(kode_pengguna: str) -> str:
    isi = _b64(json.dumps({"u": kode_pengguna, "exp": int(time.time()) + config.SESSION_JAM * 3600}).encode())
    tanda = _b64(hmac.new(config.SESSION_SECRET.encode(), isi.encode(), hashlib.sha256).digest())
    return f"{isi}.{tanda}"


def baca_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    isi, tanda = token.rsplit(".", 1)
    benar = _b64(hmac.new(config.SESSION_SECRET.encode(), isi.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(benar, tanda):
        return None
    try:
        data = json.loads(_unb64(isi))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data.get("u")
