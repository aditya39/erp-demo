import { Component, computed, inject, input, OnChanges, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { bulan } from '../../core/format';
import { Faktur, Kredit } from '../../core/model';
import { PIPES } from '../../core/pipes';
import { Grafik } from '../../shared/grafik';
import { UI } from '../../shared/ui';
import { CustomerForm, DataCustomer } from './customer-form';

interface DetailCustomer {
  id: number;
  kode: string;
  nama: string;
  kota: string;
  segmen: string;
  termin_hari: number;
  limit_kredit: number;
  alamat: string;
  kontak: string;
  telepon: string;
  aktif: boolean;
  diskon_standar: number;
  omzet_bulanan: { bulan: string; nilai: number; qty: number }[];
  produk_favorit: { id: number; produk: string; kategori: string; qty: number; nilai: number }[];
  faktur_terakhir: Faktur[];
  kredit: Kredit | null;
  faktur_terbuka: { id: number; nomor: string; tanggal: string; jatuh_tempo: string; total: number; sisa: number; hari: number }[] | null;
  so_menunggu: { id: number; nomor: string; tanggal: string; status: string; total: number }[];
}

@Component({
  selector: 'app-customer-detail',
  imports: [RouterLink, Grafik, CustomerForm, ...UI, ...PIPES],
  templateUrl: './customer-detail.html',
})
export class CustomerDetail implements OnChanges {
  readonly id = input.required<string>();
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly c = signal<DetailCustomer | null>(null);
  readonly form = signal<DataCustomer | null>(null);
  readonly tab = signal<'ringkasan' | 'faktur' | 'terbuka'>('ringkasan');

  readonly omzet12 = computed(() => (this.c()?.omzet_bulanan ?? []).reduce((a, x) => a + x.nilai, 0));
  readonly grafik = computed(() => {
    const b = this.c()?.omzet_bulanan ?? [];
    return { label: b.map((x) => bulan(x.bulan, true)), seri: [{ nama: 'Omzet', data: b.map((x) => x.nilai) }] };
  });
  readonly maksProduk = computed(() => Math.max(1, ...(this.c()?.produk_favorit ?? []).map((p) => p.nilai)));

  ngOnChanges(): void {
    this.muat();
  }

  async muat(): Promise<void> {
    this.c.set(await this.api.get<DetailCustomer>(`/customer/${this.id()}`));
  }

  ubah(): void {
    const c = this.c()!;
    this.form.set({ id: c.id, nama: c.nama, kota: c.kota, segmen: c.segmen, alamat: c.alamat ?? '', kontak: c.kontak ?? '',
                    telepon: c.telepon ?? '', limit_kredit: c.limit_kredit, aktif: c.aktif });
  }
}
