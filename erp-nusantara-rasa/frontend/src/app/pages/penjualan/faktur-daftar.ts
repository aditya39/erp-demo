import { Component, computed, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { Faktur } from '../../core/model';
import { PIPES } from '../../core/pipes';
import { DaftarServer } from '../../shared/daftar';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

@Component({
  selector: 'app-faktur-daftar',
  imports: [FormsModule, RouterLink, TableModule, SelectModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Faktur penjualan" [jejak]="[{ label: 'Penjualan' }, { label: 'Faktur penjualan' }]">
      <ng-container meta><span>Diterbitkan otomatis dari sales order yang disetujui</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
    </app-judul>

    <div class="statistik">
      <div class="stat"><span class="stat-label">Faktur</span><span class="stat-nilai">{{ ringkas()?.jumlah | angka }}</span><span class="stat-ket">sesuai filter</span></div>
      <div class="stat"><span class="stat-label">Nilai faktur</span><span class="stat-nilai">{{ ringkas()?.total | rupiah: true }}</span><span class="stat-ket">setelah diskon</span></div>
      @if (auth.punya('piutang')) {
        <div class="stat"><span class="stat-label">Sisa tagihan</span><span class="stat-nilai">{{ ringkas()?.sisa | rupiah: true }}</span><span class="stat-ket">belum dibayar</span></div>
      }
    </div>

    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" />
          <input [(ngModel)]="q" (ngModelChange)="d.filter['q'] = $event; d.segarkan(300)" placeholder="Cari nomor atau customer" /></div>
        <p-select [options]="opsiStatus" [(ngModel)]="status" (ngModelChange)="d.filter['status'] = $event; d.segarkan()" optionLabel="label"
                  optionValue="nilai" placeholder="Semua status" [showClear]="true" />
        <p-select [options]="opsiPeriode" [(ngModel)]="periode" (ngModelChange)="pilihPeriode($event)" optionLabel="label" optionValue="nilai" />
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
            <th pSortableColumn="jatuh_tempo">Jatuh tempo <p-sortIcon field="jatuh_tempo" /></th>
            <th class="r" pSortableColumn="total">Total <p-sortIcon field="total" /></th>
            <th class="r" pSortableColumn="sisa">Sisa <p-sortIcon field="sisa" /></th>
          </tr>
        </ng-template>
        <ng-template #body let-r>
          <tr class="klik" (click)="router.navigate(['/penjualan/faktur', r.id])">
            <td><a class="kode" [routerLink]="'/penjualan/faktur/' + r.id" (click)="$event.stopPropagation()">{{ r.nomor }}</a></td>
            <td class="nowrap redup">{{ r.tanggal | tgl }}</td>
            <td><div class="sel-utama"><b>{{ r.customer }}</b><small>{{ r.segmen }} · {{ r.kota }}</small></div></td>
            <td><app-status [nilai]="r.status" /></td>
            <td class="nowrap"><span class="redup">{{ r.jatuh_tempo | tgl }}</span>
              @if (r.hari_lewat > 0) { <div class="t-bahaya kecil">lewat {{ r.hari_lewat }} hari</div> }</td>
            <td class="r tebal nowrap">{{ r.total | rupiah }}</td>
            <td class="r nowrap" [class.samar]="r.sisa <= 0.5">{{ r.sisa > 0.5 ? (r.sisa | rupiah) : '–' }}</td>
          </tr>
        </ng-template>
        <ng-template #emptymessage><tr><td colspan="7"><app-kosong judul="Tidak ada faktur" ikon="faktur" /></td></tr></ng-template>
      </p-table>
    </section>`,
})
export class FakturDaftar {
  private api = inject(Api);
  readonly router = inject(Router);
  readonly auth = inject(Auth);
  readonly d = new DaftarServer<Faktur>(this.api, '/faktur');
  q = '';
  status: string | null = null;
  periode = '';
  readonly opsiStatus = ['Lunas', 'Sebagian', 'Belum Lunas', 'Jatuh Tempo'].map((s) => ({ label: s, nilai: s }));
  readonly opsiPeriode = [
    { label: 'Semua periode', nilai: '' },
    { label: 'Bulan berjalan', nilai: '1' },
    { label: '3 bulan terakhir', nilai: '3' },
    { label: '6 bulan terakhir', nilai: '6' },
  ];
  readonly ringkas = computed(() => this.d.ekstra()['ringkasan'] as { jumlah: number; total: number; sisa: number } | undefined);

  async ekspor(): Promise<void> {
    unduhCsv<Faktur>('faktur-penjualan', [
      { label: 'Nomor', nilai: (r) => r.nomor }, { label: 'Tanggal', nilai: (r) => r.tanggal }, { label: 'Customer', nilai: (r) => r.customer },
      { label: 'Segmen', nilai: (r) => r.segmen }, { label: 'Kota', nilai: (r) => r.kota }, { label: 'Jatuh tempo', nilai: (r) => r.jatuh_tempo },
      { label: 'Total', nilai: (r) => r.total }, { label: 'Terbayar', nilai: (r) => r.terbayar }, { label: 'Sisa', nilai: (r) => r.sisa },
      { label: 'Status', nilai: (r) => r.status }, { label: 'Hari lewat jatuh tempo', nilai: (r) => r.hari_lewat },
    ], await this.d.semua());
  }

  pilihPeriode(n: string): void {
    const akhir = new Date(this.auth.meta()!.periode.akhir + 'T00:00:00');
    if (!n) {
      this.d.filter['dari'] = null;
    } else {
      const awal = new Date(akhir.getFullYear(), akhir.getMonth() - (Number(n) - 1), 1);
      this.d.filter['dari'] = `${awal.getFullYear()}-${String(awal.getMonth() + 1).padStart(2, '0')}-01`;
    }
    this.d.segarkan();
  }
}
