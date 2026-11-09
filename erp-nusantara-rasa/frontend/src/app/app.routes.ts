import { Routes } from '@angular/router';
import { harusLogin } from './core/auth';
import { konfirmasiTinggalkan } from './core/guard';
import { Shell } from './layout/shell';
import { Dashboard } from './pages/dashboard';
import { Login } from './pages/login';

const izin = (...i: string[]) => ({ izin: i });
const SO = ['penjualan', 'so_buat', 'so_setujui_kredit', 'so_setujui_diskon', 'so_setujui_direksi'];

export const routes: Routes = [
  { path: 'login', component: Login, title: 'Masuk' },
  {
    path: 'cetak/faktur/:id', canActivate: [harusLogin], data: izin('penjualan'), title: 'Cetak faktur',
    loadComponent: () => import('./pages/penjualan/faktur-cetak').then((m) => m.FakturCetak),
  },
  {
    path: '', component: Shell, canActivate: [harusLogin], canActivateChild: [harusLogin],
    children: [
      { path: '', component: Dashboard, title: 'Ringkasan' },
      { path: 'penjualan/sales-order', data: izin(...SO), title: 'Sales order',
        loadComponent: () => import('./pages/penjualan/so-daftar').then((m) => m.SoDaftar) },
      { path: 'penjualan/sales-order/baru', data: izin('so_buat'), title: 'Sales order baru',
        canDeactivate: [konfirmasiTinggalkan],
        loadComponent: () => import('./pages/penjualan/so-form').then((m) => m.SoForm) },
      { path: 'penjualan/sales-order/:id', data: izin(...SO), title: 'Sales order',
        loadComponent: () => import('./pages/penjualan/so-detail').then((m) => m.SoDetail) },
      { path: 'penjualan/faktur', data: izin('penjualan'), title: 'Faktur penjualan',
        loadComponent: () => import('./pages/penjualan/faktur-daftar').then((m) => m.FakturDaftar) },
      { path: 'penjualan/faktur/:id', data: izin('penjualan'), title: 'Faktur',
        loadComponent: () => import('./pages/penjualan/faktur-detail').then((m) => m.FakturDetail) },
      { path: 'penjualan/customer', data: izin('penjualan', 'so_buat'), title: 'Customer',
        loadComponent: () => import('./pages/penjualan/customer-daftar').then((m) => m.CustomerDaftar) },
      { path: 'penjualan/customer/:id', data: izin('penjualan', 'so_buat'), title: 'Customer',
        loadComponent: () => import('./pages/penjualan/customer-detail').then((m) => m.CustomerDetail) },
      { path: 'penjualan/laporan', data: izin('penjualan'), title: 'Laporan penjualan',
        loadComponent: () => import('./pages/penjualan/laporan').then((m) => m.LaporanPenjualan) },
      { path: 'keuangan/piutang', data: izin('piutang'), title: 'Piutang usaha',
        loadComponent: () => import('./pages/keuangan/piutang').then((m) => m.Piutang) },
      { path: 'keuangan/pembayaran', data: izin('piutang', 'pembayaran_catat'), title: 'Penerimaan pembayaran',
        loadComponent: () => import('./pages/keuangan/pembayaran').then((m) => m.Pembayaran) },
      { path: 'persediaan/stok', data: izin('stok'), title: 'Stok gudang',
        loadComponent: () => import('./pages/persediaan/stok').then((m) => m.Stok) },
      { path: 'persediaan/mutasi', data: izin('stok'), title: 'Mutasi stok',
        loadComponent: () => import('./pages/persediaan/mutasi').then((m) => m.Mutasi) },
      { path: 'produksi/produk', data: izin('produk'), title: 'Produk',
        loadComponent: () => import('./pages/produksi/produk-daftar').then((m) => m.ProdukDaftar) },
      { path: 'produksi/produk/:id', data: izin('produk'), title: 'Produk',
        loadComponent: () => import('./pages/produksi/produk-detail').then((m) => m.ProdukDetail) },
      { path: 'produksi/bahan-baku', data: izin('hpp'), title: 'Bahan baku',
        loadComponent: () => import('./pages/produksi/bahan-daftar').then((m) => m.BahanDaftar) },
      { path: 'produksi/bahan-baku/:id', data: izin('hpp'), title: 'Bahan baku',
        loadComponent: () => import('./pages/produksi/bahan-detail').then((m) => m.BahanDetail) },
      { path: 'produksi/hpp', data: izin('hpp'), title: 'Analisis HPP',
        loadComponent: () => import('./pages/produksi/hpp').then((m) => m.AnalisisHpp) },
      { path: 'dokumen', data: izin('dokumen'), title: 'SOP & Kebijakan',
        loadComponent: () => import('./pages/dokumen').then((m) => m.Dokumen) },
      { path: 'dokumen/:slug', data: izin('dokumen'), title: 'Dokumen',
        loadComponent: () => import('./pages/dokumen').then((m) => m.Dokumen) },
      { path: 'pengaturan/pengguna', data: izin('pengaturan'), title: 'Pengguna & hak akses',
        loadComponent: () => import('./pages/pengaturan/pengguna').then((m) => m.PenggunaHakAkses) },
      { path: 'pengaturan/aktivitas', data: izin('pengaturan'), title: 'Log aktivitas',
        loadComponent: () => import('./pages/pengaturan/aktivitas').then((m) => m.LogAktivitas) },
      { path: 'akses-ditolak', title: 'Akses ditolak', loadComponent: () => import('./pages/lain').then((m) => m.AksesDitolak) },
      { path: '**', title: 'Tidak ditemukan', loadComponent: () => import('./pages/lain').then((m) => m.TidakDitemukan) },
    ],
  },
];
