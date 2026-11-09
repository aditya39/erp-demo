import { Component, computed, input, signal } from '@angular/core';
import { AngkaPipe } from '../core/pipes';
import { GrafikAI, QueryAI } from '../core/model';
import { Grafik, Seri } from '../shared/grafik';
import { Ikon } from '../shared/ikon';
import { MarkdownPipe } from '../shared/markdown';
import { LangkahAI, PesanChat } from './asisten';
import { KartuDraftSO } from './kartu-draft-so';

export const LABEL_TOOL: Record<string, string> = {
  cari_produk: 'Cari produk',
  tren_penjualan: 'Tren penjualan',
  penjualan_teratas: 'Peringkat penjualan',
  rincian_hpp: 'Rincian HPP',
  riwayat_harga_bahan: 'Riwayat harga bahan',
  produk_pengguna_bahan: 'Produk pemakai bahan',
  cari_dokumen: 'Cari dokumen (RAG)',
  piutang_terbesar: 'Piutang terbesar',
  stok_di_bawah_minimum: 'Stok di bawah minimum',
  margin_produk: 'Margin produk',
  siapkan_draft_so: 'Siapkan draft SO',
};

/** Kartu jawaban asisten: langkah agent (tool call), grafik, jawaban, dan metadata. */
@Component({
  selector: 'app-pesan-ai',
  imports: [Grafik, MarkdownPipe, AngkaPipe, Ikon, KartuDraftSO],
  template: `
    <div class="ai-pesan">
      @if (p().langkah.length) {
        <div class="ai-jejak">
          <button class="ai-jejak-head" (click)="tertutup.set(!tertutup())">
            <app-ikon n="alur" />
            <span>{{ p().selesai ? 'Langkah agent' : 'Agent bekerja' }} · {{ p().langkah.length }} tool{{ jumlahDitolak() ? ' · ' + jumlahDitolak() + ' ditolak' : '' }}</span>
            <app-ikon [n]="tertutup() ? 'kanan' : 'bawah'" />
          </button>
          @if (!tertutup()) {
            <ol class="ai-jejak-list">
              @for (l of p().langkah; track $index) {
                <li [class]="'langkah ' + l.status">
                  <button class="langkah-baris" (click)="buka.set(buka() === $index ? -1 : $index)">
                    <app-ikon class="langkah-ikon" [n]="l.status === 'ok' ? 'ok' : l.status === 'ditolak' ? 'tolak' : 'awas'" [ukuran]="15" />
                    <span class="langkah-isi">
                      <span class="langkah-nama">{{ label(l) }} <code>{{ l.nama }}</code></span>
                      @if (argumen(l)) { <span class="langkah-arg">{{ argumen(l) }}</span> }
                      <span class="langkah-hasil">{{ l.status === 'ditolak' ? 'Ditolak oleh sistem: ' : '' }}{{ l.ringkas }}</span>
                    </span>
                    <span class="langkah-ms">{{ l.durasi_ms | angka }} ms</span>
                  </button>
                  @if (buka() === $index) {
                    @if (l.query?.length) {
                      <div class="langkah-query">
                        <div class="langkah-query-judul"><app-ikon n="db" [ukuran]="13" />Query yang dijalankan</div>
                        @for (q of l.query; track $index) {
                          <pre>{{ sql(q) }}</pre>
                          @if (q.params !== undefined && q.params !== null) { <small>params {{ json(q.params, 0) }}</small> }
                        }
                      </div>
                    }
                    <pre class="langkah-json">{{ json(l.hasil) }}</pre>
                  }
                </li>
              }
            </ol>
          }
        </div>
      }

      @if (!p().selesai && p().fase) {
        <div class="ai-fase"><span class="ai-loader"><i></i><i></i><i></i></span>{{ p().fase }}</div>
      }

      @for (g of p().grafik; track $index) {
        <div class="ai-grafik">
          @if (g.judul) { <div class="ai-grafik-judul">{{ g.judul }}</div> }
          <app-grafik [tipe]="g.tipe" [label]="g.label" [seri]="seri(g)" [horizontal]="!!g.horizontal" [tinggi]="g.horizontal ? 200 : 180" />
        </div>
      }

      @if (p().teks) { <div class="ai-jawaban" [innerHTML]="p().teks | markdown"></div> }
      @for (d of p().draft; track $index) { <app-kartu-draft-so [draft]="d" [aksi]="aksi()" [terbaru]="$last" /> }
      @if (p().error) { <div class="ai-galat"><app-ikon n="galat" /> {{ p().error }}</div> }

      @if (p().selesai && p().durasi_ms !== undefined) {
        <div class="ai-meta">
          <span>{{ p().mode === 'cloud' ? 'Cloud' : 'Lokal' }} · {{ p().model }}</span>
          <span>· {{ detik() }}</span>
          @if (p().token) { <span>· {{ p().token | angka }} token</span> }
          @if (p().rekaman) { <span class="ai-rekaman"><app-ikon n="putar" /> rekaman</span> }
        </div>
      }
    </div>`,
})
export class PesanAI {
  readonly p = input.required<PesanChat>();
  /** false di mode bandingkan: kartu draft transaksi hanya tampil, tanpa tombol simpan. */
  readonly aksi = input(true);
  readonly tertutup = signal(false);
  readonly buka = signal(-1);
  readonly detik = computed(() => ((this.p().durasi_ms ?? 0) / 1000).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' dtk');

  label(l: LangkahAI): string {
    return LABEL_TOOL[l.nama] ?? l.nama;
  }

  argumen(l: LangkahAI): string {
    return Object.entries(l.argumen ?? {}).map(([k, v]) => `${k}=${typeof v === 'string' ? `"${v}"` : JSON.stringify(v)}`).join('  ');
  }

  jumlahDitolak(): number {
    return this.p().langkah.filter((l) => l.status === 'ditolak').length;
  }

  json(v: unknown, indent = 2): string {
    return JSON.stringify(v, null, indent);
  }

  /** SQL dari kode Python (string multi-baris) dirapikan indentasinya. */
  sql(q: QueryAI): string {
    const baris = String(q.sql ?? '').replace(/^\s*\n/, '').trimEnd().split('\n');
    const indent = Math.min(...baris.slice(1).filter((b) => b.trim()).map((b) => b.length - b.trimStart().length));
    return [baris[0].trim(), ...baris.slice(1).map((b) => (Number.isFinite(indent) ? b.slice(indent) : b))].join('\n');
  }

  seri(g: GrafikAI): Seri[] {
    // dua seri = perbandingan periode: periode lama abu-abu, periode baru warna utama
    if (g.seri.length === 2) return g.seri.map((s, i) => ({ nama: s.nama, data: s.data, warna: i === 0 ? '#b8bec8' : undefined }));
    return g.seri.map((s) => ({ nama: s.nama, data: s.data }));
  }
}
