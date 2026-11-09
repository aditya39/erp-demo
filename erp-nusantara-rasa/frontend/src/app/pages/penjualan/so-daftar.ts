import { Component, computed, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { Persetujuan } from '../../core/model';
import { PIPES } from '../../core/pipes';
import { DaftarServer } from '../../shared/daftar';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisSO {
  id: number;
  nomor: string;
  tanggal: string;
  status: string;
  total: number;
  gudang: string;
  diskon_tambahan: number;
  persetujuan: Persetujuan[];
  dibuat_oleh_nama: string;
  faktur_id: number | null;
  nomor_faktur: string | null;
  sumber: 'manual' | 'asisten_ai';
  customer_id: number;
  customer: string;
  segmen: string;
}

@Component({
  selector: 'app-so-daftar',
  imports: [FormsModule, RouterLink, TableModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Sales order" [jejak]="[{ label: 'Penjualan' }, { label: 'Sales order' }]">
      <ng-container meta><span>{{ hitung()[''] | angka }} dokumen</span>
        @if (hitung()['menunggu']) { <span><app-ikon n="pasir" />{{ hitung()['menunggu'] }} menunggu persetujuan</span> }</ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
      @if (auth.punya('so_buat')) { <a class="btn-utama" routerLink="/penjualan/sales-order/baru"><app-ikon n="plus" />Sales order baru</a> }
    </app-judul>

    <div class="tab">
      @for (t of tab; track t.nilai) {
        <button [class.aktif]="status === t.nilai" (click)="pilihTab(t.nilai)">{{ t.label }}
          @if (hitung()[t.nilai]) { <span class="hitung">{{ hitung()[t.nilai] | angka }}</span> }</button>
      }
    </div>

    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" />
          <input [(ngModel)]="q" (ngModelChange)="d.filter['q'] = $event; d.segarkan(300)" placeholder="Cari nomor atau customer" /></div>
        <span class="spacer"></span>
        <span class="ringkas-tabel"><b>{{ d.total() | angka }}</b> hasil</span>
      </div>
      <p-table [value]="d.baris()" [lazy]="true" (onLazyLoad)="d.muat($event)" [loading]="d.memuat()" [paginator]="true" [rows]="20"
               [totalRecords]="d.total()" [rowsPerPageOptions]="[20, 50, 100]" sortField="tanggal" [sortOrder]="-1" dataKey="id"
               [showCurrentPageReport]="true" currentPageReportTemplate="{first}–{last} dari {totalRecords}">
        <ng-template #header>
          <tr>
            <th pSortableColumn="nomor">Nomor <p-sortIcon field="nomor" /></th>
            <th pSortableColumn="tanggal">Tanggal <p-sortIcon field="tanggal" /></th>
            <th pSortableColumn="customer">Customer <p-sortIcon field="customer" /></th>
            <th>Status</th>
            <th class="r" pSortableColumn="total">Total <p-sortIcon field="total" /></th>
            <th>Gudang</th>
            <th>Dibuat oleh</th>
            <th>Faktur</th>
          </tr>
        </ng-template>
        <ng-template #body let-r>
          <tr class="klik" (click)="buka(r)">
            <td class="nowrap"><a class="kode" [routerLink]="'/penjualan/sales-order/' + r.id" (click)="$event.stopPropagation()">{{ r.nomor }}</a>
              @if (r.sumber === 'asisten_ai') { <app-ikon n="asisten" [ukuran]="13" class="sumber-ai" title="Dibuat lewat Asisten AI" /> }</td>
            <td class="nowrap redup">{{ r.tanggal | tgl }}</td>
            <td><div class="sel-utama"><b>{{ r.customer }}</b><small>{{ r.segmen }}</small></div></td>
            <td><app-status [nilai]="r.status" />
              @if (menunggu(r)) { <div class="samar kecil" style="margin-top: 2px">menunggu {{ menunggu(r) }}</div> }</td>
            <td class="r tebal nowrap">{{ r.total | rupiah }}</td>
            <td class="redup nowrap">{{ r.gudang.replace('Gudang ', '') }}</td>
            <td class="redup nowrap">{{ r.dibuat_oleh_nama }}</td>
            <td>@if (r.nomor_faktur) { <a class="kode" [routerLink]="'/penjualan/faktur/' + r.faktur_id" (click)="$event.stopPropagation()">{{ r.nomor_faktur }}</a> } @else { <span class="samar">–</span> }</td>
          </tr>
        </ng-template>
        <ng-template #emptymessage><tr><td colspan="8"><app-kosong judul="Tidak ada sales order" ikon="so" /></td></tr></ng-template>
      </p-table>
    </section>`,
})
export class SoDaftar {
  private api = inject(Api);
  private router = inject(Router);
  readonly auth = inject(Auth);
  readonly d = new DaftarServer<BarisSO>(this.api, '/sales-order');
  q = '';
  status = '';
  readonly tab = [
    { label: 'Semua', nilai: '' },
    { label: 'Menunggu persetujuan', nilai: 'menunggu' },
    { label: 'Faktur terbit', nilai: 'Faktur Terbit' },
    { label: 'Ditolak', nilai: 'Ditolak' },
    { label: 'Dibatalkan', nilai: 'Dibatalkan' },
  ];

  readonly hitung = computed(() => {
    const rows = (this.d.ekstra()['hitung_status'] as { status: string; n: number }[]) ?? [];
    const m: Record<string, number> = {};
    for (const r of rows) m[r.status] = r.n;
    return { '': rows.reduce((a, r) => a + r.n, 0), menunggu: (m['Ditahan'] ?? 0) + (m['Menunggu Persetujuan'] ?? 0), ...m } as Record<string, number>;
  });

  pilihTab(s: string): void {
    this.status = s;
    this.d.filter['status'] = s;
    this.d.segarkan();
  }

  menunggu(r: BarisSO): string {
    return (r.persetujuan ?? []).filter((p) => p.status === 'menunggu').map((p) => p.peran).join(', ');
  }

  buka(r: BarisSO): void {
    this.router.navigate(['/penjualan/sales-order', r.id]);
  }

  async ekspor(): Promise<void> {
    unduhCsv<BarisSO>('sales-order', [
      { label: 'Nomor', nilai: (r) => r.nomor }, { label: 'Tanggal', nilai: (r) => r.tanggal }, { label: 'Customer', nilai: (r) => r.customer },
      { label: 'Segmen', nilai: (r) => r.segmen }, { label: 'Status', nilai: (r) => r.status }, { label: 'Total', nilai: (r) => r.total },
      { label: 'Gudang', nilai: (r) => r.gudang }, { label: 'Dibuat oleh', nilai: (r) => r.dibuat_oleh_nama }, { label: 'Faktur', nilai: (r) => r.nomor_faktur },
      { label: 'Sumber', nilai: (r) => (r.sumber === 'asisten_ai' ? 'Asisten AI' : 'Manual') },
    ], await this.d.semua());
  }
}
