"""Login, info sistem, pencarian global, dan notifikasi."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from .. import config, db, keamanan, logika
from ..izin import KATALOG, PASSWORD_DEMO
from ..sesi import COOKIE, pengguna_login, punya

router = APIRouter(prefix="/api")


def _profil(u: dict) -> dict:
    inisial = "".join(k[0] for k in u["nama"].split()[:2]).upper()
    return {"kode": u["kode"], "nama": u["nama"], "jabatan": u["jabatan"], "divisi": u["divisi"],
            "email": u["email"], "izin": u["izin"], "inisial": inisial}


class Login(BaseModel):
    kode: str
    password: str


@router.post("/auth/login")
def login(data: Login, response: Response) -> dict:
    u = db.satu("SELECT * FROM erp.pengguna WHERE kode = %s", (data.kode.strip().lower(),))
    if not u or not u["aktif"] or not keamanan.cek_password(data.password, u["password_hash"]):
        raise HTTPException(401, "Nama pengguna atau password salah.")
    with db.koneksi() as conn:
        conn.execute("UPDATE erp.pengguna SET login_terakhir = now() WHERE kode = %s", (u["kode"],))
        db.catat_audit(conn, u["kode"], "Sistem", "Masuk aplikasi")
    response.set_cookie(COOKIE, keamanan.buat_token(u["kode"]), httponly=True, samesite="lax",
                        max_age=config.SESSION_JAM * 3600)
    return _profil(u)


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/auth/me")
def me(u: dict = Depends(pengguna_login)) -> dict:
    return _profil(u)


@router.get("/auth/akun-demo")
def akun_demo() -> dict:
    """Daftar akun untuk kartu 'masuk cepat' di halaman login. Hanya untuk aplikasi demo."""
    rows = db.query("SELECT kode, nama, jabatan, divisi FROM erp.pengguna WHERE aktif ORDER BY array_length(izin, 1) DESC")
    return {"password": PASSWORD_DEMO, "akun": rows}


@router.get("/meta")
def meta(u: dict = Depends(pengguna_login)) -> dict:
    awal, akhir = db.periode_berjalan()
    nama = db.satu("SELECT nilai FROM erp.parameter WHERE kunci = 'nama_perusahaan'")["nilai"]
    return {
        "perusahaan": nama.replace(" (fiktif)", ""),
        "catatan_data": "Perusahaan & data fiktif untuk workshop",
        "tanggal_sistem": akhir.isoformat(),
        "periode": {"awal": awal.isoformat(), "akhir": akhir.isoformat()},
        "gudang": logika.GUDANG,
        "segmen": [{"nama": s, "diskon": logika.DISKON_SEGMEN[s], "termin": logika.TERMIN_SEGMEN[s],
                    "limit": logika.LIMIT_SEGMEN[s]} for s in logika.DISKON_SEGMEN],
        "kategori": [r["nama"] for r in db.query("SELECT nama FROM erp.kategori ORDER BY id")],
        "kota": [r["kota"] for r in db.query("SELECT DISTINCT kota FROM erp.customer ORDER BY kota")],
        "metode_bayar": logika.METODE_BAYAR,
        "aturan": {"diskon_supervisor": logika.BATAS_DISKON_SUPERVISOR, "diskon_maks": logika.BATAS_DISKON_MAKS},
        "katalog_izin": [{"kode": k, "label": label, "kelompok": g} for k, label, g in KATALOG],
    }


@router.get("/cari")
def cari(q: str, u: dict = Depends(pengguna_login)) -> dict:
    q = q.strip()
    if len(q) < 2:
        return {"hasil": []}
    pola = f"%{q}%"
    hasil = []
    if punya(u, "produk"):
        hasil += [{"jenis": "Produk", "judul": r["nama"], "sub": f"{r['kode']} · {r['kategori']}",
                   "tautan": f"/produksi/produk/{r['id']}"}
                  for r in db.query("""SELECT p.id, p.kode, p.nama, k.nama AS kategori FROM erp.produk p
                                       JOIN erp.kategori k ON k.id = p.kategori_id
                                       WHERE p.nama ILIKE %s OR p.kode ILIKE %s ORDER BY p.nama LIMIT 5""", (pola, pola))]
    if punya(u, "penjualan"):
        hasil += [{"jenis": "Customer", "judul": r["nama"], "sub": f"{r['kode']} · {r['segmen']} · {r['kota']}",
                   "tautan": f"/penjualan/customer/{r['id']}"}
                  for r in db.query("""SELECT id, kode, nama, segmen, kota FROM erp.customer
                                       WHERE nama ILIKE %s OR kode ILIKE %s ORDER BY nama LIMIT 5""", (pola, pola))]
        hasil += [{"jenis": "Faktur", "judul": r["nomor"], "sub": f"{r['customer']} · {r['tanggal']}",
                   "tautan": f"/penjualan/faktur/{r['id']}"}
                  for r in db.query("""SELECT f.id, f.nomor, f.tanggal, c.nama AS customer FROM erp.faktur f
                                       JOIN erp.customer c ON c.id = f.customer_id
                                       WHERE f.nomor ILIKE %s ORDER BY f.id DESC LIMIT 5""", (pola,))]
        hasil += [{"jenis": "Sales Order", "judul": r["nomor"], "sub": f"{r['customer']} · {r['status']}",
                   "tautan": f"/penjualan/sales-order/{r['id']}"}
                  for r in db.query("""SELECT so.id, so.nomor, so.status, c.nama AS customer FROM erp.sales_order so
                                       JOIN erp.customer c ON c.id = so.customer_id
                                       WHERE so.nomor ILIKE %s ORDER BY so.id DESC LIMIT 5""", (pola,))]
    if punya(u, "hpp"):
        hasil += [{"jenis": "Bahan baku", "judul": r["nama"], "sub": r["kode"], "tautan": f"/produksi/bahan-baku/{r['id']}"}
                  for r in db.query("""SELECT id, kode, nama FROM erp.bahan_baku
                                       WHERE nama ILIKE %s OR kode ILIKE %s ORDER BY nama LIMIT 5""", (pola, pola))]
    return {"hasil": hasil}


@router.get("/notifikasi")
def notifikasi(u: dict = Depends(pengguna_login)) -> dict:
    item = []
    so = db.query("""SELECT so.id, so.nomor, so.status, so.persetujuan, so.total, c.nama AS customer
                     FROM erp.sales_order so JOIN erp.customer c ON c.id = so.customer_id
                     WHERE so.status IN ('Ditahan', 'Menunggu Persetujuan') ORDER BY so.id DESC""")
    for r in so:
        for p in r["persetujuan"]:
            if p["status"] == "menunggu" and p["izin"] in u["izin"]:
                item.append({"jenis": "persetujuan", "judul": f"{r['nomor']} perlu persetujuan Anda",
                             "isi": f"{r['customer']} · {p['judul']}", "tautan": f"/penjualan/sales-order/{r['id']}",
                             "tingkat": "warn"})
            elif p["status"] == "menunggu" and punya(u, "so_buat"):
                item.append({"jenis": "info", "judul": f"{r['nomor']} {r['status'].lower()}",
                             "isi": f"{r['customer']} · menunggu {p['peran']}", "tautan": f"/penjualan/sales-order/{r['id']}",
                             "tingkat": "info"})
    if punya(u, "stok"):
        n = db.satu("SELECT count(*) AS n FROM erp.stok WHERE qty < stok_minimum")["n"]
        if n:
            item.append({"jenis": "stok", "judul": f"{n} stok di bawah minimum", "isi": "Perlu produksi / transfer gudang",
                         "tautan": "/persediaan/stok?status=menipis", "tingkat": "danger"})
    if punya(u, "hpp"):
        naik = db.query("""WITH h AS (SELECT produk, bulan, hpp_per_unit,
                                      lag(hpp_per_unit) OVER (PARTITION BY produk_id ORDER BY bulan) AS lalu
                                      FROM ai.v_hpp_bulanan)
                           SELECT produk, round((hpp_per_unit - lalu) / lalu * 100, 1) AS naik FROM h
                           WHERE bulan = (SELECT max(bulan) FROM ai.v_hpp_bulanan) AND hpp_per_unit > lalu * 1.08""")
        for r in naik:
            item.append({"jenis": "hpp", "judul": f"HPP {r['produk']} naik {str(r['naik']).replace('.', ',')}%",
                         "isi": "Di atas ambang 8% · wajib kajian harga (KBJ-PJL-002)", "tautan": "/produksi/hpp",
                         "tingkat": "warn"})
    so_saya = sum(1 for i in item if i["jenis"] == "persetujuan")
    return {"item": item, "jumlah": len(item), "hitung": {"so_saya": so_saya, "so_menunggu": len(so)}}
