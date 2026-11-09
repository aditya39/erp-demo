import { Component, computed, effect, inject, OnInit, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { DatePickerModule } from 'primeng/datepicker';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectModule } from 'primeng/select';
import { Asisten } from '../../ai/asisten';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { Halaman, PayloadSO, SimulasiSO } from '../../core/model';
import { PIPES } from '../../core/pipes';
import { TitikDesimal } from '../../shared/desimal';
import { UI } from '../../shared/ui';

interface OpsiCustomer { id: number; kode: string; nama: string; segmen: string; kota: string; termin_hari: number }
interface OpsiProduk { id: number; kode: string; nama: string; satuan: string; harga_jual: number; kategori: string }

function isoTanggal(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

@Component({
  selector: 'app-so-form',
  imports: [FormsModule, RouterLink, SelectModule, DatePickerModule, InputNumberModule, TitikDesimal, ...UI, ...PIPES],
  templateUrl: './so-form.html',
})
export class SoForm implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private pesan = inject(MessageService);
  private ai = inject(Asisten);
  readonly auth = inject(Auth);

  readonly customer = signal<OpsiCustomer[]>([]);
  readonly produk = signal<OpsiProduk[]>([]);
  readonly sim = signal<SimulasiSO | null>(null);
  /** 'asisten_ai' bila isian berasal dari draft Asisten AI (tombol "Ubah di form" di panel Asisten). */
  readonly sumber = signal<'manual' | 'asisten_ai'>('manual');
  readonly menyimpan = signal(false);
  readonly galat = signal('');

  customerId: number | null = null;
  tanggal = new Date();
  gudang = 'Gudang Jakarta';
  diskonTambahan = 0;
  catatan = '';
  barisItem: { produk_id: number | null; qty: number }[] = [{ produk_id: null, qty: 100 }];
  private tunda?: ReturnType<typeof setTimeout>;

  readonly minTanggal = computed(() => new Date(this.auth.meta()!.periode.awal + 'T00:00:00'));
  readonly maxTanggal = computed(() => new Date(this.auth.meta()!.periode.akhir + 'T00:00:00'));
  readonly cust = computed(() => this.customer().find((c) => c.id === this.customerIdSig()) ?? null);
  private customerIdSig = signal<number | null>(null);

  constructor() {
    // draft dari Asisten AI diterapkan setelah daftar customer & produk termuat (juga bila form sudah terbuka)
    effect(() => {
      const d = this.ai.draftForm();
      if (!d || !this.produk().length) return;
      untracked(() => this.terapkanDraft(d));
      this.ai.draftForm.set(null);
    });
  }

  private terapkanDraft(d: PayloadSO): void {
    this.pilihCustomer(d.customer_id);
    this.gudang = d.gudang;
    this.diskonTambahan = d.diskon_tambahan ?? 0;
    this.catatan = d.catatan ?? '';
    this.barisItem = d.item.length ? d.item.map((x) => ({ produk_id: x.produk_id, qty: x.qty })) : [{ produk_id: null, qty: 100 }];
    this.sumber.set('asisten_ai');
    this.ubah();
  }

  async ngOnInit(): Promise<void> {
    this.tanggal = this.maxTanggal();
    const [c, p] = await Promise.all([
      this.api.get<Halaman<OpsiCustomer>>('/customer', { size: 100, sort: 'nama' }),
      this.api.get<{ data: OpsiProduk[] }>('/produk'),
    ]);
    this.customer.set(c.data);
    this.produk.set(p.data.filter((x) => (x as unknown as { aktif: boolean }).aktif !== false));
    const awal = Number(this.route.snapshot.queryParamMap.get('customer'));
    if (awal) this.pilihCustomer(awal);
  }

  pilihCustomer(id: number | null): void {
    this.customerId = id;
    this.customerIdSig.set(id);
    const c = this.customer().find((x) => x.id === id);
    if (c) this.gudang = ['Surabaya', 'Denpasar', 'Makassar'].includes(c.kota) ? 'Gudang Surabaya' : 'Gudang Jakarta';
    this.ubah();
  }

  tambahBaris(): void {
    this.barisItem.push({ produk_id: null, qty: 100 });
  }

  hapusBaris(i: number): void {
    this.barisItem.splice(i, 1);
    if (!this.barisItem.length) this.tambahBaris();
    this.ubah();
  }

  produkDipakai(i: number): (number | null)[] {
    return this.barisItem.filter((_, j) => j !== i).map((x) => x.produk_id);
  }

  opsiProduk(i: number): OpsiProduk[] {
    const dipakai = this.produkDipakai(i);
    return this.produk().filter((p) => !dipakai.includes(p.id));
  }

  infoProduk(id: number | null): OpsiProduk | undefined {
    return this.produk().find((p) => p.id === id);
  }

  stok(id: number | null): number | null {
    return id ? (this.sim()?.stok[String(id)] ?? null) : null;
  }

  subtotal(id: number | null): number | null {
    return this.sim()?.hitungan?.item.find((x) => x.produk_id === id)?.subtotal ?? null;
  }

  private payload() {
    return {
      customer_id: this.customerId, tanggal: isoTanggal(this.tanggal), gudang: this.gudang,
      diskon_tambahan: this.diskonTambahan ?? 0, catatan: this.catatan,
      item: this.barisItem.filter((x) => x.produk_id && x.qty > 0).map((x) => ({ produk_id: x.produk_id, qty: x.qty })),
      sumber: this.sumber(),
    };
  }

  ubah(): void {
    clearTimeout(this.tunda);
    this.tunda = setTimeout(async () => {
      if (!this.customerId) {
        this.sim.set(null);
        return;
      }
      try {
        this.sim.set(await this.api.post<SimulasiSO>('/sales-order/simulasi', this.payload()));
      } catch {
        /* galat ditampilkan saat simpan */
      }
    }, 220);
  }

  readonly bruto = computed(() => {
    const h = this.sim()?.hitungan;
    return h ? h.item.reduce((a, x) => a + x.subtotal / (1 - x.diskon_persen / 100), 0) : 0;
  });

  readonly perkiraan = computed(() => {
    const s = this.sim();
    if (!s?.hitungan) return null;
    if (s.galat) return { kelas: 'merah', ikon: 'gagal', judul: 'Belum dapat disimpan' };
    if (s.status === 'Faktur Terbit') return { kelas: 'hijau', ikon: 'ok', judul: 'Lolos semua pemeriksaan' };
    return { kelas: s.status === 'Ditahan' ? 'merah' : 'kuning', ikon: 'jeda', judul: `Akan berstatus ${s.status}` };
  });

  readonly bisaSimpan = computed(() => {
    const s = this.sim();
    return !!s?.hitungan && !s.galat && !this.menyimpan();
  });

  /** Ada isian yang belum disimpan? (dipakai guard saat meninggalkan halaman) */
  adaPerubahan(): boolean {
    return !this.tersimpan && (!!this.customerId || this.barisItem.some((x) => x.produk_id));
  }
  private tersimpan = false;

  async simpan(): Promise<void> {
    this.galat.set('');
    this.menyimpan.set(true);
    try {
      const r = await this.api.post<{ id: number; nomor: string; status: string; faktur: { nomor: string } | null }>('/sales-order', this.payload());
      this.tersimpan = true;
      this.pesan.add({
        severity: r.faktur ? 'success' : 'warn', summary: r.nomor + ' tersimpan',
        detail: r.faktur ? `Faktur ${r.faktur.nomor} diterbitkan.` : `Status: ${r.status}. Menunggu persetujuan.`, life: 5000,
      });
      this.router.navigate(['/penjualan/sales-order', r.id]);
    } catch (e) {
      this.galat.set(pesanGalat(e));
    } finally {
      this.menyimpan.set(false);
    }
  }
}
