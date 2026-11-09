import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { Api, pesanGalat } from '../core/api';
import { Auth } from '../core/auth';
import { DraftSO, HasilSO, SimulasiSO } from '../core/model';
import { PIPES } from '../core/pipes';
import { UI } from '../shared/ui';
import { Asisten } from './asisten';

type Keadaan = 'draft' | 'tersimpan' | 'form' | 'batal';

interface BarisDraft {
  produk_id: number;
  nama: string;
  satuan: string;
  qty: number;
  harga: number;
  diskon: number | null;
  subtotal: number | null;
  tersedia: number | null;   // null = stok tidak tercatat
  kurang: boolean;
}

/**
 * Kartu draft sales order dari tool asisten `siapkan_draft_so`.
 * AI hanya mengisi draft. Angka di kartu ini berasal dari simulasi ERP (/sales-order/simulasi, tanpa menyimpan),
 * dan menyimpan = user menekan "Simpan sales order": browser memanggil POST /sales-order dengan sesi & izin user sendiri.
 */
@Component({
  selector: 'app-kartu-draft-so',
  imports: [RouterLink, ...UI, ...PIPES],
  template: `
    @let d = draft();
    <section class="ai-draft" [class.ringkas]="ringkas()">
      <header class="ai-draft-kepala">
        <app-ikon n="so" [ukuran]="15" />
        <b>Draft sales order</b>
        @switch (keadaan()) {
          @case ('tersimpan') { <app-status [nilai]="hasil()!.status" /> }
          @case ('batal') { <span class="badge">Dibatalkan</span> }
          @case ('form') { <span class="badge b-garis">Dilanjutkan di form</span> }
          @default { <span class="badge b-garis">Belum disimpan</span> }
        }
      </header>

      @if (keadaan() === 'batal') {
        <p class="ai-draft-catatan">{{ d.customer.nama }} · draft dibatalkan, tidak ada data yang disimpan.</p>
      } @else if (ringkas()) {
        <p class="ai-draft-catatan">{{ d.customer.nama }} · diganti draft yang lebih baru di bawah.</p>
      } @else {
        <div class="ai-draft-bagian">
          <div class="ai-draft-customer">
            <b>{{ d.customer.nama }}</b>
            <small>{{ d.customer.kode }} · {{ d.customer.segmen }} · {{ d.customer.kota }} · termin {{ d.customer.termin_hari }} hari</small>
          </div>
          <div class="daftar-info ai-draft-info">
            <div><span>Gudang</span><span>{{ d.gudang }}@if (d.gudang_otomatis) { <small>dipilih otomatis sesuai kota customer</small> }</span></div>
            <div><span>Tanggal</span><span>{{ tanggal() | tgl }}</span></div>
            <div><span>Diskon</span><span>{{ diskonStandar() | angka: 1 }}% standar{{ d.diskon_tambahan ? ' + ' + (d.diskon_tambahan | angka: 1) + '% tambahan' : '' }}</span></div>
            @if (d.catatan) { <div><span>Catatan</span><span>{{ d.catatan }}</span></div> }
          </div>
        </div>

        <ul class="ai-draft-bagian ai-draft-item">
          @for (b of baris(); track b.produk_id) {
            <li>
              <div>
                <b>{{ b.nama }}</b>
                <small><span [class.t-bahaya]="b.kurang">{{ b.qty | angka }} {{ b.satuan }}</span> × {{ b.harga | rupiah }}@if (b.diskon !== null) { · diskon {{ b.diskon | angka: 1 }}% }</small>
                @if (b.kurang) { <small class="t-bahaya">Stok {{ d.gudang }} {{ b.tersedia | angka }} {{ b.satuan }}</small> }
              </div>
              <span>{{ b.subtotal === null ? '–' : (b.subtotal | rupiah) }}</span>
            </li>
          }
        </ul>

        <div class="ai-draft-bagian ai-draft-total">
          <div><span>Subtotal sebelum diskon</span><b>{{ bruto() | rupiah }}</b></div>
          @if (sim()?.hitungan; as h) {
            <div><span>Diskon</span><b>−{{ bruto() - h.total | rupiah }}</b></div>
            <div class="besar"><span>Total</span><b>{{ h.total | rupiah }}</b></div>
          } @else {
            <div class="besar"><span>Total</span><b>–</b></div>
          }
        </div>

        <div class="ai-draft-bagian">
          @if (!bolehBuat()) {
            <ul class="cek-list"><li class="cek-warn"><app-ikon n="kunci" /><div><b>Tidak dapat dihitung</b>
              <small>Akun Anda tidak memiliki izin Membuat sales order, jadi harga final, kredit, dan persetujuan tidak dihitung.</small></div></li></ul>
          } @else if (galatSim()) {
            <div class="galat-form"><app-ikon n="galat" [ukuran]="15" /> {{ galatSim() }}</div>
          } @else if (sim(); as s) {
            @if (perkiraan(); as pk) {
              <div [class]="'status-perkiraan ' + pk.kelas"><app-ikon [n]="pk.ikon" />{{ pk.judul }}</div>
            }
            <ul class="cek-list">
              @if (galat()) { <li class="cek-galat"><app-ikon n="galat" /><div><b>Belum dapat disimpan</b><small>{{ galat() }}</small></div></li> }
              @for (p of s.persetujuan; track p.jenis) {
                <li class="cek-warn"><app-ikon n="setuju" /><div><b>{{ p.judul }} · {{ p.peran }}</b><small>{{ p.alasan }}</small></div></li>
              }
              @for (w of s.peringatan; track w) { <li class="cek-info"><app-ikon n="info" /><div><small>{{ w }}</small></div></li> }
              @if (s.hitungan && !galat() && !s.persetujuan.length) {
                <li class="cek-ok"><app-ikon n="ok" /><div><b>Limit, tunggakan, diskon, dan stok aman</b></div></li>
              }
              <li class="cek-kredit"><app-ikon n="piutang" /><div><b>Kredit {{ s.kredit.pemakaian_persen | angka: 0 }}% terpakai</b>
                <small>Piutang {{ s.kredit.piutang | rupiah: true }} dari limit {{ s.kredit.limit_kredit | rupiah: true }} · tunggakan terlama {{ s.kredit.hari_lewat_maks }} hari</small></div></li>
            </ul>
          } @else {
            <div class="ai-fase"><span class="ai-loader"><i></i><i></i><i></i></span>Menghitung harga & memeriksa aturan di sistem ERP…</div>
          }
        </div>

        <footer class="ai-draft-kaki">
          @switch (keadaan()) {
            @case ('tersimpan') {
              @let h = hasil()!;
              <div class="ai-draft-hasil" [class.kuning]="!h.faktur">
                <app-ikon [n]="h.faktur ? 'ok' : 'jeda'" />
                <div><b><span class="mono">{{ h.nomor }}</span> tersimpan</b>
                  <small>{{ h.faktur ? 'Faktur ' + h.faktur.nomor + ' diterbitkan' : h.status + ' · menunggu ' + peran(h) }} · disimpan oleh {{ auth.user()?.nama }}</small></div>
                <a class="tautan-aksi" [routerLink]="'/penjualan/sales-order/' + h.id">Buka<app-ikon n="kanan" /></a>
              </div>
            }
            @case ('form') {
              <p class="ai-draft-catatan"><app-ikon n="info" [ukuran]="14" />Draft dipindahkan ke form Sales order baru. Simpan dari form setelah diperiksa.</p>
              <div class="ai-draft-aksi"><button class="btn" (click)="ubahDiForm()"><app-ikon n="edit" />Buka form lagi</button></div>
            }
            @default {
              @if (aksi()) {
                <p class="ai-draft-catatan"><app-ikon n="info" [ukuran]="14" />
                  {{ bolehBuat() ? 'Draft ini belum tersimpan. Harga, diskon, kredit, dan status di atas dihitung sistem ERP, bukan oleh AI.'
                                 : 'Draft ini belum tersimpan. Menyimpan sales order membutuhkan izin Membuat sales order (Pengaturan › Pengguna & Hak Akses).' }}</p>
                @if (galatSimpan()) { <div class="galat-form"><app-ikon n="galat" [ukuran]="15" /> {{ galatSimpan() }}</div> }
                <div class="ai-draft-aksi">
                  <button class="btn-utama" (click)="simpan()" [disabled]="!bisaSimpan()">{{ menyimpan() ? 'Menyimpan…' : 'Simpan sales order' }}</button>
                  <button class="btn" (click)="ubahDiForm()" [disabled]="!bolehBuat() || menyimpan()">Ubah di form</button>
                  <button class="btn-hantu" (click)="keadaan.set('batal')" [disabled]="menyimpan()">Batal</button>
                </div>
              } @else {
                <p class="ai-draft-catatan"><app-ikon n="info" [ukuran]="14" />Mode bandingkan: draft hanya ditampilkan, tidak dapat disimpan dari sini.</p>
              }
            }
          }
        </footer>
      }
    </section>`,
})
export class KartuDraftSO {
  readonly draft = input.required<DraftSO>();
  /** false di mode bandingkan lokal vs cloud: kartu hanya tampil. */
  readonly aksi = input(true);
  /** Draft lama dalam pesan yang sama (agent menyiapkan ulang) diringkas supaya tidak tersimpan dua kali. */
  readonly terbaru = input(true);

  private api = inject(Api);
  private router = inject(Router);
  private pesan = inject(MessageService);
  private ai = inject(Asisten);
  readonly auth = inject(Auth);

  readonly sim = signal<SimulasiSO | null>(null);
  readonly menghitung = signal(false);
  readonly galatSim = signal('');
  readonly menyimpan = signal(false);
  readonly galatSimpan = signal('');
  readonly hasil = signal<HasilSO | null>(null);
  readonly keadaan = signal<Keadaan>('draft');

  readonly bolehBuat = computed(() => this.auth.punya('so_buat'));
  readonly tanggal = computed(() => this.auth.meta()?.tanggal_sistem ?? '');
  readonly ringkas = computed(() => !this.terbaru() && this.keadaan() === 'draft');
  readonly diskonStandar = computed(() =>
    this.sim()?.hitungan?.diskon_standar ?? this.auth.meta()?.segmen.find((s) => s.nama === this.draft().customer.segmen)?.diskon ?? 0);

  /** Angka sistem bila simulasi berhasil; bila belum/gagal, harga daftar dari draft (tanpa subtotal). */
  readonly baris = computed<BarisDraft[]>(() => {
    const d = this.draft();
    const s = this.sim();
    const stok = (id: number, cadangan: number | null) => (s ? (s.stok[String(id)] ?? 0) : cadangan);
    const baris = (b: Omit<BarisDraft, 'kurang'>): BarisDraft => ({ ...b, kurang: b.tersedia !== null && b.qty > b.tersedia });
    if (s?.hitungan) {
      return s.hitungan.item.map((i) => baris({ produk_id: i.produk_id, nama: i.nama, satuan: i.satuan, qty: i.qty, harga: i.harga,
        diskon: i.diskon_persen, subtotal: i.subtotal, tersedia: stok(i.produk_id, null) }));
    }
    return d.item.map((i) => baris({ produk_id: i.produk_id, nama: i.nama, satuan: i.satuan, qty: i.qty, harga: i.harga_daftar,
      diskon: null, subtotal: null, tersedia: stok(i.produk_id, i.stok_gudang) }));
  });

  readonly bruto = computed(() => {
    const h = this.sim()?.hitungan;
    return h ? h.item.reduce((a, i) => a + i.qty * i.harga, 0) : this.draft().nilai_bruto;
  });

  readonly galat = computed(() => {
    const s = this.sim();
    return s ? (s.galat ?? (s.hitungan ? null : 'Draft belum berisi produk.')) : null;
  });

  /** Status sales order bila disimpan sekarang (dari aturan ERP, bukan perkiraan AI). */
  readonly perkiraan = computed(() => {
    const s = this.sim();
    if (!s) return null;
    if (this.galat()) return { kelas: 'merah', ikon: 'gagal', judul: 'Belum dapat disimpan' };
    if (s.status === 'Faktur Terbit') return { kelas: 'hijau', ikon: 'ok', judul: 'Faktur langsung terbit saat disimpan' };
    if (s.status === 'Ditahan') {
      const alasan = s.persetujuan.filter((p) => p.jenis === 'credit_hold' || p.jenis === 'limit_kredit').map((p) => p.judul.toLowerCase());
      return { kelas: 'merah', ikon: 'jeda', judul: `Ditahan: ${alasan.join(', ')}` };
    }
    return { kelas: 'kuning', ikon: 'jeda', judul: `Menunggu persetujuan ${s.persetujuan.map((p) => p.peran).join(', ')}` };
  });

  readonly bisaSimpan = computed(() =>
    this.bolehBuat() && !!this.sim()?.hitungan && !this.galat() && !this.menghitung() && !this.menyimpan()
    && this.keadaan() === 'draft' && !this.ringkas());

  constructor() {
    effect(() => {
      const d = this.draft();
      if (this.bolehBuat()) untracked(() => this.simulasikan(d));
    });
  }

  async simulasikan(d = this.draft()): Promise<void> {
    this.galatSim.set('');
    this.menghitung.set(true);
    try {
      this.sim.set(await this.api.post<SimulasiSO>('/sales-order/simulasi', { ...d.payload, tanggal: this.tanggal() }));
    } catch (e) {
      this.sim.set(null);
      this.galatSim.set(pesanGalat(e));
    } finally {
      this.menghitung.set(false);
    }
  }

  async simpan(): Promise<void> {
    if (!this.bisaSimpan()) return;
    this.galatSimpan.set('');
    this.menyimpan.set(true);
    try {
      const r = await this.api.post<HasilSO>('/sales-order', { ...this.draft().payload, tanggal: this.tanggal(), sumber: 'asisten_ai' });
      this.hasil.set(r);
      this.keadaan.set('tersimpan');
      this.pesan.add({
        severity: r.faktur ? 'success' : 'warn', summary: r.nomor + ' tersimpan',
        detail: r.faktur ? `Faktur ${r.faktur.nomor} diterbitkan.` : `Status: ${r.status}. Menunggu ${this.peran(r)}.`, life: 5000,
      });
    } catch (e) {
      this.galatSimpan.set(pesanGalat(e));
      this.simulasikan();   // data bisa berubah sejak draft dibuat (mis. stok terpakai SO lain): hitung ulang
    } finally {
      this.menyimpan.set(false);
    }
  }

  /** Lanjutkan di form "Sales order baru" dengan isian draft ini. */
  ubahDiForm(): void {
    this.ai.draftForm.set(this.draft().payload);
    this.keadaan.set('form');
    this.router.navigate(['/penjualan/sales-order/baru']);
  }

  peran(h: HasilSO): string {
    return h.persetujuan.filter((p) => p.status === 'menunggu').map((p) => p.peran).join(', ');
  }
}
