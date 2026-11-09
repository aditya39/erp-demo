import { Component, computed, inject, input, OnChanges, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { Asisten } from '../../ai/asisten';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { ItemBaris, Kredit, Peristiwa, Persetujuan, Tahap } from '../../core/model';
import { tanggal } from '../../core/format';
import { PIPES } from '../../core/pipes';
import { Riwayat, Tahapan } from '../../shared/dokumen';
import { UI } from '../../shared/ui';

interface DetailSO {
  id: number;
  nomor: string;
  tanggal: string;
  status: string;
  gudang: string;
  diskon_tambahan: number;
  diskon_standar: number;
  catatan: string;
  total: number;
  persetujuan: Persetujuan[];
  faktur_id: number | null;
  nomor_faktur: string | null;
  dibuat_oleh: string;
  dibuat_oleh_nama: string;
  dibuat_pada: string;
  sumber: 'manual' | 'asisten_ai';
  customer_id: number;
  customer: string;
  kode_customer: string;
  segmen: string;
  kota: string;
  alamat: string;
  termin_hari: number;
  item: ItemBaris[];
  kredit: Kredit;
  bisa_batal: boolean;
  riwayat: Peristiwa[];
  faktur: { id: number; nomor: string; tanggal: string; jatuh_tempo: string; total: number; terbayar: number; sisa: number; status: string } | null;
}

@Component({
  selector: 'app-so-detail',
  imports: [FormsModule, RouterLink, DialogModule, Tahapan, Riwayat, ...UI, ...PIPES],
  templateUrl: './so-detail.html',
})
export class SoDetail implements OnChanges {
  readonly id = input.required<string>();
  private api = inject(Api);
  private pesan = inject(MessageService);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly so = signal<DetailSO | null>(null);
  readonly proses = signal('');
  readonly dialog = signal<{ jenis: string; setuju: boolean; judul: string } | null>(null);
  readonly dialogBatal = signal(false);
  catatan = '';
  readonly galat = signal('');

  readonly bruto = computed(() => (this.so()?.item ?? []).reduce((a, i) => a + i.qty * i.harga, 0));
  readonly menunggu = computed(() => ['Ditahan', 'Menunggu Persetujuan'].includes(this.so()?.status ?? ''));
  readonly untukSaya = computed(() => (this.so()?.persetujuan ?? []).filter((p) => p.bisa_saya));

  readonly tahapan = computed<Tahap[]>(() => {
    const s = this.so();
    if (!s) return [];
    const p = s.persetujuan;
    const ditolak = p.find((x) => x.status === 'ditolak');
    const tunggu = p.filter((x) => x.status === 'menunggu');
    const batal = s.status === 'Dibatalkan';
    const tPersetujuan: Tahap = batal ? { label: 'Persetujuan', ket: 'Dibatalkan', keadaan: 'gagal' }
      : ditolak ? { label: 'Persetujuan', ket: `Ditolak ${ditolak.oleh ?? ''}`, keadaan: 'gagal' }
      : !p.length ? { label: 'Persetujuan', ket: 'Tidak diperlukan', keadaan: 'selesai' }
      : tunggu.length ? { label: 'Persetujuan', ket: `Menunggu ${tunggu.map((x) => x.peran).join(', ')}`, keadaan: 'aktif' }
      : { label: 'Persetujuan', ket: `${p.length} disetujui`, keadaan: 'selesai' };
    const f = s.faktur;
    return [
      { label: 'Dibuat', ket: `${tanggal(s.tanggal)} · ${s.dibuat_oleh_nama}`, keadaan: 'selesai' },
      tPersetujuan,
      f ? { label: 'Faktur terbit', ket: f.nomor, keadaan: 'selesai' } : { label: 'Faktur terbit', ket: batal || ditolak ? '—' : 'Setelah disetujui', keadaan: 'nanti' },
      f?.status === 'Lunas' ? { label: 'Lunas', ket: 'Pembayaran lengkap', keadaan: 'selesai' }
        : f ? { label: 'Lunas', ket: `Jatuh tempo ${tanggal(f.jatuh_tempo)}`, keadaan: f.status === 'Jatuh Tempo' ? 'gagal' : 'aktif' }
        : { label: 'Lunas', ket: '—', keadaan: 'nanti' },
    ];
  });

  ngOnChanges(): void {
    this.muat();
  }

  async muat(): Promise<void> {
    this.so.set(await this.api.get<DetailSO>(`/sales-order/${this.id()}`));
  }

  buka(p: Persetujuan, setuju: boolean): void {
    this.catatan = '';
    this.galat.set('');
    this.dialog.set({ jenis: p.jenis, setuju, judul: `${setuju ? 'Setujui' : 'Tolak'}: ${p.judul}` });
  }

  async putuskan(): Promise<void> {
    const d = this.dialog();
    if (!d) return;
    this.proses.set(d.jenis);
    try {
      const r = await this.api.post<{ status: string; faktur: { nomor: string } | null }>(`/sales-order/${this.id()}/keputusan`,
        { jenis: d.jenis, setuju: d.setuju, catatan: this.catatan });
      this.dialog.set(null);
      this.pesan.add({
        severity: d.setuju ? 'success' : 'warn', summary: d.setuju ? 'Disetujui' : 'Ditolak',
        detail: r.faktur ? `Semua persetujuan lengkap · faktur ${r.faktur.nomor} diterbitkan.` : `Status sales order: ${r.status}.`, life: 5000,
      });
      await this.muat();
    } catch (e) {
      this.galat.set(pesanGalat(e));
    } finally {
      this.proses.set('');
    }
  }

  async batal(): Promise<void> {
    try {
      await this.api.post(`/sales-order/${this.id()}/batal`, { alasan: this.catatan });
      this.dialogBatal.set(false);
      this.pesan.add({ severity: 'info', summary: 'Sales order dibatalkan', life: 4000 });
      await this.muat();
    } catch (e) {
      this.galat.set(pesanGalat(e));
    }
  }

  tanyaKebijakan(p: Persetujuan): void {
    const q: Record<string, string> = {
      credit_hold: 'Apa kebijakan perusahaan untuk customer yang fakturnya lewat jatuh tempo lebih dari 60 hari? Siapa yang memutuskan?',
      limit_kredit: 'Apa yang terjadi jika sales order melebihi limit kredit customer dan siapa yang menyetujuinya?',
      diskon: 'Siapa yang berwenang menyetujui diskon tambahan 2% dan apa syaratnya?',
    };
    this.ai.tanya(q[p.jenis] ?? `Jelaskan kebijakan terkait: ${p.judul}`);
  }
}
