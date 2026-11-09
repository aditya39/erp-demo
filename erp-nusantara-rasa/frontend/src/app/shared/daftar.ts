import { signal } from '@angular/core';
import { TableLazyLoadEvent } from 'primeng/table';
import { Api } from '../core/api';
import { Halaman } from '../core/model';

/**
 * Status daftar ber-paginasi di server (dipakai p-table mode lazy).
 * Filter disimpan di `filter`; panggil `segarkan()` setelah filter berubah.
 */
export class DaftarServer<T> {
  readonly baris = signal<T[]>([]);
  readonly total = signal(0);
  readonly memuat = signal(true);
  readonly ekstra = signal<Record<string, unknown>>({});
  readonly halaman = signal(0);
  filter: Record<string, string | number | boolean | null> = {};
  private terakhir: TableLazyLoadEvent = { first: 0, rows: 20 };
  private tunda?: ReturnType<typeof setTimeout>;

  constructor(private api: Api, private url: string, private urutAwal = '-tanggal') {}

  async muat(ev: TableLazyLoadEvent = this.terakhir): Promise<void> {
    this.terakhir = ev;
    const size = ev.rows ?? 20;
    const page = Math.floor((ev.first ?? 0) / size) + 1;
    const field = Array.isArray(ev.sortField) ? ev.sortField[0] : ev.sortField;
    const sort = field ? `${ev.sortOrder === -1 ? '-' : ''}${field}` : this.urutAwal;
    this.memuat.set(true);
    try {
      const h = await this.api.get<Halaman<T> & Record<string, unknown>>(this.url, { ...this.filter, page, size, sort });
      const { data, total, ...lain } = h;
      this.baris.set(data);
      this.total.set(total);
      this.ekstra.set(lain);
      this.halaman.set(ev.first ?? 0);
    } finally {
      this.memuat.set(false);
    }
  }

  /** Semua baris sesuai filter & urutan saat ini (untuk ekspor CSV). */
  async semua(): Promise<T[]> {
    const ev = this.terakhir;
    const field = Array.isArray(ev.sortField) ? ev.sortField[0] : ev.sortField;
    const sort = field ? `${ev.sortOrder === -1 ? '-' : ''}${field}` : this.urutAwal;
    return (await this.api.get<Halaman<T>>(this.url, { ...this.filter, page: 1, size: 5000, sort })).data;
  }

  segarkan(tunda = 0): void {
    clearTimeout(this.tunda);
    this.tunda = setTimeout(() => this.muat({ ...this.terakhir, first: 0 }), tunda);
  }
}
