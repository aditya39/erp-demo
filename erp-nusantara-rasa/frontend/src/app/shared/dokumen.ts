import { Component, input } from '@angular/core';
import { Peristiwa, Tahap } from '../core/model';
import { TanggalPipe } from '../core/pipes';
import { Ikon } from './ikon';

/** Tahapan dokumen (stepper horizontal). */
@Component({
  selector: 'app-tahapan',
  imports: [Ikon],
  template: `
    <div class="tahapan">
      @for (t of tahap(); track t.label; let i = $index) {
        <div class="tahap" [class]="'tahap ' + t.keadaan">
          <span class="tahap-ikon">
            @if (t.keadaan === 'selesai') { <app-ikon n="centang" [tebal]="2.5" /> }
            @else if (t.keadaan === 'gagal') { <app-ikon n="x" [tebal]="2.5" /> }
            @else { <small>{{ i + 1 }}</small> }
          </span>
          <span class="tahap-teks"><b>{{ t.label }}</b><small>{{ t.ket }}</small></span>
        </div>
      }
    </div>`,
  styles: `.tahap-ikon small { font-size: 11px; font-weight: 600; }`,
})
export class Tahapan {
  readonly tahap = input.required<Tahap[]>();
}

const IKON: Record<string, string> = {
  buat: 'so', tahan: 'jeda', setuju: 'centang', tolak: 'tolak', faktur: 'faktur', bayar: 'bayar', batal: 'tolak', ai: 'asisten',
};

/** Riwayat dokumen (timeline vertikal). */
@Component({
  selector: 'app-riwayat',
  imports: [Ikon, TanggalPipe],
  template: `
    <ol class="linimasa">
      @for (e of data(); track $index) {
        <li [class]="'j-' + e.jenis">
          <span class="lm-ikon"><app-ikon [n]="ikon(e.jenis)" /></span>
          <div class="lm-isi"><b>{{ e.aktor }}</b> <span class="redup">{{ e.aksi.charAt(0).toLowerCase() + e.aksi.slice(1) }}</span>
            @if (e.ket) { <p>{{ e.ket }}</p> }</div>
          <span class="lm-waktu">{{ e.hanya_tanggal ? (e.waktu | tgl) : (e.waktu | tgl: 'waktu') }}</span>
        </li>
      }
    </ol>`,
})
export class Riwayat {
  readonly data = input.required<Peristiwa[]>();

  ikon(j: string): string {
    return IKON[j] ?? 'titik';
  }
}
