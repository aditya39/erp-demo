import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api';
import { PIPES } from '../../core/pipes';
import { UI } from '../../shared/ui';

interface BarisBahan {
  id: number;
  kode: string;
  nama: string;
  satuan: string;
  harga: number;
  harga_lalu: number;
  ubah: number | null;
  ubah_12: number | null;
  dipakai_produk: number;
}

@Component({
  selector: 'app-bahan-daftar',
  imports: [FormsModule, RouterLink, ...UI, ...PIPES],
  template: `
    <app-judul judul="Bahan baku" [jejak]="[{ label: 'Produksi & biaya' }, { label: 'Bahan baku' }]">
      <ng-container meta><span>Harga rata-rata pembelian {{ bulan() | bulan }}</span><span>Sumber biaya bahan dalam HPP</span></ng-container>
    </app-judul>
    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" /><input [(ngModel)]="q" (ngModelChange)="tunda()" placeholder="Cari bahan" /></div>
        <span class="spacer"></span><span class="ringkas-tabel">Disorot: naik lebih dari 5% dari bulan lalu</span>
      </div>
      <table class="tabel">
        <thead><tr><th>Bahan</th><th>Satuan</th><th class="r">Harga bulan ini</th><th class="r">Bulan lalu</th><th class="r">Perubahan</th><th class="r">12 bulan</th><th class="r">Dipakai di</th></tr></thead>
        <tbody>
          @for (b of data(); track b.id) {
            <tr class="klik" [class.sorot]="(b.ubah ?? 0) > 5" (click)="router.navigate(['/produksi/bahan-baku', b.id])">
              <td><div class="sel-utama"><a [routerLink]="'/produksi/bahan-baku/' + b.id" (click)="$event.stopPropagation()">{{ b.nama }}</a><small>{{ b.kode }}</small></div></td>
              <td class="redup">{{ b.satuan }}</td>
              <td class="r tebal">{{ b.harga | rupiah }}</td>
              <td class="r redup">{{ b.harga_lalu | rupiah }}</td>
              <td class="r"><app-delta [nilai]="b.ubah" [terbalik]="true" /></td>
              <td class="r"><app-delta [nilai]="b.ubah_12" [terbalik]="true" /></td>
              <td class="r redup">{{ b.dipakai_produk }} produk</td>
            </tr>
          }
        </tbody>
      </table>
    </section>`,
})
export class BahanDaftar implements OnInit {
  private api = inject(Api);
  readonly router = inject(Router);
  readonly data = signal<BarisBahan[]>([]);
  readonly bulan = signal('');
  q = '';
  private t?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.muat();
  }

  tunda(): void {
    clearTimeout(this.t);
    this.t = setTimeout(() => this.muat(), 300);
  }

  async muat(): Promise<void> {
    const d = await this.api.get<{ data: BarisBahan[]; bulan: string }>('/bahan-baku', { q: this.q });
    this.data.set(d.data);
    this.bulan.set(d.bulan);
  }
}
