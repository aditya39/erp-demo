import { Component, computed, inject, input, OnChanges, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Asisten } from '../../ai/asisten';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { bulan } from '../../core/format';
import { PIPES } from '../../core/pipes';
import { Grafik } from '../../shared/grafik';
import { UI } from '../../shared/ui';

interface DetailBahan {
  id: number;
  kode: string;
  nama: string;
  satuan: string;
  harga_bulanan: { bulan: string; harga: number }[];
  produk: { id: number; produk: string; qty_per_unit: number; biaya_per_unit: number; hpp_per_unit: number; porsi_hpp: number }[];
}

@Component({
  selector: 'app-bahan-detail',
  imports: [RouterLink, Grafik, ...UI, ...PIPES],
  template: `
    @if (b(); as b) {
      <app-judul [judul]="b.nama" [jejak]="[{ label: 'Produksi & biaya' }, { label: 'Bahan baku', tautan: '/produksi/bahan-baku' }, { label: b.nama }]">
        <ng-container meta><span class="kode">{{ b.kode }}</span><span>Harga per {{ b.satuan }}</span></ng-container>
        @if (auth.punya('ai')) {
          <button class="btn" (click)="ai.tanya('Bagaimana riwayat harga ' + b.nama.toLowerCase() + ' 6 bulan terakhir dan produk apa saja yang terdampak?')">
            <app-ikon n="asisten" class="ikon-ai" />Tanya dampaknya</button>
        }
      </app-judul>
      <div class="statistik">
        <div class="stat"><span class="stat-label">Harga bulan ini</span><span class="stat-nilai">{{ kini()?.harga | rupiah }}</span>
          <span class="stat-ket"><app-delta [nilai]="ubah()" [terbalik]="true" /> dari {{ lalu()?.harga | rupiah }}</span></div>
        <div class="stat"><span class="stat-label">Perubahan 18 bulan</span><span class="stat-nilai">{{ ubahTotal() | persen }}</span>
          <span class="stat-ket">sejak {{ b.harga_bulanan[0]?.bulan | bulan }}</span></div>
        <div class="stat"><span class="stat-label">Dipakai di</span><span class="stat-nilai">{{ b.produk.length }} produk</span><span class="stat-ket">lihat tabel di bawah</span></div>
      </div>
      <div class="grid g-2-1">
        <section class="panel">
          <div class="panel-kepala"><h3>Riwayat harga<span class="panel-sub">per {{ b.satuan }}</span></h3></div>
          <div class="panel-isi"><app-grafik tipe="line" [label]="grafik().label" [seri]="grafik().seri" formatNilai="rupiah" [tinggi]="250" /></div>
        </section>
        <section class="panel">
          <div class="panel-kepala"><h3>Produk pemakai</h3><span class="redup kecil">porsi dalam HPP</span></div>
          <table class="tabel"><tbody>@for (p of b.produk; track p.id) {
            <tr><td><div class="sel-utama"><a [routerLink]="'/produksi/produk/' + p.id">{{ p.produk }}</a><small>{{ p.qty_per_unit | angka: 3 }} {{ b.satuan }} per unit · {{ p.biaya_per_unit | rupiah }}</small></div></td>
              <td class="r tebal">{{ p.porsi_hpp | angka: 1 }}%</td></tr>
          }</tbody></table>
        </section>
      </div>
    }`,
})
export class BahanDetail implements OnChanges {
  readonly id = input.required<string>();
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly b = signal<DetailBahan | null>(null);
  readonly kini = computed(() => this.b()?.harga_bulanan.at(-1));
  readonly lalu = computed(() => this.b()?.harga_bulanan.at(-2));
  readonly ubah = computed(() => {
    const k = this.kini(), l = this.lalu();
    return k && l ? Math.round(((k.harga - l.harga) / l.harga) * 1000) / 10 : null;
  });
  readonly ubahTotal = computed(() => {
    const h = this.b()?.harga_bulanan ?? [];
    return h.length > 1 ? Math.round(((h.at(-1)!.harga - h[0].harga) / h[0].harga) * 1000) / 10 : null;
  });
  readonly grafik = computed(() => {
    const h = this.b()?.harga_bulanan ?? [];
    return { label: h.map((x) => bulan(x.bulan, true)), seri: [{ nama: this.b()?.nama ?? '', data: h.map((x) => x.harga) }] };
  });

  ngOnChanges(): void {
    this.api.get<DetailBahan>(`/bahan-baku/${this.id()}`).then((b) => this.b.set(b));
  }
}
