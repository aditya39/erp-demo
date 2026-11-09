import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { SelectModule } from 'primeng/select';
import { Asisten } from '../../ai/asisten';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisPiutang {
  id: number;
  customer: string;
  segmen: string;
  kota: string;
  total: number;
  b0: number;
  b1: number;
  b2: number;
  b3: number;
  b4: number;
  faktur: number;
  hari_maks: number;
  limit_kredit: number;
  tahap: string;
}

@Component({
  selector: 'app-piutang',
  imports: [FormsModule, RouterLink, SelectModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Piutang usaha" [jejak]="[{ label: 'Keuangan' }, { label: 'Piutang usaha' }]">
      <ng-container meta><span>Umur piutang per {{ tanggal() | tgl }}</span><span>Pengelompokan sesuai KBJ-KEU-004</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
      @if (auth.punya('pembayaran_catat')) { <a class="btn-utama" routerLink="/keuangan/pembayaran" [queryParams]="{ catat: 1 }"><app-ikon n="plus" />Catat pembayaran</a> }
    </app-judul>

    <div class="statistik">
      <div class="stat"><span class="stat-label">Total piutang</span><span class="stat-nilai">{{ r()?.['total'] | rupiah: true }}</span>
        <span class="stat-ket">{{ r()?.['customer'] }} customer</span></div>
      @for (b of bucket; track b.k) {
        <div class="stat klik" [class.pilih]="fokus() === b.k" (click)="fokus.set(fokus() === b.k ? '' : b.k)">
          <span class="stat-label"><span class="dot" [style.background]="b.warna"></span>{{ b.label }}</span>
          <span class="stat-nilai">{{ r()?.[b.k] | rupiah: true }}</span>
          <span class="stat-ket">{{ persen(b.k) | angka: 1 }}% · {{ fokus() === b.k ? 'filter aktif' : 'klik untuk filter' }}</span>
        </div>
      }
    </div>

    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" /><input [(ngModel)]="q" (ngModelChange)="tunda()" placeholder="Cari customer" /></div>
        <p-select [options]="['Distributor', 'Retail Modern', 'Toko']" [(ngModel)]="segmen" (ngModelChange)="muat()" placeholder="Semua segmen" [showClear]="true" />
        <label class="cek"><input type="checkbox" [(ngModel)]="hanyaLewat" (ngModelChange)="muat()" />Hanya yang lewat jatuh tempo</label>
        <span class="spacer"></span>
        @if (auth.punya('ai') && auth.punya('dokumen')) {
          <button class="tanya-asisten" (click)="ai.tanya('Apa tahapan penagihan untuk faktur yang lewat jatuh tempo lebih dari 60 hari?')"><app-ikon n="asisten" />Tanya Asisten: tahapan penagihan</button>
        }
      </div>
      <div class="gulir-x">
        <table class="tabel">
          <thead><tr><th>Customer</th><th class="r">Belum jatuh tempo</th><th class="r">1–30</th><th class="r">31–60</th><th class="r">61–90</th><th class="r">&gt; 90</th><th class="r">Total</th><th>Tahap penagihan</th></tr></thead>
          <tbody>
            @for (c of tampil(); track c.id) {
              <tr>
                <td><div class="sel-utama"><a [routerLink]="'/penjualan/customer/' + c.id">{{ c.customer }}</a><small>{{ c.segmen }} · {{ c.kota }} · {{ c.faktur }} faktur</small></div></td>
                <td class="r" [class.samar]="!c.b0">{{ c.b0 ? (c.b0 | rupiah: true) : '–' }}</td>
                <td class="r" [class.samar]="!c.b1">{{ c.b1 ? (c.b1 | rupiah: true) : '–' }}</td>
                <td class="r" [class.samar]="!c.b2" [class.t-peringatan]="c.b2">{{ c.b2 ? (c.b2 | rupiah: true) : '–' }}</td>
                <td class="r" [class.samar]="!c.b3" [class.t-bahaya]="c.b3">{{ c.b3 ? (c.b3 | rupiah: true) : '–' }}</td>
                <td class="r" [class.samar]="!c.b4" [class.t-bahaya]="c.b4">{{ c.b4 ? (c.b4 | rupiah: true) : '–' }}</td>
                <td class="r tebal">{{ c.total | rupiah: true }} @if (c.total > c.limit_kredit) { <div class="kecil t-bahaya">melebihi limit</div> }</td>
                <td><app-status [nilai]="c.tahap" /></td>
              </tr>
            } @empty { <tr><td colspan="8"><app-kosong judul="Tidak ada piutang" ikon="piutang" /></td></tr> }
          </tbody>
        </table>
      </div>
    </section>`,
})
export class Piutang implements OnInit {
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly data = signal<BarisPiutang[]>([]);
  readonly r = signal<Record<string, number> | null>(null);
  readonly tanggal = signal('');
  readonly fokus = signal('');
  q = '';
  segmen: string | null = null;
  hanyaLewat = false;
  private t?: ReturnType<typeof setTimeout>;
  readonly bucket = [
    { k: 'b0', label: 'Belum jatuh tempo', warna: 'var(--g1)' },
    { k: 'b1', label: '1–30 hari', warna: '#7fb3a6' },
    { k: 'b2', label: '31–60 hari', warna: '#d9b36a' },
    { k: 'b3', label: '61–90 hari', warna: '#cf8a5c' },
    { k: 'b4', label: '> 90 hari', warna: 'var(--bahaya)' },
  ];
  readonly tampil = computed(() => {
    const f = this.fokus() as keyof BarisPiutang;
    return f ? this.data().filter((c) => (c[f] as number) > 0).sort((a, b) => (b[f] as number) - (a[f] as number)) : this.data();
  });

  ngOnInit(): void {
    this.muat();
  }

  tunda(): void {
    clearTimeout(this.t);
    this.t = setTimeout(() => this.muat(), 300);
  }

  async muat(): Promise<void> {
    const d = await this.api.get<{ tanggal: string; ringkasan: Record<string, number>; customer: BarisPiutang[] }>('/piutang',
      { q: this.q, segmen: this.segmen ?? '', hanya_lewat: this.hanyaLewat || null });
    this.data.set(d.customer);
    this.r.set(d.ringkasan);
    this.tanggal.set(d.tanggal);
  }

  ekspor(): void {
    unduhCsv<BarisPiutang>('umur-piutang', [
      { label: 'Customer', nilai: (r) => r.customer }, { label: 'Segmen', nilai: (r) => r.segmen }, { label: 'Kota', nilai: (r) => r.kota },
      { label: 'Belum jatuh tempo', nilai: (r) => r.b0 }, { label: '1-30', nilai: (r) => r.b1 }, { label: '31-60', nilai: (r) => r.b2 },
      { label: '61-90', nilai: (r) => r.b3 }, { label: '>90', nilai: (r) => r.b4 }, { label: 'Total', nilai: (r) => r.total },
      { label: 'Limit kredit', nilai: (r) => r.limit_kredit }, { label: 'Tahap penagihan', nilai: (r) => r.tahap },
    ], this.tampil());
  }

  persen(k: string): number {
    const r = this.r();
    return r && r['total'] ? (r[k] / r['total']) * 100 : 0;
  }
}
