import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisProduk {
  id: number;
  kode: string;
  nama: string;
  kategori: string;
  satuan: string;
  harga_jual: number;
  hpp: number | null;
  margin: number | null;
  qty_bulan_ini: number | null;
  nilai_bulan_ini: number | null;
  ubah_qty: number | null;
  stok: number | null;
  gudang_menipis: number | null;
}

@Component({
  selector: 'app-produk-daftar',
  imports: [FormsModule, RouterLink, ...UI, ...PIPES],
  template: `
    <app-judul judul="Produk" [jejak]="[{ label: 'Produksi & biaya' }, { label: 'Produk' }]">
      <ng-container meta><span>{{ data().length }} produk aktif</span><span>Harga daftar, HPP, dan penjualan {{ bulan() | bulan }}</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
    </app-judul>
    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" /><input [(ngModel)]="q" (ngModelChange)="tunda()" placeholder="Cari nama atau kode" /></div>
        <div class="segmen">
          <button [class.aktif]="!kategori" (click)="kategori = ''; muat()">Semua</button>
          @for (k of auth.meta()!.kategori; track k) { <button [class.aktif]="kategori === k" (click)="kategori = k; muat()">{{ k }}</button> }
        </div>
      </div>
      <table class="tabel">
        <thead><tr><th>Produk</th><th>Kategori</th><th class="r">Harga jual</th>
          @if (kolom().hpp) { <th class="r">HPP / unit</th><th class="r">Margin</th> }
          @if (kolom().penjualan) { <th class="r">Qty bulan ini</th><th class="r">vs bulan lalu</th><th class="r">Nilai</th> }
          @if (kolom().stok) { <th class="r">Stok</th> }</tr></thead>
        <tbody>
          @for (p of data(); track p.id) {
            <tr class="klik" (click)="router.navigate(['/produksi/produk', p.id])">
              <td><div class="sel-utama"><a [routerLink]="'/produksi/produk/' + p.id" (click)="$event.stopPropagation()">{{ p.nama }}</a><small>{{ p.kode }} · per {{ p.satuan }}</small></div></td>
              <td class="redup">{{ p.kategori }}</td>
              <td class="r">{{ p.harga_jual | rupiah }}</td>
              @if (kolom().hpp) {
                <td class="r redup">{{ p.hpp | rupiah }}</td>
                <td class="r"><span class="margin" [class.rendah]="(p.margin ?? 100) < 30">{{ p.margin | angka: 1 }}%</span></td>
              }
              @if (kolom().penjualan) {
                <td class="r">{{ p.qty_bulan_ini | angka }}</td>
                <td class="r"><app-delta [nilai]="p.ubah_qty" /></td>
                <td class="r tebal">{{ p.nilai_bulan_ini | rupiah: true }}</td>
              }
              @if (kolom().stok) {
                <td class="r">{{ p.stok | angka }} @if (p.gudang_menipis) { <app-ikon n="awas" [ukuran]="13" class="t-peringatan" title="Ada gudang di bawah minimum" /> }</td>
              }
            </tr>
          }
        </tbody>
      </table>
    </section>`,
})
export class ProdukDaftar implements OnInit {
  private api = inject(Api);
  readonly router = inject(Router);
  readonly auth = inject(Auth);
  readonly data = signal<BarisProduk[]>([]);
  readonly kolom = signal({ hpp: false, penjualan: false, stok: false });
  readonly bulan = signal('');
  q = '';
  kategori = '';
  private t?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.muat();
  }

  ekspor(): void {
    unduhCsv<BarisProduk>('produk', [
      { label: 'Kode', nilai: (r) => r.kode }, { label: 'Produk', nilai: (r) => r.nama }, { label: 'Kategori', nilai: (r) => r.kategori },
      { label: 'Harga jual', nilai: (r) => r.harga_jual }, { label: 'HPP', nilai: (r) => r.hpp }, { label: 'Margin %', nilai: (r) => r.margin },
      { label: 'Qty bulan ini', nilai: (r) => r.qty_bulan_ini }, { label: 'Nilai bulan ini', nilai: (r) => r.nilai_bulan_ini }, { label: 'Stok', nilai: (r) => r.stok },
    ], this.data());
  }

  tunda(): void {
    clearTimeout(this.t);
    this.t = setTimeout(() => this.muat(), 300);
  }

  async muat(): Promise<void> {
    const d = await this.api.get<{ data: BarisProduk[]; bulan: string; kolom: { hpp: boolean; penjualan: boolean; stok: boolean } }>(
      '/produk', { q: this.q, kategori: this.kategori });
    this.data.set(d.data);
    this.kolom.set(d.kolom);
    this.bulan.set(d.bulan);
  }
}
