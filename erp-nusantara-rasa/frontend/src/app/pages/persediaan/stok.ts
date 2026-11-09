import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectModule } from 'primeng/select';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { unduhCsv } from '../../shared/ekspor';
import { UI } from '../../shared/ui';

interface BarisStok {
  produk_id: number;
  kode: string;
  nama: string;
  kategori: string;
  satuan: string;
  gudang: string;
  qty: number;
  stok_minimum: number;
  status: string;
  nilai_stok: number | null;
  rata_jual_harian: number;
  hari_cukup: number | null;
  mutasi_terakhir: string | null;
}

@Component({
  selector: 'app-stok',
  imports: [FormsModule, RouterLink, SelectModule, DialogModule, InputNumberModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Stok gudang" [jejak]="[{ label: 'Persediaan' }, { label: 'Stok gudang' }]">
      <ng-container meta><span>Barang jadi per gudang · posisi {{ auth.meta()?.tanggal_sistem | tgl }}</span></ng-container>
      <button class="btn" (click)="ekspor()"><app-ikon n="unduh" />Ekspor</button>
      <a class="btn" routerLink="/persediaan/mutasi"><app-ikon n="mutasi" />Mutasi stok</a>
    </app-judul>

    <div class="statistik">
      <div class="stat"><span class="stat-label">Total qty</span><span class="stat-nilai">{{ ringkas()?.qty | angka }}</span><span class="stat-ket">{{ ringkas()?.baris }} produk × gudang</span></div>
      <div class="stat klik" (click)="menipis = !menipis; muat()" [class.pilih]="menipis">
        <span class="stat-label">Di bawah minimum</span><span class="stat-nilai" [class.t-bahaya]="ringkas()?.menipis">{{ ringkas()?.menipis | angka }}</span>
        <span class="stat-ket">{{ menipis ? 'filter aktif' : 'klik untuk filter' }}</span></div>
      @if (ringkas()?.nilai !== null) {
        <div class="stat"><span class="stat-label">Nilai persediaan</span><span class="stat-nilai">{{ ringkas()?.nilai | rupiah: true }}</span><span class="stat-ket">dinilai dengan HPP bulan berjalan</span></div>
      }
    </div>

    <section class="panel">
      <div class="alat">
        <div class="cari-kecil"><app-ikon n="cari" /><input [(ngModel)]="q" (ngModelChange)="tunda()" placeholder="Cari produk" /></div>
        <div class="segmen">
          <button [class.aktif]="!gudang" (click)="gudang = ''; muat()">Semua gudang</button>
          @for (g of auth.meta()!.gudang; track g) { <button [class.aktif]="gudang === g" (click)="gudang = g; muat()">{{ g.replace('Gudang ', '') }}</button> }
        </div>
        <span class="spacer"></span><span class="ringkas-tabel"><b>{{ data().length }}</b> baris</span>
      </div>
      <table class="tabel">
        <thead><tr><th>Produk</th><th>Gudang</th><th class="r">Qty</th><th class="r">Minimum</th><th style="width: 13%">Level</th><th class="r">Rata jual/hari</th><th class="r">Cukup untuk</th>
          @if (ringkas()?.nilai !== null) { <th class="r">Nilai</th> }<th>Status</th>@if (auth.punya('stok_sesuaikan')) { <th></th> }</tr></thead>
        <tbody>
          @for (s of data(); track s.produk_id + s.gudang) {
            <tr>
              <td><div class="sel-utama"><a [routerLink]="'/produksi/produk/' + s.produk_id">{{ s.nama }}</a><small>{{ s.kode }} · {{ s.kategori }}</small></div></td>
              <td class="redup nowrap">{{ s.gudang.replace('Gudang ', '') }}</td>
              <td class="r tebal">{{ s.qty | angka }} <span class="samar">{{ s.satuan }}</span></td>
              <td class="r redup">{{ s.stok_minimum | angka }}</td>
              <td><div class="meter" [class.bahaya]="s.status !== 'Aman'"><i [style.width.%]="level(s)"></i></div></td>
              <td class="r redup">{{ s.rata_jual_harian | angka: 0 }}</td>
              <td class="r nowrap" [class.t-bahaya]="(s.hari_cukup ?? 99) < 7">{{ s.hari_cukup === null ? '–' : (s.hari_cukup | angka: 1) + ' hari' }}</td>
              @if (ringkas()?.nilai !== null) { <td class="r">{{ s.nilai_stok | rupiah: true }}</td> }
              <td><app-status [nilai]="s.status" /></td>
              @if (auth.punya('stok_sesuaikan')) { <td class="r"><button class="btn-hantu" (click)="buka(s)"><app-ikon n="filter" />Opname</button></td> }
            </tr>
          } @empty { <tr><td colspan="10"><app-kosong ikon="stok" judul="Tidak ada data" /></td></tr> }
        </tbody>
      </table>
    </section>

    <p-dialog header="Stock opname" [visible]="!!form()" (visibleChange)="!$event && form.set(null)" [modal]="true" [style]="{ width: '480px' }" appendTo="body">
      @if (form(); as s) {
        <p class="dialog-sub">{{ s.nama }} · {{ s.gudang }} · stok sistem {{ s.qty | angka }} {{ s.satuan }}</p>
        <div class="form-grid">
          <label class="isian">Qty fisik<p-inputnumber [(ngModel)]="fisik" [min]="0" /></label>
          <label class="isian">Stok minimum<p-inputnumber [(ngModel)]="minimum" [min]="0" /></label>
          <label class="isian penuh">Alasan<input [(ngModel)]="alasan" placeholder="mis. Hasil hitung fisik akhir bulan" /></label>
        </div>
        <p class="selisih">Selisih <b [class.t-bahaya]="fisik - s.qty < 0" [class.t-sukses]="fisik - s.qty > 0">{{ fisik - s.qty > 0 ? '+' : '' }}{{ fisik - s.qty | angka }}</b> {{ s.satuan }} · tercatat di mutasi stok</p>
        @if (galat()) { <div class="galat-form"><app-ikon n="galat" [ukuran]="15" /> {{ galat() }}</div> }
        <div class="dialog-aksi">
          <button class="btn" (click)="form.set(null)">Batal</button>
          <button class="btn-utama" (click)="simpan()">Simpan penyesuaian</button>
        </div>
      }
    </p-dialog>`,
})
export class Stok implements OnInit {
  private api = inject(Api);
  private pesan = inject(MessageService);
  private route = inject(ActivatedRoute);
  readonly auth = inject(Auth);
  readonly data = signal<BarisStok[]>([]);
  readonly ringkas = signal<{ baris: number; menipis: number; nilai: number | null; qty: number } | null>(null);
  readonly form = signal<BarisStok | null>(null);
  readonly galat = signal('');
  q = '';
  gudang = '';
  menipis = false;
  fisik = 0;
  minimum = 0;
  alasan = '';
  private t?: ReturnType<typeof setTimeout>;

  readonly maks = computed(() => this.data().reduce((m, s) => Math.max(m, s.stok_minimum * 3), 1));

  ngOnInit(): void {
    this.menipis = this.route.snapshot.queryParamMap.get('status') === 'menipis';
    this.muat();
  }

  tunda(): void {
    clearTimeout(this.t);
    this.t = setTimeout(() => this.muat(), 300);
  }

  async muat(): Promise<void> {
    const d = await this.api.get<{ data: BarisStok[]; ringkasan: { baris: number; menipis: number; nilai: number | null; qty: number } }>(
      '/stok', { q: this.q, gudang: this.gudang, status: this.menipis ? 'menipis' : '' });
    this.data.set(d.data);
    this.ringkas.set(d.ringkasan);
  }

  ekspor(): void {
    unduhCsv<BarisStok>('stok-gudang', [
      { label: 'Kode', nilai: (r) => r.kode }, { label: 'Produk', nilai: (r) => r.nama }, { label: 'Gudang', nilai: (r) => r.gudang },
      { label: 'Qty', nilai: (r) => r.qty }, { label: 'Minimum', nilai: (r) => r.stok_minimum }, { label: 'Status', nilai: (r) => r.status },
      { label: 'Rata jual per hari', nilai: (r) => r.rata_jual_harian }, { label: 'Hari cukup', nilai: (r) => r.hari_cukup },
    ], this.data());
  }

  level(s: BarisStok): number {
    return Math.min(100, (s.qty / Math.max(1, s.stok_minimum * 3)) * 100);
  }

  buka(s: BarisStok): void {
    this.fisik = s.qty;
    this.minimum = s.stok_minimum;
    this.alasan = '';
    this.galat.set('');
    this.form.set(s);
  }

  async simpan(): Promise<void> {
    const s = this.form()!;
    try {
      const r = await this.api.post<{ selisih: number }>('/stok/penyesuaian', {
        produk_id: s.produk_id, gudang: s.gudang, tanggal: this.auth.meta()!.periode.akhir, qty_fisik: this.fisik,
        stok_minimum: this.minimum, alasan: this.alasan,
      });
      this.pesan.add({ severity: 'success', summary: 'Stok disesuaikan', detail: `${s.nama}: selisih ${r.selisih}`, life: 4000 });
      this.form.set(null);
      this.muat();
    } catch (e) {
      this.galat.set(pesanGalat(e));
    }
  }
}
