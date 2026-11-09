import { Component, computed, inject, input, OnChanges, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectModule } from 'primeng/select';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { Faktur, ItemBaris, Peristiwa, Tahap } from '../../core/model';
import { tanggal } from '../../core/format';
import { PIPES } from '../../core/pipes';
import { Riwayat, Tahapan } from '../../shared/dokumen';
import { UI } from '../../shared/ui';

export interface DetailFaktur extends Faktur {
  customer_info: { kode: string; nama: string; alamat: string; kontak: string; telepon: string; segmen: string; termin_hari: number };
  item: ItemBaris[];
  bruto: number;
  pembayaran: { id: number; tanggal: string; jumlah: number; metode: string; referensi: string; dibuat_oleh: string }[] | null;
  so: { id: number; nomor: string; dibuat_oleh: string; tanggal: string } | null;
  tahap: string;
  riwayat: Peristiwa[];
}

@Component({
  selector: 'app-faktur-detail',
  imports: [FormsModule, RouterLink, DialogModule, InputNumberModule, SelectModule, DatePickerModule, Tahapan, Riwayat, ...UI, ...PIPES],
  templateUrl: './faktur-detail.html',
})
export class FakturDetail implements OnChanges {
  readonly id = input.required<string>();
  private api = inject(Api);
  private pesan = inject(MessageService);
  readonly auth = inject(Auth);
  readonly f = signal<DetailFaktur | null>(null);
  readonly persenBayar = computed(() => {
    const f = this.f();
    return f && f.total ? Math.min(100, (f.terbayar / f.total) * 100) : 0;
  });

  readonly tahapan = computed<Tahap[]>(() => {
    const f = this.f();
    if (!f) return [];
    const lunas = f.status === 'Lunas';
    return [
      ...(f.so ? [{ label: 'Sales order', ket: f.so.nomor, keadaan: 'selesai' as const }] : []),
      { label: 'Faktur terbit', ket: tanggal(f.tanggal), keadaan: 'selesai' },
      { label: 'Jatuh tempo', ket: tanggal(f.jatuh_tempo) + (f.hari_lewat > 0 ? ` · lewat ${f.hari_lewat} hari` : ''),
        keadaan: lunas ? 'selesai' : f.hari_lewat > 0 ? 'gagal' : 'aktif' },
      { label: 'Lunas', ket: lunas ? 'Pembayaran lengkap' : f.terbayar > 0 ? `Terbayar ${Math.round(this.persenBayar())}%` : 'Belum ada pembayaran',
        keadaan: lunas ? 'selesai' : 'nanti' },
    ];
  });

  // dialog pembayaran
  readonly dialogBayar = signal(false);
  readonly galat = signal('');
  readonly proses = signal(false);
  jumlah = 0;
  metode = 'Transfer Bank';
  referensi = '';
  tanggal = new Date();

  ngOnChanges(): void {
    this.muat();
  }

  async muat(): Promise<void> {
    this.f.set(await this.api.get<DetailFaktur>(`/faktur/${this.id()}`));
  }

  bukaBayar(): void {
    const f = this.f()!;
    this.jumlah = Math.round(f.sisa);
    this.referensi = '';
    this.galat.set('');
    this.tanggal = new Date(this.auth.meta()!.periode.akhir + 'T00:00:00');
    this.dialogBayar.set(true);
  }

  async bayar(): Promise<void> {
    const f = this.f()!;
    this.proses.set(true);
    this.galat.set('');
    const t = this.tanggal;
    try {
      await this.api.post('/pembayaran', {
        customer_id: f.customer_id, faktur_id: f.id, jumlah: this.jumlah, metode: this.metode, referensi: this.referensi,
        tanggal: `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`,
      });
      this.dialogBayar.set(false);
      this.pesan.add({ severity: 'success', summary: 'Pembayaran tercatat', detail: f.nomor, life: 4000 });
      await this.muat();
    } catch (e) {
      this.galat.set(pesanGalat(e));
    } finally {
      this.proses.set(false);
    }
  }

  minTanggal(): Date {
    return new Date(this.auth.meta()!.periode.awal + 'T00:00:00');
  }

  maxTanggal(): Date {
    return new Date(this.auth.meta()!.periode.akhir + 'T00:00:00');
  }
}
