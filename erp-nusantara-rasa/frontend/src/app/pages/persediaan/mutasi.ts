import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { DaftarServer } from '../../shared/daftar';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisMutasi {
  id: number;
  tanggal: string;
  gudang: string;
  jenis: string;
  qty: number;
  saldo: number | null;
  referensi: string;
  keterangan: string;
  pengguna: string;
  produk_id: number;
  kode: string;
  nama: string;
  satuan: string;
}

@Component({
  selector: 'app-mutasi',
  imports: [FormsModule, RouterLink, TableModule, SelectModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Mutasi stok" [jejak]="[{ label: 'Persediaan' }, { label: 'Mutasi stok' }]">
      <ng-container meta><span>Kartu stok: masuk dari produksi, keluar karena penjualan, dan penyesuaian hasil opname</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
    </app-judul>
    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" />
          <input [(ngModel)]="q" (ngModelChange)="d.filter['q'] = $event; d.segarkan(300)" placeholder="Cari produk atau referensi" /></div>
        <p-select [options]="auth.meta()!.gudang" [(ngModel)]="gudang" (ngModelChange)="d.filter['gudang'] = $event ?? ''; d.segarkan()" placeholder="Semua gudang" [showClear]="true" />
        <p-select [options]="['Penjualan', 'Produksi', 'Penyesuaian']" [(ngModel)]="jenis" (ngModelChange)="d.filter['jenis'] = $event ?? ''; d.segarkan()" placeholder="Semua jenis" [showClear]="true" />
        <span class="spacer"></span><span class="ringkas-tabel"><b>{{ d.total() | angka }}</b> mutasi</span>
      </div>
      <p-table [value]="d.baris()" [lazy]="true" (onLazyLoad)="d.muat($event)" [loading]="d.memuat()" [paginator]="true" [rows]="25"
               [totalRecords]="d.total()" [rowsPerPageOptions]="[25, 50, 100]" sortField="tanggal" [sortOrder]="-1" dataKey="id"
               [showCurrentPageReport]="true" currentPageReportTemplate="{first}–{last} dari {totalRecords}">
        <ng-template #header>
          <tr><th pSortableColumn="tanggal">Tanggal <p-sortIcon field="tanggal" /></th><th pSortableColumn="nama">Produk <p-sortIcon field="nama" /></th>
            <th>Gudang</th><th>Jenis</th><th class="r" pSortableColumn="qty">Qty <p-sortIcon field="qty" /></th><th class="r">Saldo</th><th>Referensi</th><th>Keterangan</th><th>Oleh</th></tr>
        </ng-template>
        <ng-template #body let-r>
          <tr>
            <td class="nowrap redup">{{ r.tanggal | tgl }}</td>
            <td><div class="sel-utama"><a [routerLink]="'/produksi/produk/' + r.produk_id">{{ r.nama }}</a><small>{{ r.kode }}</small></div></td>
            <td class="redup nowrap">{{ r.gudang.replace('Gudang ', '') }}</td>
            <td><app-status [nilai]="r.jenis" /></td>
            <td class="r tebal nowrap" [class.t-sukses]="r.qty > 0" [class.t-bahaya]="r.qty < 0">{{ r.qty > 0 ? '+' : '' }}{{ r.qty | angka }}</td>
            <td class="r redup">{{ r.saldo === null ? '–' : (r.saldo | angka) }}</td>
            <td class="kode nowrap">{{ r.referensi }}</td>
            <td class="redup">{{ r.keterangan }}</td>
            <td class="redup nowrap">{{ r.pengguna }}</td>
          </tr>
        </ng-template>
      </p-table>
    </section>`,
})
export class Mutasi {
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly d = new DaftarServer<BarisMutasi>(this.api, '/mutasi-stok');
  q = '';
  gudang: string | null = null;
  jenis: string | null = null;

  async ekspor(): Promise<void> {
    unduhCsv<BarisMutasi>('mutasi-stok', [
      { label: 'Tanggal', nilai: (r) => r.tanggal }, { label: 'Kode', nilai: (r) => r.kode }, { label: 'Produk', nilai: (r) => r.nama },
      { label: 'Gudang', nilai: (r) => r.gudang }, { label: 'Jenis', nilai: (r) => r.jenis }, { label: 'Qty', nilai: (r) => r.qty },
      { label: 'Saldo', nilai: (r) => r.saldo }, { label: 'Referensi', nilai: (r) => r.referensi }, { label: 'Keterangan', nilai: (r) => r.keterangan },
      { label: 'Oleh', nilai: (r) => r.pengguna },
    ], await this.d.semua());
  }
}
