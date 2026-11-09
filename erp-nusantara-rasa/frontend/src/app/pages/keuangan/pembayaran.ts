import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { Halaman } from '../../core/model';
import { PIPES } from '../../core/pipes';
import { DaftarServer } from '../../shared/daftar';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisBayar {
  id: number;
  tanggal: string;
  jumlah: number;
  metode: string;
  referensi: string;
  dicatat_oleh: string;
  faktur_id: number;
  nomor_faktur: string;
  customer_id: number;
  customer: string;
}
interface Terbuka { id: number; nomor: string; tanggal: string; jatuh_tempo: string; total: number; terbayar: number; sisa: number; hari: number }

@Component({
  selector: 'app-pembayaran',
  imports: [FormsModule, RouterLink, TableModule, DialogModule, SelectModule, InputNumberModule, DatePickerModule, ...UI, ...PIPES],
  templateUrl: './pembayaran.html',
})
export class Pembayaran implements OnInit {
  private api = inject(Api);
  private pesan = inject(MessageService);
  private route = inject(ActivatedRoute);
  readonly auth = inject(Auth);
  readonly d = new DaftarServer<BarisBayar>(this.api, '/pembayaran');
  q = '';
  metodeFilter: string | null = null;
  readonly bulanIni = computed(() => this.d.ekstra()['bulan_ini'] as { jumlah: number; n: number } | undefined);

  // form
  readonly dialog = signal(false);
  readonly customer = signal<{ id: number; nama: string; kode: string; piutang: number | null }[]>([]);
  readonly terbuka = signal<Terbuka[]>([]);
  readonly galat = signal('');
  readonly proses = signal(false);
  readonly hasil = signal<{ jumlah: number; alokasi: { nomor: string; jumlah: number; lunas: boolean }[] } | null>(null);
  customerId: number | null = null;
  jumlah = 0;
  metode = 'Transfer Bank';
  referensi = '';
  tanggal = new Date();
  readonly jumlahSig = signal(0);

  readonly alokasi = computed(() => {
    let sisa = this.jumlahSig();
    return this.terbuka().map((f) => {
      const bayar = Math.max(0, Math.min(sisa, f.sisa));
      sisa -= bayar;
      return { ...f, bayar, lunas: bayar > 0 && bayar >= f.sisa - 0.5 };
    });
  });
  readonly totalSisa = computed(() => this.terbuka().reduce((a, f) => a + f.sisa, 0));

  async ngOnInit(): Promise<void> {
    const q = this.route.snapshot.queryParamMap;
    if (this.auth.punya('pembayaran_catat') && (q.get('catat') || q.get('customer'))) {
      await this.buka(Number(q.get('customer')) || null);
    }
  }

  async buka(customerId: number | null = null): Promise<void> {
    this.galat.set('');
    this.hasil.set(null);
    this.referensi = '';
    this.tanggal = new Date(this.auth.meta()!.periode.akhir + 'T00:00:00');
    if (!this.customer().length) {
      const c = await this.api.get<Halaman<{ id: number; nama: string; kode: string; piutang: number | null }>>('/customer',
        { size: 100, sort: '-piutang' });
      this.customer.set(c.data.filter((x) => (x.piutang ?? 0) > 0));
    }
    this.dialog.set(true);
    await this.pilihCustomer(customerId);
  }

  async pilihCustomer(id: number | null): Promise<void> {
    this.customerId = id;
    this.terbuka.set([]);
    this.setJumlah(0);
    if (!id) return;
    const d = await this.api.get<{ data: Terbuka[]; total_sisa: number }>('/piutang/terbuka', { customer_id: id });
    this.terbuka.set(d.data);
  }

  setJumlah(v: number | null): void {
    this.jumlah = v ?? 0;
    this.jumlahSig.set(this.jumlah);
  }

  async simpan(): Promise<void> {
    this.proses.set(true);
    this.galat.set('');
    const t = this.tanggal;
    try {
      const r = await this.api.post<{ jumlah: number; alokasi: { nomor: string; jumlah: number; lunas: boolean }[] }>('/pembayaran', {
        customer_id: this.customerId, jumlah: this.jumlah, metode: this.metode, referensi: this.referensi,
        tanggal: `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`,
      });
      this.hasil.set(r);
      this.pesan.add({ severity: 'success', summary: 'Pembayaran tercatat', detail: `${r.alokasi.length} faktur dialokasikan`, life: 4000 });
      this.d.segarkan();
      this.customer.set([]);
    } catch (e) {
      this.galat.set(pesanGalat(e));
    } finally {
      this.proses.set(false);
    }
  }

  async ekspor(): Promise<void> {
    unduhCsv<BarisBayar>('penerimaan-pembayaran', [
      { label: 'Tanggal', nilai: (r) => r.tanggal }, { label: 'Customer', nilai: (r) => r.customer }, { label: 'Faktur', nilai: (r) => r.nomor_faktur },
      { label: 'Metode', nilai: (r) => r.metode }, { label: 'Referensi', nilai: (r) => r.referensi }, { label: 'Jumlah', nilai: (r) => r.jumlah },
      { label: 'Dicatat oleh', nilai: (r) => r.dicatat_oleh },
    ], await this.d.semua());
  }

  minTanggal(): Date {
    return new Date(this.auth.meta()!.periode.awal + 'T00:00:00');
  }

  maxTanggal(): Date {
    return new Date(this.auth.meta()!.periode.akhir + 'T00:00:00');
  }
}
