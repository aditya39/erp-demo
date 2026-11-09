import { Component, computed, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Api } from '../../core/api';
import { PIPES } from '../../core/pipes';
import { DaftarServer } from '../../shared/daftar';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisAudit {
  id: number;
  waktu: string;
  pengguna: string;
  nama: string;
  modul: string;
  aksi: string;
  objek: string;
  keterangan: string;
}

@Component({
  selector: 'app-aktivitas',
  imports: [FormsModule, TableModule, SelectModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Log aktivitas" [jejak]="[{ label: 'Pengaturan' }, { label: 'Log aktivitas' }]">
      <ng-container meta><span>Transaksi, persetujuan, perubahan hak akses, dan setiap pertanyaan ke Asisten</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
    </app-judul>
    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" />
          <input [(ngModel)]="q" (ngModelChange)="d.filter['q'] = $event; d.segarkan(300)" placeholder="Cari aksi, objek, keterangan" /></div>
        <p-select [options]="modul()" [(ngModel)]="m" (ngModelChange)="d.filter['modul'] = $event ?? ''; d.segarkan()" placeholder="Semua modul" [showClear]="true" />
        <span class="spacer"></span><span class="ringkas-tabel"><b>{{ d.total() | angka }}</b> entri</span>
      </div>
      <p-table [value]="d.baris()" [lazy]="true" (onLazyLoad)="d.muat($event)" [loading]="d.memuat()" [paginator]="true" [rows]="30"
               [totalRecords]="d.total()" [rowsPerPageOptions]="[30, 60, 100]" dataKey="id"
               [showCurrentPageReport]="true" currentPageReportTemplate="{first}–{last} dari {totalRecords}">
        <ng-template #header><tr><th>Waktu</th><th>Pengguna</th><th>Modul</th><th>Aksi</th><th>Objek</th><th>Keterangan</th></tr></ng-template>
        <ng-template #body let-r>
          <tr [class.baris-ai]="r.modul === 'Asisten AI'">
            <td class="nowrap redup">{{ r.waktu | tgl: 'waktu' }}</td>
            <td class="nowrap"><div class="sel-orang"><app-avatar [nama]="r.nama" ukuran="kecil" /><span>{{ r.nama }}</span></div></td>
            <td>@if (r.modul === 'Asisten AI') { <span class="badge b-ai">Asisten</span> } @else { <span class="badge b-garis">{{ r.modul }}</span> }</td>
            <td>{{ r.aksi }}</td>
            <td class="objek" [title]="r.objek">{{ r.objek }}</td>
            <td class="redup">{{ r.keterangan }}</td>
          </tr>
        </ng-template>
      </p-table>
    </section>`,
})
export class LogAktivitas {
  private api = inject(Api);
  readonly d = new DaftarServer<BarisAudit>(this.api, '/audit', '');
  readonly modul = computed(() => (this.d.ekstra()['modul'] as string[]) ?? []);
  q = '';
  m: string | null = null;

  async ekspor(): Promise<void> {
    unduhCsv<BarisAudit>('log-aktivitas', [
      { label: 'Waktu', nilai: (r) => r.waktu }, { label: 'Pengguna', nilai: (r) => r.nama }, { label: 'Modul', nilai: (r) => r.modul },
      { label: 'Aksi', nilai: (r) => r.aksi }, { label: 'Objek', nilai: (r) => r.objek }, { label: 'Keterangan', nilai: (r) => r.keterangan },
    ], await this.d.semua());
  }
}
