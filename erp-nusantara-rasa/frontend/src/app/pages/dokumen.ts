import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Asisten } from '../ai/asisten';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { MarkdownPipe } from '../shared/markdown';
import { UI } from '../shared/ui';

interface MetaDok {
  slug: string;
  judul: string;
  nomor: string;
  berlaku: string;
  pemilik: string;
  bagian: number;
  kata: number;
}

const SARAN_DOK: Record<string, string> = {
  '01-SOP-Retur-Barang': 'Berapa lama batas retur untuk roti yang rusak dan siapa yang menyetujui retur di atas Rp 10 juta?',
  '02-Kebijakan-Harga-dan-Diskon': 'Siapa yang berwenang menyetujui diskon tambahan 2%?',
  '03-Kebijakan-Kredit-dan-Penagihan': 'Apa tahapan penagihan untuk faktur yang lewat jatuh tempo lebih dari 60 hari?',
  '04-Panduan-Perhitungan-HPP': 'Bagaimana cara menghitung HPP per unit?',
  '05-FAQ-Aplikasi-ERP': 'Bagaimana cara mencetak ulang faktur?',
};

@Component({
  selector: 'app-dokumen',
  imports: [RouterLink, MarkdownPipe, ...UI],
  template: `
    <app-judul judul="SOP & Kebijakan" [jejak]="[{ label: 'Dokumen' }, { label: 'SOP & Kebijakan' }]">
      <ng-container meta><span>{{ daftar().length }} dokumen</span><span>Sumber jawaban Asisten untuk pertanyaan kebijakan</span></ng-container>
    </app-judul>
    <div class="dok">
      <aside class="panel dok-daftar">
        @for (d of daftar(); track d.slug) {
          <a class="dok-item" [class.aktif]="d.slug === aktif()" [routerLink]="'/dokumen/' + d.slug">
            <app-ikon n="teks" /><span><b>{{ d.judul }}</b><small>{{ d.nomor }} · {{ d.pemilik }}</small></span>
          </a>
        }
        <div class="dok-rag"><app-ikon n="db" [ukuran]="14" />
          <span>Setiap bagian (##) disimpan sebagai embedding <code>bge-m3</code> di PostgreSQL + pgvector. Fungsi <code>cari_dokumen</code> mengambil bagian yang paling relevan.</span></div>
      </aside>
      <article class="panel dok-isi">
        @if (isi(); as d) {
          <div class="dok-kepala">
            <div class="dok-meta"><span class="badge b-garis">{{ d.nomor }}</span><span class="badge b-garis">{{ d.berlaku }}</span><span class="badge b-garis">{{ d.pemilik }}</span></div>
            @if (auth.punya('ai') && saran()) {
              <button class="tanya-asisten" (click)="ai.tanya(saran()!)"><app-ikon n="asisten" />Tanya Asisten tentang dokumen ini</button>
            }
          </div>
          <div class="dok-markdown" [innerHTML]="d.isi | markdown"></div>
        } @else {
          <app-kosong ikon="dokumen" judul="Pilih dokumen" />
        }
      </article>
    </div>`,
})
export class Dokumen {
  readonly slug = input<string>();
  private api = inject(Api);
  private router = inject(Router);
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly daftar = signal<MetaDok[]>([]);
  readonly isi = signal<(MetaDok & { isi: string }) | null>(null);
  readonly aktif = computed(() => this.slug() ?? this.daftar()[0]?.slug);
  readonly saran = computed(() => SARAN_DOK[this.aktif() ?? ''] ?? null);

  constructor() {
    this.api.get<{ data: MetaDok[] }>('/dokumen').then((d) => this.daftar.set(d.data));
    effect(() => {
      const s = this.aktif();
      if (s) this.api.get<MetaDok & { isi: string }>(`/dokumen/${s}`).then((d) => this.isi.set(d)).catch(() => this.router.navigate(['/dokumen']));
    });
  }
}
