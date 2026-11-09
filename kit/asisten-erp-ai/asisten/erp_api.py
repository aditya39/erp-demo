"""
Klien kecil untuk API aplikasi ERP (dipakai Latihan 7: draft sales order).

Pembagian peran saat asisten AI membantu membuat transaksi:
  1. AI hanya MENGISI FORMULIR: tool siapkan_draft_so menghasilkan draft (belum disimpan).
  2. SISTEM ERP menghitung harga, diskon, kredit, dan persetujuan: simulasi_so().
  3. MANUSIA memutuskan: program bertanya "Simpan sales order ini?".
  4. KODE program (bukan model) menyimpan: buat_so(), dengan sesi login user itu
     sendiri, sehingga hak akses dan aturan bisnis ERP tetap berlaku.
Karena itu modul ini sengaja TIDAK didaftarkan sebagai tool: model tidak bisa menyimpan.

Hanya memakai pustaka standar Python (urllib + cookie jar), tanpa dependensi tambahan.
"""
from __future__ import annotations

import http.cookiejar
import json
import socket
import urllib.error
import urllib.request

from . import config
from . import format as fmt


class GagalERP(Exception):
    """Pemanggilan API ERP gagal. Pesannya siap ditampilkan ke user; `detail` berisi pesan asli dari ERP."""

    def __init__(self, pesan: str, status: int | None = None, detail: str = ""):
        super().__init__(pesan)
        self.status = status      # kode HTTP (401/403/422/...), None bila ERP tidak dapat dihubungi
        self.detail = detail


AWALAN_STATUS = {
    401: "Login ERP ditolak",
    403: "Hak akses ERP tidak cukup",
    404: "Data tidak ditemukan di ERP",
    422: "Ditolak aturan ERP",
}


def _detail(e: urllib.error.HTTPError) -> str:
    """Pesan error dari respons ERP: {"pesan": "..."}, atau {"detail": ...} bawaan FastAPI (galat validasi)."""
    try:
        isi = json.loads(e.read() or b"{}")
    except ValueError:
        return e.reason or ""
    detail = (isi.get("pesan") or isi.get("detail") or "") if isinstance(isi, dict) else ""
    if isinstance(detail, list):   # galat validasi pydantic: [{"loc": [...], "msg": "..."}]
        return "; ".join(f"{'.'.join(str(x) for x in d.get('loc', [])[1:])}: {d.get('msg', '')}".lstrip(": ")
                         for d in detail if isinstance(d, dict))
    return str(detail or e.reason or "")


class SesiERP:
    """Satu sesi login ERP (cookie `erp_sesi`), seperti user yang membuka aplikasi ERP di browser."""

    def __init__(self, url: str | None = None, timeout: float = 10):
        self.url = (url or config.ERP_URL).rstrip("/")
        self.timeout = timeout
        self.cookie = http.cookiejar.CookieJar()
        self._pembuka = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie))
        self.pengguna: dict | None = None
        self._meta: dict | None = None

    def _panggil(self, metode: str, path: str, data: dict | None = None) -> dict:
        body = None if data is None else json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(self.url + path, data=body, method=metode,
                                     headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self._pembuka.open(req, timeout=self.timeout) as resp:
                isi = resp.read()
        except urllib.error.HTTPError as e:
            detail = _detail(e)
            awalan = AWALAN_STATUS.get(e.code, f"ERP mengembalikan error {e.code}")
            raise GagalERP(f"{awalan}: {detail}" if detail else awalan, e.code, detail) from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            alasan = getattr(e, "reason", e)
            if isinstance(alasan, (socket.timeout, TimeoutError)):
                pesan = f"Aplikasi ERP di {self.url} tidak menjawab dalam {self.timeout:g} detik."
            else:
                pesan = (f"Aplikasi ERP tidak dapat dihubungi di {self.url}. "
                         "Pastikan ERP berjalan, lalu cek ERP_URL di .env.")
            raise GagalERP(pesan, None, str(alasan)) from None
        return json.loads(isi) if isi else {}

    # -- sesi -----------------------------------------------------------------------------
    def login(self, kode: str, password: str | None = None) -> dict:
        """Masuk sebagai user ERP. Kembalikan profil (kode, nama, jabatan, izin)."""
        self.pengguna = self._panggil("POST", "/api/auth/login",
                                      {"kode": kode, "password": config.ERP_PASSWORD if password is None else password})
        self._meta = None
        return self.pengguna

    def meta(self) -> dict:
        """Info sistem ERP: tanggal_sistem, periode berjalan, gudang, aturan diskon."""
        if self._meta is None:
            self._meta = self._panggil("GET", "/api/meta")
        return self._meta

    def _lengkapi(self, payload: dict) -> dict:
        """Tanggal SO diisi tanggal sistem ERP bila belum ada (harus di periode berjalan)."""
        data = dict(payload)
        if not data.get("tanggal"):
            data["tanggal"] = self.meta()["tanggal_sistem"]
        return data

    # -- sales order ------------------------------------------------------------------------
    def simulasi_so(self, payload: dict) -> dict:
        """Hitung SO oleh SISTEM ERP tanpa menyimpan: kredit, hitungan, status, persetujuan, peringatan, galat."""
        return self._panggil("POST", "/api/sales-order/simulasi", self._lengkapi(payload))

    def buat_so(self, payload: dict, sumber: str = "asisten_ai") -> dict:
        """Simpan SO dengan hak akses user yang login. Status ditentukan ERP. Gagal aturan bisnis → GagalERP 422."""
        return self._panggil("POST", "/api/sales-order", {**self._lengkapi(payload), "sumber": sumber})

    def detail_so(self, so_id: int) -> dict:
        return self._panggil("GET", f"/api/sales-order/{int(so_id)}")

    def tautan_so(self, so_id: int) -> str:
        """Alamat halaman SO di aplikasi ERP (untuk dibuka di browser)."""
        return f"{self.url}/penjualan/sales-order/{int(so_id)}"


# ---------------------------------------------------------------------------
# Ringkasan hasil simulasi untuk ditampilkan ke user
# ---------------------------------------------------------------------------
def _rp(n: float) -> str:
    """Rupiah lengkap (Rp 9.900, Rp 18.798.409): di transaksi angka tidak dibulatkan ke 'juta'."""
    return ("-" if n < 0 else "") + "Rp " + fmt.angka(abs(n))


def _persen(n: float) -> str:
    return f"{float(n):g}".replace(".", ",") + "%"


def ringkas_simulasi(sim: dict, draft: dict | None = None) -> list[str]:
    """
    Ubah hasil POST /api/sales-order/simulasi menjadi baris teks yang mudah dibaca.
    Semua angka berasal dari SISTEM ERP (`sim`); dari draft AI hanya diambil kode customer & gudang.
    """
    draft = draft or {}
    h = sim.get("hitungan") or {}
    c = h.get("customer") or draft.get("customer") or {}
    baris = []
    if c:
        kode = (draft.get("customer") or {}).get("kode")
        baris.append(f"Customer : {c.get('nama', '-')}{f' ({kode})' if kode else ''} · segmen {c.get('segmen', '-')}"
                     f" · termin {c.get('termin_hari', '-')} hari")
    if draft.get("gudang"):
        baris.append(f"Gudang   : {draft['gudang']}")
    if h.get("item"):
        baris.append("Item     :")
        qty = [f"{fmt.angka(i['qty'])} {i['satuan']}" for i in h["item"]]
        lebar, lebar_qty = max(len(i["nama"]) for i in h["item"]), max(len(q) for q in qty)
        for i, q in zip(h["item"], qty):
            baris.append(f"  - {i['nama']:<{lebar}}  {q:>{lebar_qty}} × {_rp(i['harga'])}"
                         f"  diskon {_persen(i['diskon_persen'])}  subtotal {_rp(i['subtotal'])}")
        bruto = sum(i["qty"] * i["harga"] for i in h["item"])
        baris.append(f"Diskon   : segmen {_persen(h['diskon_standar'])} + tambahan {_persen(h['diskon_tambahan'])}"
                     f" = {_persen(h['diskon_standar'] + h['diskon_tambahan'])}"
                     f" (nilai bruto {_rp(bruto)})")
        baris.append(f"Total    : {_rp(h['total'])}")
    elif draft.get("item"):   # ERP menolak sebelum menghitung: tampilkan isi draft apa adanya, tanpa harga
        baris.append("Isi draft (belum dihitung sistem): " + ", ".join(
            f"{fmt.angka(i['qty'])} {i.get('satuan', '')} {i.get('nama', '')}".replace("  ", " ") for i in draft["item"]))
        if draft.get("diskon_tambahan"):
            baris.append(f"Diskon tambahan di draft: {_persen(draft['diskon_tambahan'])}")
    k = sim.get("kredit")
    if k:
        baris.append(f"Kredit   : piutang {_rp(k['piutang'])} dari limit {_rp(k['limit_kredit'])}"
                     f" ({_persen(k['pemakaian_persen'])}), lewat jatuh tempo maks {k['hari_lewat_maks']} hari"
                     f" · tahap {k['tahap'].lower()}")
    if sim.get("galat"):
        baris.append(f"Tidak dapat disimpan: {sim['galat']}")
    elif sim.get("status"):
        baris.append(f"Jika disimpan: {sim['status']}")
    for p in sim.get("persetujuan") or []:
        baris.append(f"Persetujuan dibutuhkan: {p['judul']} → {p['peran']}. {p['alasan']}")
    for p in sim.get("peringatan") or []:
        baris.append(f"Peringatan: {p}")
    return baris
