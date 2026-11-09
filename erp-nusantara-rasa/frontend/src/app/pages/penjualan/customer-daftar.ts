import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { DaftarServer } from '../../shared/daftar';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';
import { CustomerForm, customerKosong, DataCustomer } from './customer-form';

interface BarisCustomer {
  id: number;
  kode: string;
  nama: string;
  kota: string;
  segmen: string;
  termin_hari: number;
  limit_kredit: number;
  kontak: string;
  aktif: boolean;
  omzet_12_bulan: number;
  faktur_terakhir: string | null;
  piutang: number | null;
  hari_lewat: number | null;
}

@Component({
  selector: 'app-customer-daftar',
  imports: [FormsModule, RouterLink, TableModule, SelectModule, CustomerForm, ...UI, ...PIPES],
  template: `
    <app-judul judul="Customer" [jejak]="[{ label: 'Penjualan' }, { label: 'Customer' }]">
      <ng-container meta><span>{{ d.total() | angka }} customer</span><span>Termin, diskon, dan limit kredit mengikuti segmen</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
      @if (auth.punya('customer_kelola')) { <button class="btn-utama" (click)="baru()"><app-ikon n="plus" />Customer baru</button> }
    </app-judul>

    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" />
          <input [(ngModel)]="q" (ngModelChange)="d.filter['q'] = $event; d.segarkan(300)" placeholder="Cari nama atau kode" /></div>
        <p-select [options]="opsiSegmen" [(ngModel)]="segmen" (ngModelChange)="d.filter['segmen'] = $event ?? ''; d.segarkan()" placeholder="Semua segmen" [showClear]="true" />
        <p-select [options]="auth.meta()!.kota" [(ngModel)]="kota" (ngModelChange)="d.filter['kota'] = $event ?? ''; d.segarkan()" placeholder="Semua kota" [showClear]="true" />
        <span class="spacer"></span>
        <span class="ringkas-tabel"><b>{{ d.total() | angka }}</b> hasil</span>
      </div>
      <p-table [value]="d.baris()" [lazy]="true" (onLazyLoad)="d.muat($event)" [loading]="d.memuat()" [paginator]="true" [rows]="20"
               [totalRecords]="d.total()" [rowsPerPageOptions]="[20, 50]" sortField="nama" [sortOrder]="1" dataKey="id"
               [showCurrentPageReport]="true" currentPageReportTemplate="{first}–{last} dari {totalRecords}">
        <ng-template #header>
          <tr>
            <th pSortableColumn="nama">Customer <p-sortIcon field="nama" /></th>
            <th pSortableColumn="segmen">Segmen <p-sortIcon field="segmen" /></th>
            <th pSortableColumn="kota">Kota <p-sortIcon field="kota" /></th>
            <th class="r" pSortableColumn="omzet">Omzet 12 bulan <p-sortIcon field="omzet" /></th>
            @if (auth.punya('piutang')) {
              <th class="r" pSortableColumn="piutang">Piutang <p-sortIcon field="piutang" /></th>
              <th style="width: 150px">Pemakaian limit</th>
            }
            <th>Faktur terakhir</th>
          </tr>
        </ng-template>
        <ng-template #body let-r>
          <tr class="klik" (click)="router.navigate(['/penjualan/customer', r.id])" [class.nonaktif]="!r.aktif">
            <td><div class="sel-orang"><app-avatar [nama]="r.nama" ukuran="kecil" />
              <div class="sel-utama"><a [routerLink]="'/penjualan/customer/' + r.id" (click)="$event.stopPropagation()">{{ r.nama }}</a>
                <small>{{ r.kode }}</small></div></div></td>
            <td><app-status [nilai]="r.segmen" /></td>
            <td class="redup">{{ r.kota }}</td>
            <td class="r nowrap">{{ r.omzet_12_bulan | rupiah: true }}</td>
            @if (auth.punya('piutang')) {
              <td class="r nowrap">{{ r.piutang ? (r.piutang | rupiah: true) : '–' }}
                @if ((r.hari_lewat ?? 0) > 0) { <div class="kecil" [class.t-bahaya]="r.hari_lewat > 30" [class.redup]="r.hari_lewat <= 30">lewat {{ r.hari_lewat }} hari</div> }</td>
              <td>
                <div class="meter" [class.bahaya]="pakai(r) > 100" [class.waspada]="pakai(r) > 80 && pakai(r) <= 100"><i [style.width.%]="pakai(r) > 100 ? 100 : pakai(r)"></i></div>
                <small class="samar">{{ pakai(r) | angka: 0 }}% dari {{ r.limit_kredit | rupiah: true }}</small>
              </td>
            }
            <td class="redup nowrap">{{ r.faktur_terakhir | tgl }}</td>
          </tr>
        </ng-template>
      </p-table>
    </section>
    <app-customer-form [(data)]="form" (tersimpan)="d.segarkan()" />`,
})
export class CustomerDaftar {
  private api = inject(Api);
  readonly router = inject(Router);
  readonly auth = inject(Auth);
  readonly d = new DaftarServer<BarisCustomer>(this.api, '/customer', 'nama');
  readonly form = signal<DataCustomer | null>(null);
  q = '';
  segmen: string | null = null;
  kota: string | null = null;
  readonly opsiSegmen = ['Distributor', 'Retail Modern', 'Toko'];

  pakai(r: BarisCustomer): number {
    return r.limit_kredit ? ((r.piutang ?? 0) / r.limit_kredit) * 100 : 0;
  }

  async ekspor(): Promise<void> {
    unduhCsv<BarisCustomer>('customer', [
      { label: 'Kode', nilai: (r) => r.kode }, { label: 'Nama', nilai: (r) => r.nama }, { label: 'Segmen', nilai: (r) => r.segmen },
      { label: 'Kota', nilai: (r) => r.kota }, { label: 'Termin (hari)', nilai: (r) => r.termin_hari }, { label: 'Limit kredit', nilai: (r) => r.limit_kredit },
      { label: 'Omzet 12 bulan', nilai: (r) => r.omzet_12_bulan }, { label: 'Piutang', nilai: (r) => r.piutang },
      { label: 'Faktur terakhir', nilai: (r) => r.faktur_terakhir },
    ], await this.d.semua());
  }

  baru(): void {
    this.form.set(customerKosong('Toko', this.auth.meta()!.segmen.find((s) => s.nama === 'Toko')!.limit));
  }
}
