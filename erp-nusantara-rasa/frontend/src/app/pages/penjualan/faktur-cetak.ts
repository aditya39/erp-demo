import { Component, inject, input, OnInit, signal } from '@angular/core';
import { Api } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { Ikon } from '../../shared/ikon';
import { DetailFaktur } from './faktur-detail';

/** Tampilan cetak faktur (A4). Dibuka di tab baru lalu dialog cetak browser muncul otomatis. */
@Component({
  selector: 'app-faktur-cetak',
  imports: [...PIPES, Ikon],
  template: `
    @if (f(); as f) {
      <div class="cetak">
        <div class="cetak-alat"><button class="btn" (click)="tutup()">Tutup</button><button class="btn-utama" (click)="cetak()"><app-ikon n="cetak" />Cetak</button></div>
        <article class="cetak-kertas">
          <header class="cetak-kepala">
            <div>
              <div class="cetak-merek"><span class="logo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5c3.7 2.9 5.8 6.2 5.8 9.6 0 3.8-2.6 6.8-5.8 7.4-3.2-.6-5.8-3.6-5.8-7.4 0-3.4 2.1-6.7 5.8-9.6Z" /><path d="M12 8.5v12" /><path d="M12 13l2.8-2.2M12 16.6l-2.8-2.2" /></svg></span>{{ auth.meta()?.perusahaan }}</div>
              <small>Kawasan Industri Pangan Blok C-12 (alamat fiktif)</small>
            </div>
            <div class="cetak-judul"><h1>FAKTUR</h1><b>{{ f.nomor }}</b></div>
          </header>
          <section class="cetak-info">
            <div><span>Kepada</span><b>{{ f.customer_info.nama }}</b><small>{{ f.customer_info.alamat }}</small><small>{{ f.customer_info.kontak }}</small></div>
            <div class="cetak-meta">
              <div><span>Tanggal</span><b>{{ f.tanggal | tgl }}</b></div>
              <div><span>Jatuh tempo</span><b>{{ f.jatuh_tempo | tgl }}</b></div>
              <div><span>Sales order</span><b>{{ f.so?.nomor ?? '–' }}</b></div>
              <div><span>Gudang</span><b>{{ f.gudang ?? '–' }}</b></div>
            </div>
          </section>
          <table>
            <thead><tr><th>No</th><th>Produk</th><th class="r">Qty</th><th class="r">Harga</th><th class="r">Disc.</th><th class="r">Jumlah</th></tr></thead>
            <tbody>
              @for (i of f.item; track i.id; let n = $index) {
                <tr><td>{{ n + 1 }}</td><td>{{ i.nama }} <small>{{ i.kode }}</small></td><td class="r">{{ i.qty | angka }} {{ i.satuan }}</td>
                  <td class="r">{{ i.harga | rupiah }}</td><td class="r">{{ i.diskon_persen | angka: 1 }}%</td><td class="r">{{ i.subtotal | rupiah }}</td></tr>
              }
            </tbody>
          </table>
          <div class="cetak-total">
            <div><span>Total sebelum diskon</span><b>{{ f.bruto | rupiah }}</b></div>
            <div><span>Diskon</span><b>-{{ f.bruto - f.total | rupiah }}</b></div>
            <div class="besar"><span>TOTAL</span><b>{{ f.total | rupiah }}</b></div>
            <small>Harga sudah termasuk PPN.</small>
          </div>
          <footer class="cetak-kaki">
            <div>Pembayaran melalui transfer ke rekening perusahaan dengan mencantumkan nomor faktur.</div>
            <div class="ttd"><span>Hormat kami,</span><b>Divisi Finance</b></div>
          </footer>
          <div class="cetak-fiktif">Dokumen contoh dari aplikasi demo workshop · perusahaan & data fiktif</div>
        </article>
      </div>
    }`,
})
export class FakturCetak implements OnInit {
  readonly id = input.required<string>();
  private api = inject(Api);
  readonly auth = inject(Auth);
  readonly f = signal<DetailFaktur | null>(null);

  async ngOnInit(): Promise<void> {
    this.f.set(await this.api.get<DetailFaktur>(`/faktur/${this.id()}`));
    setTimeout(() => window.print(), 400);
  }

  cetak(): void {
    window.print();
  }

  tutup(): void {
    window.close();
  }
}
