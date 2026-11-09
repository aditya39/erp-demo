import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Asisten } from '../ai/asisten';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { bulan, rupiahRingkas } from '../core/format';
import { PIPES } from '../core/pipes';
import { Grafik } from '../shared/grafik';
import { UI } from '../shared/ui';

interface Kartu {
  kode: string;
  label: string;
  nilai: number;
  format: 'rupiah' | 'angka';
  ubah?: number | null;
  sub?: string;
  sub_nilai?: number;
  seri?: number[];
}

interface Insight {
  ikon: string;
  tingkat: 'merah' | 'kuning' | 'hijau' | 'biru';
  judul: string;
  isi: string;
  tautan?: string;
  aksi?: string;
  tanya?: string;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, Grafik, ...UI, ...PIPES],
  templateUrl: './dashboard.html',
})
export class Dashboard implements OnInit {
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly d = signal<any>(null);
  readonly muat = signal(true);


  readonly kartu = computed<Kartu[]>(() => this.d()?.kartu ?? []);
  readonly labelTerkunci: Record<string, string> = { omzet: 'Omzet bulan ini', faktur: 'Faktur terbit', piutang: 'Piutang lewat jatuh tempo', stok: 'Stok di bawah minimum' };

  readonly omzet = computed(() => {
    const b = this.d()?.omzet_bulanan ?? [];
    return { label: b.map((x: any) => bulan(x.bulan, true)), seri: [{ nama: 'Omzet', data: b.map((x: any) => x.nilai) }] };
  });

  readonly kategori = computed(() => {
    const k = this.d()?.kategori ?? [];
    const total = k.reduce((a: number, x: any) => a + x.nilai, 0) || 1;
    return k.map((x: any) => ({ nama: x.kategori, nilai: x.nilai, persen: (x.nilai / total) * 100 }));
  });

  readonly totalKategori = computed(() => (this.d()?.kategori ?? []).reduce((a: number, x: any) => a + x.nilai, 0));

  readonly aging = computed(() => {
    const a = this.d()?.aging;
    if (!a) return [];
    const total = a.total || 1;
    return [
      { label: 'Belum jatuh tempo', nilai: a.b0, warna: 'var(--g1)' },
      { label: '1–30 hari', nilai: a.b1, warna: '#7fb3a6' },
      { label: '31–60 hari', nilai: a.b2, warna: '#d9b36a' },
      { label: '61–90 hari', nilai: a.b3, warna: '#cf8a5c' },
      { label: '> 90 hari', nilai: a.b4, warna: 'var(--bahaya)' },
    ].map((x) => ({ ...x, persen: (x.nilai / total) * 100 }));
  });

  readonly insight = computed<Insight[]>(() => {
    const d = this.d();
    if (!d) return [];
    const out: Insight[] = [];
    for (const s of d.so_menunggu ?? []) {
      if (s.bisa_saya)
        out.push({ ikon: 'setuju', tingkat: 'kuning', judul: `Persetujuan ${s.nomor}`,
                   isi: `${s.customer} · ${s.perlu.map((p: any) => p.judul).join(', ')}`, tautan: `/penjualan/sales-order/${s.id}`, aksi: 'Tinjau' });
    }
    for (const h of d.hpp_naik ?? [])
      out.push({ ikon: 'hpp', tingkat: 'merah', judul: `HPP ${h.produk} naik ${String(h.ubah).replace('.', ',')}%`,
                 isi: 'Melewati ambang 8% · perlu kajian harga', tautan: `/produksi/produk/${h.id}`,
                 tanya: `Kenapa HPP ${h.produk} naik bulan ini? Produk apa lagi yang terdampak?` });
    for (const p of d.produk_teratas ?? []) {
      if ((p.ubah ?? 0) >= 15)
        out.push({ ikon: 'trend_naik', tingkat: 'hijau', judul: `Penjualan ${p.produk} naik ${String(p.ubah).replace('.', ',')}%`,
                   isi: 'Qty dibanding bulan lalu', tautan: `/produksi/produk/${p.id}`,
                   tanya: `Bagaimana tren penjualan ${p.produk} per segmen 6 bulan terakhir?` });
    }
    for (const c of (d.penunggak ?? []).slice(0, 2))
      out.push({ ikon: 'awas', tingkat: 'merah', judul: `${c.customer} menunggak ${c.hari} hari`,
                 isi: `Sisa ${rupiahRingkas(c.sisa)} · credit hold`, tautan: `/penjualan/customer/${c.id}`,
                 tanya: this.auth.punya('dokumen') ? 'Apa tahapan penagihan untuk faktur yang lewat jatuh tempo lebih dari 90 hari?' : undefined });
    const stok = d.stok_menipis ?? [];
    if (stok.length)
      out.push({ ikon: 'stok', tingkat: 'kuning', judul: `${stok.length} stok di bawah minimum`,
                 isi: stok.slice(0, 3).map((s: any) => `${s.nama} (${s.gudang.replace('Gudang ', '')})`).join(', '),
                 tautan: '/persediaan/stok' });
    return out.map((i) => (i.tanya && !this.auth.punya('ai') ? { ...i, tanya: undefined } : i)).slice(0, 6);
  });

  async ngOnInit(): Promise<void> {
    try {
      this.d.set(await this.api.get('/dashboard'));
    } finally {
      this.muat.set(false);
    }
  }

  terkunci(kode: string): boolean {
    return (this.d()?.terkunci ?? []).includes(kode);
  }

  lebar(n: number, maks: number): number {
    return maks ? Math.max(4, (n / maks) * 100) : 0;
  }

  maksProduk = computed(() => Math.max(...(this.d()?.produk_teratas ?? []).map((p: any) => p.nilai ?? 0), 1));
  maksCustomer = computed(() => Math.max(...(this.d()?.customer_teratas ?? []).map((p: any) => p.nilai ?? 0), 1));
}
