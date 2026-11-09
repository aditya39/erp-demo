import { Component, effect, ElementRef, inject, input, OnDestroy, viewChild } from '@angular/core';
import { Chart, ChartConfiguration, registerables } from 'chart.js';
import { angka, rupiahRingkas } from '../core/format';
import { Tampilan } from '../core/tampilan';

Chart.register(...registerables);

export const WARNA = ['#0e6b57', '#8a93a3', '#c08a2e', '#5679bf', '#ad5a6e', '#6c5fcf', '#3f8f7c', '#b8bec8'];

export interface Seri {
  nama: string;
  data: (number | null)[];
  warna?: string;
  tipe?: 'line' | 'bar';
  garisPutus?: boolean;
}

/** Pembungkus Chart.js dengan gaya ERP (mengikuti mode terang/gelap). */
@Component({
  selector: 'app-grafik',
  template: `<div class="grafik-wadah" [style.height.px]="tinggi()"><canvas #kanvas></canvas></div>`,
  styles: `.grafik-wadah { position: relative; width: 100%; }`,
})
export class Grafik implements OnDestroy {
  readonly tipe = input<'line' | 'bar' | 'doughnut'>('bar');
  readonly label = input<string[]>([]);
  readonly seri = input<Seri[]>([]);
  readonly tinggi = input(260);
  readonly horizontal = input(false);
  readonly bertumpuk = input(false);
  readonly formatNilai = input<'angka' | 'rupiah' | 'juta' | 'persen'>('angka');
  readonly legenda = input<boolean | null>(null);
  readonly mini = input(false);
  readonly area = input(true);
  /** Sumbu Y mulai dari nol (default: ya untuk bar & qty). */
  readonly nol = input<boolean | null>(null);

  private kanvas = viewChild.required<ElementRef<HTMLCanvasElement>>('kanvas');
  private tampilan = inject(Tampilan);
  private chart?: Chart;

  constructor() {
    effect(() => {
      this.tampilan.gelap();
      this.gambar();
    });
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }

  private fmt(v: number): string {
    switch (this.formatNilai()) {
      case 'rupiah': return Math.abs(v) < 1e6 ? 'Rp ' + angka(v) : rupiahRingkas(v);
      case 'juta': return angka(v) + ' jt';
      case 'persen': return angka(v, 1) + '%';
      default: return angka(v);
    }
  }

  private gambar(): void {
    const css = getComputedStyle(document.documentElement);
    const teks = css.getPropertyValue('--teks-3').trim() || '#69707c';
    const garis = css.getPropertyValue('--garis-halus').trim() || '#edeef1';
    const palet = ['--g1', '--g2', '--g3', '--g4', '--g5', '--g6'].map((v, i) => css.getPropertyValue(v).trim() || WARNA[i]);
    const tipe = this.tipe();
    const seri = this.seri();
    const mini = this.mini();
    const donat = tipe === 'doughnut';
    const tampilLegenda = this.legenda() ?? (donat || seri.length > 1);

    const datasets = donat
      ? [{ data: seri[0]?.data ?? [], backgroundColor: palet, borderWidth: 0, hoverOffset: 4 }]
      : seri.map((s, i) => {
          const w = s.warna ?? palet[i % palet.length];
          const t = s.tipe ?? tipe;
          return {
            type: t, label: s.nama, data: s.data, borderColor: w,
            backgroundColor: t === 'bar' ? w : w + '14',
            borderWidth: t === 'bar' ? 0 : mini ? 1.5 : 2, borderRadius: t === 'bar' ? 3 : 0,
            borderDash: s.garisPutus ? [5, 4] : [], tension: 0.25, pointRadius: mini ? 0 : t === 'line' ? 2.5 : 0,
            pointHoverRadius: 4, fill: t === 'line' && this.area() && seri.length === 1,
            maxBarThickness: this.horizontal() ? 14 : 28, order: t === 'line' ? 0 : 1,
          };
        });

    const konfig: ChartConfiguration = {
      type: tipe,
      data: { labels: this.label(), datasets: datasets as never },
      options: <ChartConfiguration['options']>{
        responsive: true, maintainAspectRatio: false, animation: { duration: 450 },
        indexAxis: this.horizontal() ? 'y' : 'x',
        interaction: { mode: donat ? 'nearest' : 'index', intersect: false },
        layout: { padding: mini ? 0 : { top: 4 } },
        ...(donat ? { cutout: '68%' } : {}),
        plugins: {
          legend: {
            display: tampilLegenda && !mini, position: donat ? 'right' : 'top', align: 'end',
            labels: { color: teks, boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'rectRounded', padding: 14,
                      font: { size: 12, family: 'Inter Variable, Inter, sans-serif' } },
          },
          tooltip: {
            enabled: !mini, backgroundColor: '#15181e', titleColor: '#ffffff', bodyColor: '#e3e5e8', padding: 9,
            cornerRadius: 6, boxPadding: 4, titleFont: { weight: 600 },
            callbacks: { label: (c) => ` ${c.dataset.label ?? c.label}: ${this.fmt(Number(donat ? c.raw : c.parsed[this.horizontal() ? 'x' : 'y']))}` },
          },
        },
        scales: donat ? {} : {
          x: {
            display: !mini, stacked: this.bertumpuk(), grid: { display: this.horizontal(), color: garis },
            border: { display: false },
            ticks: { color: teks, font: { size: 11 }, maxRotation: 0, autoSkipPadding: 12,
                     ...(this.horizontal() ? { callback: (v: unknown) => this.fmt(Number(v)) } : {}) },
          },
          y: {
            display: !mini, stacked: this.bertumpuk(), grid: { display: !this.horizontal(), color: garis },
            border: { display: false }, beginAtZero: this.nol() ?? (tipe === 'bar' || this.formatNilai() === 'angka'),
            ticks: {
              color: teks, font: { size: 11 }, maxTicksLimit: 6,
              callback: this.horizontal()
                ? (v) => { const l = this.label()[Number(v)] ?? ''; return l.length > 24 ? l.slice(0, 23) + '…' : l; }
                : (v) => this.fmt(Number(v)),
            },
          },
        },
      },
    };
    this.chart?.destroy();
    this.chart = new Chart(this.kanvas().nativeElement, konfig);
  }
}
