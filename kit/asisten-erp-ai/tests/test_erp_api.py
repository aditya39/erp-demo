"""Uji klien API ERP (asisten/erp_api.py) dengan server ERP tiruan lokal, tanpa ERP sungguhan.

ERP mengirim error sebagai {"pesan": "..."}; galat validasi pydantic sebagai {"detail": [...]}.
"""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from asisten import erp_api

DITERIMA: list[tuple[str, dict]] = []   # (path, body) setiap POST yang diterima server tiruan


class ERPTiruan(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _kirim(self, kode: int, isi: dict, cookie: str | None = None) -> None:
        data = json.dumps(isi).encode()
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", f"erp_sesi={cookie}; HttpOnly; Path=/; SameSite=lax")
        self.end_headers()
        self.wfile.write(data)

    def _user(self) -> str | None:
        for bagian in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = bagian.strip().partition("=")
            if k == "erp_sesi" and v.startswith("token-"):
                return v[len("token-"):]
        return None

    def do_GET(self):
        if not self._user():
            return self._kirim(401, {"pesan": "Sesi berakhir. Silakan masuk kembali."})
        if self.path == "/api/meta":
            return self._kirim(200, {"tanggal_sistem": "2026-10-31", "periode": {"awal": "2026-10-01", "akhir": "2026-10-31"}})
        self._kirim(404, {"pesan": "Endpoint tidak ditemukan."})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        DITERIMA.append((self.path, body))
        if self.path == "/api/auth/login":
            if body.get("password") != "demo123":
                return self._kirim(401, {"pesan": "Nama pengguna atau password salah."})
            return self._kirim(200, {"kode": body["kode"], "nama": body["kode"].title(), "izin": ["so_buat"]},
                               cookie=f"token-{body['kode']}")
        user = self._user()
        if not user:
            return self._kirim(401, {"pesan": "Sesi berakhir. Silakan masuk kembali."})
        if user == "sari":
            return self._kirim(403, {"pesan": "Anda tidak memiliki hak akses: Membuat sales order"})
        if self.path == "/api/sales-order/simulasi":
            return self._kirim(200, {"status": "Faktur Terbit", "hitungan": None, "galat": None, "tanggal": body.get("tanggal")})
        if self.path == "/api/sales-order":
            if not body.get("item"):
                # galat validasi pydantic memakai format bawaan FastAPI
                return self._kirim(422, {"detail": [{"loc": ["body", "item"], "msg": "Field required"}]})
            if body.get("diskon_tambahan", 0) > 3:
                return self._kirim(422, {"pesan": "Diskon tambahan maksimal 3%. Di atas itu wajib persetujuan "
                                                   "tertulis Direktur Operasional di luar sistem (KBJ-PJL-002)."})
            return self._kirim(200, {"id": 1513, "nomor": "SO/2026/10/01513", "status": "Faktur Terbit",
                                     "persetujuan": [], "peringatan": []})
        self._kirim(404, {"pesan": "Endpoint tidak ditemukan."})


@pytest.fixture(scope="module")
def url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ERPTiruan)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


PAYLOAD = {"customer_id": 22, "gudang": "Gudang Jakarta", "diskon_tambahan": 0, "catatan": "",
           "item": [{"produk_id": 1, "qty": 50}, {"produk_id": 11, "qty": 20}]}


def test_login_menyimpan_cookie_sesi(url):
    sesi = erp_api.SesiERP(url)
    with pytest.raises(erp_api.GagalERP) as e:
        sesi.meta()                                    # belum login
    assert e.value.status == 401
    profil = sesi.login("andi", "demo123")
    assert profil["kode"] == "andi" and sesi.pengguna == profil
    assert any(c.name == "erp_sesi" for c in sesi.cookie)
    assert sesi.meta()["tanggal_sistem"] == "2026-10-31"   # cookie ikut terkirim


def test_login_salah_password(url):
    with pytest.raises(erp_api.GagalERP) as e:
        erp_api.SesiERP(url).login("andi", "salah")
    assert e.value.status == 401
    assert "password salah" in str(e.value) and str(e.value).startswith("Login ERP ditolak")


def test_tanggal_diisi_dari_tanggal_sistem(url):
    sesi = erp_api.SesiERP(url)
    sesi.login("andi", "demo123")
    assert sesi.simulasi_so(PAYLOAD)["tanggal"] == "2026-10-31"
    assert sesi.simulasi_so({**PAYLOAD, "tanggal": "2026-10-15"})["tanggal"] == "2026-10-15"
    assert "tanggal" not in PAYLOAD                        # payload asli tidak diubah


def test_buat_so_mengirim_sumber_dan_tanggal(url):
    sesi = erp_api.SesiERP(url)
    sesi.login("andi", "demo123")
    hasil = sesi.buat_so(PAYLOAD)
    assert hasil["nomor"] == "SO/2026/10/01513"
    path, body = DITERIMA[-1]
    assert path == "/api/sales-order" and body["sumber"] == "asisten_ai" and body["tanggal"] == "2026-10-31"
    assert sesi.tautan_so(hasil["id"]) == f"{url}/penjualan/sales-order/1513"


def test_pesan_422_dari_erp_ditampilkan(url):
    sesi = erp_api.SesiERP(url)
    sesi.login("andi", "demo123")
    with pytest.raises(erp_api.GagalERP) as e:
        sesi.buat_so({**PAYLOAD, "diskon_tambahan": 10})
    assert e.value.status == 422
    assert "Diskon tambahan maksimal 3%" in str(e.value) and "maksimal 3%" in e.value.detail
    with pytest.raises(erp_api.GagalERP) as e:
        sesi.buat_so({**PAYLOAD, "item": []})            # galat validasi berbentuk daftar
    assert e.value.status == 422 and "item: Field required" in str(e.value)


def test_403_hak_akses(url):
    sesi = erp_api.SesiERP(url)
    sesi.login("sari", "demo123")
    with pytest.raises(erp_api.GagalERP) as e:
        sesi.simulasi_so(PAYLOAD)
    assert e.value.status == 403 and "Membuat sales order" in str(e.value)


def test_erp_tidak_dapat_dihubungi():
    with socket.socket() as s:                             # port kosong: tidak ada server
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(erp_api.GagalERP) as e:
        erp_api.SesiERP(f"http://127.0.0.1:{port}", timeout=2).login("andi")
    assert e.value.status is None and "tidak dapat dihubungi" in str(e.value)


SIMULASI = {
    "kredit": {"limit_kredit": 40000000.0, "piutang": 18798409.0, "lewat_jatuh_tempo": 0.0, "sisa_limit": 21201591.0,
               "pemakaian_persen": 47.0, "hari_lewat_maks": 0, "tahap": "Lancar", "credit_hold": False,
               "boleh_diskon_tambahan": True},
    "hitungan": {"customer": {"id": 22, "nama": "Toko Sumber Rezeki", "segmen": "Toko", "termin_hari": 14},
                 "diskon_standar": 2.0, "diskon_tambahan": 2.0, "total": 575040.0,
                 "item": [{"produk_id": 1, "kode": "BSK-001", "nama": "Biskuit Kelapa 200g", "satuan": "pak", "qty": 50,
                           "harga": 9900.0, "diskon_persen": 4.0, "subtotal": 475200.0},
                          {"produk_id": 11, "kode": "MNM-001", "nama": "Teh Melati Botol 350ml", "satuan": "botol",
                           "qty": 20, "harga": 5200.0, "diskon_persen": 4.0, "subtotal": 99840.0}]},
    "status": "Menunggu Persetujuan",
    "persetujuan": [{"jenis": "diskon", "judul": "Diskon tambahan 2%", "peran": "Manajer Penjualan",
                     "alasan": "Diskon tambahan di atas 1,5% sampai 3% wajib disetujui Manajer Penjualan (KBJ-PJL-002)."}],
    "peringatan": [], "galat": None, "stok": {},
}


def test_ringkas_simulasi():
    teks = "\n".join(erp_api.ringkas_simulasi(SIMULASI, {"customer": {"kode": "CUS-022"}, "gudang": "Gudang Jakarta"}))
    assert "Toko Sumber Rezeki (CUS-022) · segmen Toko · termin 14 hari" in teks
    assert "Gudang   : Gudang Jakarta" in teks
    assert "50 pak × Rp 9.900  diskon 4%  subtotal Rp 475.200" in teks
    assert "segmen 2% + tambahan 2% = 4% (nilai bruto Rp 599.000)" in teks
    assert "Total    : Rp 575.040" in teks
    assert "piutang Rp 18.798.409 dari limit Rp 40.000.000 (47%)" in teks
    assert "Jika disimpan: Menunggu Persetujuan" in teks
    assert "Persetujuan dibutuhkan: Diskon tambahan 2% → Manajer Penjualan" in teks


def test_ringkas_simulasi_dengan_galat():
    sim = {**SIMULASI, "hitungan": None, "status": "", "persetujuan": [],
           "galat": "Diskon tambahan maksimal 3%. Di atas itu wajib persetujuan tertulis Direktur Operasional."}
    baris = erp_api.ringkas_simulasi(sim, {"customer": {"nama": "Swalayan Sentosa", "kode": "CUS-009",
                                                        "segmen": "Retail Modern", "termin_hari": 30}})
    assert baris[0].startswith("Customer : Swalayan Sentosa (CUS-009)")
    assert any(b.startswith("Tidak dapat disimpan: Diskon tambahan maksimal 3%") for b in baris)
    assert not any(b.startswith("Jika disimpan") for b in baris)
