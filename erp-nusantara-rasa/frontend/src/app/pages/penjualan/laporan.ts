import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Asisten } from '../../ai/asisten';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { bulan } from '../../core/format';
import { PIPES } from '../../core/pipes';
import { Grafik } from '../../shared/grafik';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface Laporan {
  awal: string;
  akhir: string;
  dimensi: string;
  baris: { nama: string; qty: number; nilai: number; faktur: number; nilai_awal: number | null; nilai_akhir: number | null; porsi: number }[];
  seri: { bulan: string; nama: string; nilai: number }[];
  total: number;
}

@Component({
  selector: 'app-laporan-penjualan',
  imports: [Grafik, ...UI, ...PIPES],
  template: `
    <app-judul judul="Laporan penjualan" [jejak]="[{ label: 'Penjualan' }, { label: 'Laporan penjualan' }]">
      <ng-container meta>@if (lap(); as l) { <span>{{ l.awal | bulan }} – {{ l.akhir | bulan }}</span><span>Total {{ l.total | rupiah: true }}</span> }</ng-container>
      <div class="segmen">@for (b of [3, 6, 12, 18]; track b) { <button [class.aktif]="bln() === b" (click)="bln.set(b); muat()">{{ b }} bulan</button> }</div>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
    </app-judul>

    <div class="tab">
      @for (d of dimensi; track d.kode) { <button [class.aktif]="dim() === d.kode" (click)="dim.set(d.kode); muat()">Per {{ d.label.toLowerCase() }}</button> }
    </div>

    <section class="panel" style="margin-bottom: 16px">
      <div class="panel-kepala"><h3>Tren 5 {{ labelDim().toLowerCase() }} teratas<span class="panel-sub">nilai penjualan per bulan</span></h3>
        @if (auth.punya('ai')) { <button class="tanya-asisten" (click)="ai.tanya(pertanyaan())"><app-ikon n="asisten" />Tanya Asisten kenapa</button> }</div>
      <div class="panel-isi"><app-grafik tipe="line" [label]="grafik().label" [seri]="grafik().seri" formatNilai="rupiah" [tinggi]="270" [area]="false" /></div>
    </section>

    <section class="panel">
      <table class="tabel">
        <thead><tr><th style="width: 40px">#</th><th>{{ labelDim() }}</th><th class="r">Qty</th><th class="r">Faktur</th><th class="r">Nilai</th><th style="width: 22%">Porsi</th><th class="r">Tren</th></tr></thead>
        <tbody>
          @for (b of lap()?.baris ?? []; track b.nama; let i = $index) {
            <tr>
              <td class="samar">{{ i + 1 }}</td>
              <td class="tebal">{{ b.nama }}</td>
              <td class="r">{{ b.qty | angka }}</td>
              <td class="r redup">{{ b.faktur | angka }}</td>
              <td class="r tebal">{{ b.nilai | rupiah: true }}</td>
              <td><div class="porsi"><div class="meter"><i [style.width.%]="b.porsi * maksPorsi()"></i></div><span>{{ b.porsi | angka: 1 }}%</span></div></td>
              <td class="r"><app-delta [nilai]="tren(b)" /></td>
            </tr>
          }
        </tbody>
      </table>
      <div class="panel-kaki">Tren membandingkan rata-rata bulanan paruh kedua periode terhadap paruh pertama.</div>
    </section>`,
})
export class LaporanPenjualan implements OnInit {
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly lap = signal<Laporan | null>(null);
  readonly dim = signal('produk');
  readonly bln = signal(6);
  readonly dimensi = [
    { kode: 'produk', label: 'Produk' }, { kode: 'customer', label: 'Customer' }, { kode: 'kota', label: 'Kota' },
    { kode: 'segmen', label: 'Segmen' }, { kode: 'kategori', label: 'Kategori' },
  ];
  readonly labelDim = computed(() => this.dimensi.find((d) => d.kode === this.dim())!.label);
  readonly maksPorsi = computed(() => 100 / Math.max(1, ...(this.lap()?.baris ?? []).map((b) => b.porsi)));

  readonly grafik = computed(() => {
    const l = this.lap();
    if (!l) return { label: [], seri: [] };
    const bulanList = [...new Set(l.seri.map((s) => s.bulan))].sort();
    const nama = l.baris.slice(0, 5).map((b) => b.nama);
    return {
      label: bulanList.map((b) => bulan(b, true)),
      seri: nama.map((n) => ({ nama: n, data: bulanList.map((b) => l.seri.find((s) => s.bulan === b && s.nama === n)?.nilai ?? 0) })),
    };
  });

  ngOnInit(): void {
    this.muat();
  }

  async muat(): Promise<void> {
    this.lap.set(await this.api.get<Laporan>('/laporan/penjualan', { dimensi: this.dim(), bulan: this.bln() }));
  }

  readonly pertanyaan = computed(() => {
    const top = this.lap()?.baris[0]?.nama ?? 'Biskuit Kelapa';
    return this.dim() === 'produk' ? `Bagaimana tren penjualan ${top} per segmen ${this.bln()} bulan terakhir?`
      : `${this.labelDim()} mana yang penjualannya paling besar ${this.bln()} bulan terakhir?`;
  });

  ekspor(): void {
    unduhCsv<Laporan['baris'][0]>(`laporan-penjualan-per-${this.dim()}`, [
      { label: this.labelDim(), nilai: (r) => r.nama }, { label: 'Qty', nilai: (r) => r.qty }, { label: 'Faktur', nilai: (r) => r.faktur },
      { label: 'Nilai', nilai: (r) => r.nilai }, { label: 'Porsi %', nilai: (r) => r.porsi }, { label: 'Tren %', nilai: (r) => this.tren(r) },
    ], this.lap()?.baris ?? []);
  }

  tren(b: Laporan['baris'][0]): number | null {
    if (!b.nilai_awal || b.nilai_akhir === null) return null;
    return Math.round(((b.nilai_akhir - b.nilai_awal) / b.nilai_awal) * 1000) / 10;
  }
}
