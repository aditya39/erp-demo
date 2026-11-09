import { Component, computed, effect, inject, Injectable, input, OnDestroy, signal } from '@angular/core';
import { persen } from '../core/format';
import { Ikon } from './ikon';

export interface Remah {
  label: string;
  tautan?: string;
}

/** Breadcrumb halaman aktif, ditampilkan di topbar. */
@Injectable({ providedIn: 'root' })
export class Jejak {
  readonly remah = signal<Remah[]>([]);
}

/**
 * Header halaman: judul + slot [judul-ekstra] (badge) + slot [meta] (baris info) + slot default (tombol aksi).
 * Input `jejak` mengisi breadcrumb di topbar.
 */
@Component({
  selector: 'app-judul',
  template: `
    <header class="hal-kepala">
      <div class="hal-kiri">
        <div class="hal-judul"><h1>{{ judul() }}</h1><ng-content select="[judul-ekstra]" /></div>
        <div class="hal-meta"><ng-content select="[meta]" /></div>
      </div>
      <div class="hal-aksi"><ng-content /></div>
    </header>`,
})
export class Judul implements OnDestroy {
  readonly judul = input.required<string>();
  readonly jejak = input<Remah[]>([]);
  private j = inject(Jejak);

  constructor() {
    effect(() => this.j.remah.set(this.jejak().length ? this.jejak() : [{ label: this.judul() }]));
  }

  ngOnDestroy(): void {
    this.j.remah.set([]);
  }
}

const VARIAN: Record<string, string> = {
  Lunas: 'sukses', 'Faktur Terbit': 'sukses', Aman: 'sukses', Lancar: 'sukses', disetujui: 'sukses', Produksi: 'sukses', Aktif: 'sukses',
  Sebagian: 'info', 'Pengingat otomatis': 'info', Penjualan: 'garis',
  'Belum Lunas': 'netral', Ditolak: 'netral', Dibatalkan: 'netral', Nonaktif: 'netral', Toko: 'garis', Distributor: 'garis', 'Retail Modern': 'garis',
  'Menunggu Persetujuan': 'peringatan', Menipis: 'peringatan', menunggu: 'peringatan', 'Surat teguran resmi': 'peringatan',
  'Kunjungan / panggilan penagihan': 'peringatan', Penyesuaian: 'garis',
  'Jatuh Tempo': 'bahaya', Ditahan: 'bahaya', Habis: 'bahaya', ditolak: 'bahaya', 'Credit hold': 'bahaya', 'Keputusan Direktur': 'bahaya',
};

@Component({
  selector: 'app-status',
  template: `<span class="badge" [class]="'badge b-' + varian()">@if (titik()) { <i></i> }{{ label() || nilai() }}</span>`,
})
export class Status {
  readonly nilai = input.required<string>();
  readonly label = input('');
  readonly varian = computed(() => VARIAN[this.nilai()] ?? 'netral');
  readonly titik = computed(() => this.varian() !== 'garis');
}

/** Perubahan persen. `terbalik` = kenaikan itu buruk (mis. HPP, harga bahan). */
@Component({
  selector: 'app-delta',
  imports: [Ikon],
  template: `
    @if (nilai() !== null && nilai() !== undefined) {
      <span class="delta" [class.baik]="baik()" [class.buruk]="buruk()">
        @if (nilai()! > 0) { <app-ikon n="naik" /> } @else if (nilai()! < 0) { <app-ikon n="turun" /> }
        {{ teks() }}
      </span>
    } @else { <span class="delta">–</span> }`,
})
export class Delta {
  readonly nilai = input<number | null | undefined>(null);
  readonly terbalik = input(false);
  readonly teks = computed(() => persen(Math.abs(this.nilai() ?? 0), false));
  readonly baik = computed(() => ((this.nilai() ?? 0) > 0) !== this.terbalik() && (this.nilai() ?? 0) !== 0);
  readonly buruk = computed(() => ((this.nilai() ?? 0) < 0) !== this.terbalik() && (this.nilai() ?? 0) !== 0);
}

@Component({
  selector: 'app-kosong',
  imports: [Ikon],
  template: `<div class="kosong"><app-ikon [n]="ikon()" [ukuran]="22" /><b>{{ judul() }}</b>@if (isi()) { <p>{{ isi() }}</p> }<ng-content /></div>`,
})
export class Kosong {
  readonly ikon = input('inbox');
  readonly judul = input('Belum ada data');
  readonly isi = input('');
}

@Component({
  selector: 'app-avatar',
  template: `<span class="avatar" [class.avatar-kecil]="ukuran() === 'kecil'" [class.avatar-besar]="ukuran() === 'besar'">{{ inisial() }}</span>`,
})
export class Avatar {
  readonly nama = input.required<string>();
  readonly ukuran = input<'kecil' | 'normal' | 'besar'>('normal');
  readonly inisial = computed(() => this.nama().replace(/^(PT|CV|Toko|Toserba|Swalayan|Mart)\s+/i, '').split(/\s+/).slice(0, 2)
    .map((k) => k[0]).join('').toUpperCase());
}

export const UI = [Judul, Status, Delta, Kosong, Avatar, Ikon];
