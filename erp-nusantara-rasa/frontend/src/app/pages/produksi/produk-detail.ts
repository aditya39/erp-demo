import { Component, computed, inject, input, OnChanges, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { Asisten } from '../../ai/asisten';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { bulan } from '../../core/format';
import { PIPES } from '../../core/pipes';
import { Grafik } from '../../shared/grafik';
import { UI } from '../../shared/ui';

interface DetailProduk {
  id: number;
  kode: string;
  nama: string;
  kategori: string;
  satuan: string;
  harga_jual: number;
  hpp_bulanan?: { bulan: string; unit_diproduksi: number; bahan_baku_per_unit: number; tenaga_kerja_per_unit: number; overhead_per_unit: number; hpp_per_unit: number }[];
  resep?: { bahan_id: number; kode: string; bahan: string; satuan: string; qty_per_unit: number; harga_bahan: number; biaya_per_unit: number; biaya_per_unit_lalu: number | null; ubah: number | null }[];
  penjualan_bulanan?: { bulan: string; qty: number; nilai: number }[];
  per_segmen?: { segmen: string; qty: number; nilai: number }[];
  customer_teratas?: { id: number; customer: string; segmen: string; qty: number; nilai: number }[];
  stok?: { gudang: string; qty: number; stok_minimum: number; menipis: boolean }[];
}

@Component({
  selector: 'app-produk-detail',
  imports: [FormsModule, RouterLink, Grafik, DialogModule, InputNumberModule, ...UI, ...PIPES],
  templateUrl: './produk-detail.html',
})
export class ProdukDetail implements OnChanges {
  readonly id = input.required<string>();
  private api = inject(Api);
  private pesan = inject(MessageService);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly p = signal<DetailProduk | null>(null);
  readonly dialogHarga = signal(false);
  readonly galat = signal('');
  hargaBaru = 0;

  readonly hppKini = computed(() => this.p()?.hpp_bulanan?.at(-1) ?? null);
  readonly hppLalu = computed(() => this.p()?.hpp_bulanan?.at(-2) ?? null);
  readonly ubahHpp = computed(() => {
    const k = this.hppKini(), l = this.hppLalu();
    return k && l ? Math.round(((k.hpp_per_unit - l.hpp_per_unit) / l.hpp_per_unit) * 1000) / 10 : null;
  });
  readonly margin = computed(() => {
    const k = this.hppKini(), p = this.p();
    return k && p ? Math.round(((p.harga_jual - k.hpp_per_unit) / p.harga_jual) * 1000) / 10 : null;
  });
  readonly marginLalu = computed(() => {
    const l = this.hppLalu(), p = this.p();
    return l && p ? Math.round(((p.harga_jual - l.hpp_per_unit) / p.harga_jual) * 1000) / 10 : null;
  });
  readonly grafikHpp = computed(() => {
    const h = this.p()?.hpp_bulanan ?? [];
    return {
      label: h.map((x) => bulan(x.bulan, true)),
      seri: [
        { nama: 'Bahan baku', data: h.map((x) => x.bahan_baku_per_unit) },
        { nama: 'Tenaga kerja', data: h.map((x) => x.tenaga_kerja_per_unit) },
        { nama: 'Overhead', data: h.map((x) => x.overhead_per_unit) },
      ],
    };
  });
  readonly grafikJual = computed(() => {
    const j = this.p()?.penjualan_bulanan ?? [];
    return { label: j.map((x) => bulan(x.bulan, true)), seri: [{ nama: 'Qty terjual', data: j.map((x) => x.qty) }] };
  });
  readonly totalStok = computed(() => (this.p()?.stok ?? []).reduce((a, s) => a + s.qty, 0));
  readonly totalSegmen = computed(() => (this.p()?.per_segmen ?? []).reduce((a, s) => a + s.nilai, 0) || 1);

  ngOnChanges(): void {
    this.muat();
  }

  async muat(): Promise<void> {
    this.p.set(await this.api.get<DetailProduk>(`/produk/${this.id()}`));
  }

  bukaHarga(): void {
    this.hargaBaru = this.p()!.harga_jual;
    this.galat.set('');
    this.dialogHarga.set(true);
  }

  async simpanHarga(): Promise<void> {
    try {
      await this.api.put(`/produk/${this.id()}/harga`, { harga_jual: this.hargaBaru });
      this.dialogHarga.set(false);
      this.pesan.add({ severity: 'success', summary: 'Harga jual diperbarui', detail: this.p()!.nama, life: 4000 });
      this.muat();
    } catch (e) {
      this.galat.set(pesanGalat(e));
    }
  }

  tanyaHpp(): void {
    this.ai.tanya(`Kenapa HPP ${this.p()!.nama} naik bulan ini? Produk apa lagi yang terdampak?`);
  }

  tanyaJual(): void {
    this.ai.tanya(`Bagaimana tren penjualan ${this.p()!.nama} per segmen 6 bulan terakhir?`);
  }
}
