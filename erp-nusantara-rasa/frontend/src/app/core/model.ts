/** Tipe data respons API ERP. */
export interface Pengguna {
  kode: string;
  nama: string;
  jabatan: string;
  divisi: string;
  email: string;
  izin: string[];
  inisial: string;
}

export interface Segmen {
  nama: string;
  diskon: number;
  termin: number;
  limit: number;
}

export interface Meta {
  perusahaan: string;
  catatan_data: string;
  tanggal_sistem: string;
  periode: { awal: string; akhir: string };
  gudang: string[];
  segmen: Segmen[];
  kategori: string[];
  kota: string[];
  metode_bayar: string[];
  aturan: { diskon_supervisor: number; diskon_maks: number };
  katalog_izin: { kode: string; label: string; kelompok: string }[];
}

export interface Halaman<T> {
  data: T[];
  total: number;
  page: number;
  size: number;
}

export interface Persetujuan {
  jenis: string;
  judul: string;
  alasan: string;
  izin: string;
  peran: string;
  status: 'menunggu' | 'disetujui' | 'ditolak';
  oleh: string | null;
  waktu: string | null;
  catatan: string;
  bisa_saya?: boolean;
}

export interface Kredit {
  limit_kredit: number;
  piutang: number;
  lewat_jatuh_tempo: number;
  sisa_limit: number;
  pemakaian_persen: number;
  hari_lewat_maks: number;
  tahap: string;
  credit_hold: boolean;
  boleh_diskon_tambahan: boolean;
}

export interface Faktur {
  id: number;
  nomor: string;
  tanggal: string;
  jatuh_tempo: string;
  total: number;
  gudang: string | null;
  so_id: number | null;
  customer_id: number;
  customer: string;
  kota: string;
  segmen: string;
  terbayar: number;
  sisa: number;
  status: string;
  hari_lewat: number;
}

export interface ItemBaris {
  id?: number;
  produk_id: number;
  kode: string;
  nama: string;
  satuan: string;
  qty: number;
  harga: number;
  diskon_persen: number;
  subtotal: number;
  stok_gudang?: number;
}

export interface Notifikasi {
  jenis: string;
  judul: string;
  isi: string;
  tautan: string;
  tingkat: 'warn' | 'info' | 'danger';
}

/** Grafik yang dikirim tool asisten AI (lihat kit: asisten/tools.py). */
export interface GrafikAI {
  tipe: 'line' | 'bar';
  judul?: string;
  label: string[];
  seri: { nama: string; data: number[] }[];
  horizontal?: boolean;
}

export interface EventAI {
  tipe: 'mulai' | 'berpikir' | 'tool' | 'grafik' | 'draft_so' | 'jawaban' | 'error' | 'selesai';
  t?: number;
  [k: string]: unknown;
}

/** Query yang dijalankan tool (untuk belajar/debug; tidak dikirim ke model). */
export interface QueryAI {
  sql: string;
  params?: unknown;
}

/** Isi form sales order = body POST /api/sales-order tanpa tanggal (tanggal = tanggal sistem). */
export interface PayloadSO {
  customer_id: number;
  gudang: string;
  diskon_tambahan: number;
  catatan: string;
  item: { produk_id: number; qty: number }[];
}

/**
 * Draft sales order dari tool asisten `siapkan_draft_so` (event "draft_so").
 * Tool hanya membaca data; harga final, diskon, dan persetujuan dihitung ERP lewat /sales-order/simulasi.
 */
export interface DraftSO {
  customer: { id: number; kode: string; nama: string; segmen: string; kota: string; termin_hari: number };
  gudang: string;
  gudang_otomatis: boolean;
  diskon_tambahan: number;
  catatan: string;
  item: { produk_id: number; kode: string; nama: string; satuan: string; qty: number; harga_daftar: number;
          harga_daftar_fmt: string; stok_gudang: number | null }[];
  nilai_bruto: number;
  nilai_bruto_fmt: string;
  payload: PayloadSO;
}

/** Hasil POST /api/sales-order/simulasi: hitungan sistem tanpa menyimpan. */
export interface SimulasiSO {
  kredit: Kredit;
  hitungan: { diskon_standar: number; diskon_tambahan: number; total: number; item: ItemBaris[] } | null;
  status: string;
  persetujuan: Persetujuan[];
  peringatan: string[];
  galat: string | null;
  stok: Record<string, number>;
}

/** Hasil POST /api/sales-order. */
export interface HasilSO {
  id: number;
  nomor: string;
  status: string;
  persetujuan: Persetujuan[];
  peringatan: string[];
  faktur: { id: number; nomor: string; jatuh_tempo: string } | null;
  sumber: 'manual' | 'asisten_ai';
}

export interface Peristiwa {
  waktu: string;
  aktor: string;
  aksi: string;
  ket: string;
  jenis: string;
  hanya_tanggal: boolean;
}

export interface Tahap {
  label: string;
  ket: string;
  keadaan: 'selesai' | 'aktif' | 'gagal' | 'nanti';
}
