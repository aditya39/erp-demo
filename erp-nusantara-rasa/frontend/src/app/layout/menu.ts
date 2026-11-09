export interface ItemMenu {
  label: string;
  ikon: string;
  tautan: string;
  izin: string[];
  exact?: boolean;
}

export interface GrupMenu {
  judul: string;
  item: ItemMenu[];
}

/** Menu utama ERP. Item hanya tampil bila user memiliki salah satu izinnya. */
export const MENU: GrupMenu[] = [
  {
    judul: '',
    item: [{ label: 'Ringkasan', ikon: 'dashboard', tautan: '/', izin: [], exact: true }],
  },
  {
    judul: 'Penjualan',
    item: [
      { label: 'Sales order', ikon: 'so', tautan: '/penjualan/sales-order',
        izin: ['penjualan', 'so_buat', 'so_setujui_kredit', 'so_setujui_diskon', 'so_setujui_direksi'] },
      { label: 'Faktur penjualan', ikon: 'faktur', tautan: '/penjualan/faktur', izin: ['penjualan'] },
      { label: 'Customer', ikon: 'customer', tautan: '/penjualan/customer', izin: ['penjualan', 'so_buat'] },
      { label: 'Laporan penjualan', ikon: 'laporan', tautan: '/penjualan/laporan', izin: ['penjualan'] },
    ],
  },
  {
    judul: 'Keuangan',
    item: [
      { label: 'Piutang usaha', ikon: 'piutang', tautan: '/keuangan/piutang', izin: ['piutang'] },
      { label: 'Penerimaan pembayaran', ikon: 'bayar', tautan: '/keuangan/pembayaran', izin: ['piutang', 'pembayaran_catat'] },
    ],
  },
  {
    judul: 'Persediaan',
    item: [
      { label: 'Stok gudang', ikon: 'stok', tautan: '/persediaan/stok', izin: ['stok'] },
      { label: 'Mutasi stok', ikon: 'mutasi', tautan: '/persediaan/mutasi', izin: ['stok'] },
    ],
  },
  {
    judul: 'Produksi & biaya',
    item: [
      { label: 'Produk', ikon: 'produk', tautan: '/produksi/produk', izin: ['produk'] },
      { label: 'Bahan baku', ikon: 'bahan', tautan: '/produksi/bahan-baku', izin: ['hpp'] },
      { label: 'Analisis HPP', ikon: 'hpp', tautan: '/produksi/hpp', izin: ['hpp'] },
    ],
  },
  {
    judul: 'Dokumen',
    item: [{ label: 'SOP & Kebijakan', ikon: 'dokumen', tautan: '/dokumen', izin: ['dokumen'] }],
  },
  {
    judul: 'Pengaturan',
    item: [
      { label: 'Pengguna & hak akses', ikon: 'akses', tautan: '/pengaturan/pengguna', izin: ['pengaturan'] },
      { label: 'Log aktivitas', ikon: 'aktivitas', tautan: '/pengaturan/aktivitas', izin: ['pengaturan'] },
    ],
  },
];
