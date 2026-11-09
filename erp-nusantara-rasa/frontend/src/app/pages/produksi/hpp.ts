import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Asisten } from '../../ai/asisten';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { bulan } from '../../core/format';
import { PIPES } from '../../core/pipes';
import { Grafik } from '../../shared/grafik';
import { UI } from '../../shared/ui';

interface BarisHpp {
  id: number;
  kode: string;
  produk: string;
  unit_diproduksi: number;
  bahan_baku_per_unit: number;
  tenaga_kerja_per_unit: number;
  overhead_per_unit: number;
  hpp_per_unit: number;
  hpp_lalu: number;
  harga_jual: number;
  margin: number;
  margin_lalu: number;
  ubah: number | null;
  perlu_kajian: boolean;
}

@Component({
  selector: 'app-hpp',
  imports: [RouterLink, Grafik, ...UI, ...PIPES],
  template: `
    <app-judul judul="Analisis HPP" [jejak]="[{ label: 'Produksi & biaya' }, { label: 'Analisis HPP' }]">
      <ng-container meta><span>{{ d()?.bulan | bulan }} dibanding {{ d()?.bulan_lalu | bulan }}</span>
        <a routerLink="/dokumen/04-Panduan-Perhitungan-HPP"><app-ikon n="kebijakan" />Panduan perhitungan HPP</a></ng-container>
    </app-judul>

    @if (kajian().length) {
      <div class="pita p-peringatan"><app-ikon n="awas" />
        <div class="pita-isi"><b>{{ kajian().length }} produk perlu kajian harga</b><p>{{ kajianNama() }} · HPP naik lebih dari 8% (KBJ-PJL-002)</p></div>
        @if (auth.punya('ai')) {
          <div class="pita-aksi"><button class="tanya-asisten" (click)="ai.tanya('Kenapa HPP ' + kajian()[0].produk + ' naik bulan ini? Produk apa lagi yang terdampak?')">
            <app-ikon n="asisten" />Telusuri penyebab</button></div>
        }
      </div>
    }

    <div class="grid g-2-1">
      <section class="panel">
        <table class="tabel">
          <thead><tr><th>Produk</th><th class="r">Bahan</th><th class="r">Tenaga kerja</th><th class="r">Overhead</th><th class="r">HPP / unit</th><th class="r">Perubahan</th><th class="r">Margin</th></tr></thead>
          <tbody>
            @for (r of d()?.data ?? []; track r.id) {
              <tr [class.sorot]="r.perlu_kajian">
                <td><div class="sel-utama"><a [routerLink]="'/produksi/produk/' + r.id">{{ r.produk }}</a><small>{{ r.kode }} · {{ r.unit_diproduksi | angka }} unit</small></div></td>
                <td class="r">{{ r.bahan_baku_per_unit | rupiah }}</td>
                <td class="r redup">{{ r.tenaga_kerja_per_unit | rupiah }}</td>
                <td class="r redup">{{ r.overhead_per_unit | rupiah }}</td>
                <td class="r tebal">{{ r.hpp_per_unit | rupiah }}</td>
                <td class="r"><app-delta [nilai]="r.ubah" [terbalik]="true" /></td>
                <td class="r"><span class="margin" [class.rendah]="r.margin < 30">{{ r.margin | angka: 1 }}%</span><div class="kecil samar">{{ r.margin_lalu | angka: 1 }}% bln lalu</div></td>
              </tr>
            }
          </tbody>
        </table>
      </section>
      <section class="panel">
        <div class="panel-kepala"><h3>Rata-rata HPP per unit<span class="panel-sub">12 bulan</span></h3></div>
        <div class="panel-isi"><app-grafik tipe="line" [label]="tren().label" [seri]="tren().seri" formatNilai="rupiah" [tinggi]="230" /></div>
        <div class="panel-kaki">HPP = bahan baku (resep × harga beli) + tenaga kerja + overhead per unit.</div>
      </section>
    </div>`,
})
export class AnalisisHpp implements OnInit {
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly d = signal<{ bulan: string; bulan_lalu: string; data: BarisHpp[]; tren: { bulan: string; rata_hpp: number }[] } | null>(null);
  readonly kajian = computed(() => (this.d()?.data ?? []).filter((r) => r.perlu_kajian).sort((a, b) => (b.ubah ?? 0) - (a.ubah ?? 0)));
  readonly kajianNama = computed(() => this.kajian().map((r) => `${r.produk} (+${String(r.ubah).replace('.', ',')}%)`).join(', '));
  readonly tren = computed(() => {
    const t = this.d()?.tren ?? [];
    return { label: t.map((x) => bulan(x.bulan, true)), seri: [{ nama: 'Rata-rata HPP', data: t.map((x) => x.rata_hpp) }] };
  });

  async ngOnInit(): Promise<void> {
    this.d.set(await this.api.get('/hpp'));
  }
}
