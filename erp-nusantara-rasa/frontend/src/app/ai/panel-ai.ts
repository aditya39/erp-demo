import { Component, computed, effect, ElementRef, HostListener, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { MenuModule } from 'primeng/menu';
import { TooltipModule } from 'primeng/tooltip';
import { filter } from 'rxjs';
import { Auth } from '../core/auth';
import { Tampilan } from '../core/tampilan';
import { alirkan, Asisten, PesanChat, pesanAIBaru, Rekaman, terapkanEvent } from './asisten';
import { Ikon } from '../shared/ikon';
import { LABEL_TOOL, PesanAI } from './pesan-ai';

interface Saran {
  teks: string;
  izin: string;
}

/** Saran pertanyaan per modul. Hanya yang diizinkan untuk user yang tampil. */
const SARAN: Record<string, Saran[]> = {
  beranda: [
    { teks: 'Kenapa HPP Roti Cokelat naik bulan ini? Produk apa lagi yang terdampak?', izin: 'hpp' },
    { teks: 'Bagaimana tren penjualan Biskuit Kelapa 6 bulan terakhir?', izin: 'penjualan' },
    { teks: 'Lima customer dengan penjualan terbesar 3 bulan terakhir?', izin: 'penjualan' },
    { teks: 'Berapa lama batas retur untuk roti yang rusak?', izin: 'dokumen' },
  ],
  penjualan: [
    { teks: 'Bagaimana tren penjualan Biskuit Kelapa per segmen 6 bulan terakhir?', izin: 'penjualan' },
    { teks: 'Produk apa yang penjualannya paling besar 3 bulan terakhir?', izin: 'penjualan' },
    { teks: 'Berapa diskon tambahan yang boleh diberikan tanpa persetujuan Manajer Penjualan?', izin: 'dokumen' },
    { teks: 'Kota mana yang omzetnya paling tinggi 6 bulan terakhir?', izin: 'penjualan' },
  ],
  keuangan: [
    { teks: 'Apa tahapan penagihan untuk faktur yang lewat jatuh tempo lebih dari 60 hari?', izin: 'dokumen' },
    { teks: 'Siapa yang menyetujui sales order yang melebihi limit kredit?', izin: 'dokumen' },
    { teks: 'Bagaimana aturan pencatatan pembayaran sebagian?', izin: 'dokumen' },
  ],
  persediaan: [
    { teks: 'Bagaimana tren penjualan Biskuit Kelapa per kota 3 bulan terakhir?', izin: 'penjualan' },
    { teks: 'Berapa lama batas retur untuk roti yang rusak?', izin: 'dokumen' },
  ],
  produksi: [
    { teks: 'Kenapa HPP Roti Cokelat naik bulan ini? Produk apa lagi yang terdampak?', izin: 'hpp' },
    { teks: 'Bagaimana riwayat harga kakao bubuk 6 bulan terakhir?', izin: 'hpp' },
    { teks: 'Produk apa saja yang memakai gula pasir dan berapa porsinya di HPP?', izin: 'hpp' },
    { teks: 'Apa yang harus dilakukan jika HPP naik lebih dari 8%?', izin: 'dokumen' },
  ],
  dokumen: [
    { teks: 'Berapa lama batas retur untuk roti yang rusak?', izin: 'dokumen' },
    { teks: 'Siapa yang menyetujui diskon tambahan 2%?', izin: 'dokumen' },
    { teks: 'Bagaimana cara mencetak ulang faktur?', izin: 'dokumen' },
  ],
};

@Component({
  selector: 'app-panel-ai',
  imports: [FormsModule, PesanAI, MenuModule, DialogModule, TooltipModule, Ikon],
  templateUrl: './panel-ai.html',
})
export class PanelAI {
  readonly ai = inject(Asisten);
  readonly auth = inject(Auth);
  readonly tampilan = inject(Tampilan);
  private router = inject(Router);
  private gulir = viewChild<ElementRef<HTMLDivElement>>('gulir');
  private input = viewChild<ElementRef<HTMLTextAreaElement>>('input');

  readonly modul = signal(this.modulDari(this.router.url));
  readonly saran = computed(() => {
    const sudah = new Set(this.ai.pesan().filter((p) => p.peran === 'user').map((p) => p.teks));
    return (SARAN[this.modul()] ?? SARAN['beranda']).filter((s) => this.auth.punya(s.izin) && !sudah.has(s.teks)).slice(0, 4);
  });
  readonly modelAktif = computed(() => {
    const i = this.ai.info();
    return i ? (this.ai.mode() === 'cloud' ? i.cloud.model : i.lokal.model) : '…';
  });
  readonly izinAI = computed(() => {
    const i = this.ai.info();
    if (!i) return [];
    const seen = new Map<string, boolean>();
    for (const t of i.tools) seen.set(t.label_izin, t.boleh);
    return [...seen.entries()].map(([label, boleh]) => ({ label, boleh }));
  });

  readonly menu: MenuItem[] = [
    { label: 'Bandingkan lokal vs cloud', icon: 'banding', command: () => this.bukaBanding() },
    { label: 'Putar rekaman demo', icon: 'putar', command: () => this.bukaRekaman() },
    { label: 'Tools & hak akses', icon: 'alat', command: () => this.dialogTools.set(true) },
    { separator: true },
    { label: 'Percakapan baru', icon: 'edit', command: () => this.ai.bersihkan() },
  ];

  // dialog
  readonly dialogTools = signal(false);
  readonly dialogRekaman = signal(false);
  readonly dialogBanding = signal(false);
  readonly rekaman = signal<Rekaman[]>([]);
  readonly kecepatan = signal(1);
  readonly bandingTanya = signal('');
  readonly banding = signal<{ lokal: PesanChat | null; cloud: PesanChat | null }>({ lokal: null, cloud: null });
  readonly labelTool = LABEL_TOOL;

  constructor() {
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe((e) => this.modul.set(this.modulDari(e.urlAfterRedirects)));
    effect(() => {
      this.ai.pesan();
      queueMicrotask(() => {
        const el = this.gulir()?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      });
    });
    effect(() => {
      if (this.ai.terbuka()) setTimeout(() => this.input()?.nativeElement.focus(), 80);
    });
  }

  private modulDari(url: string): string {
    const seg = url.split('?')[0].split('/')[1] || 'beranda';
    return seg === 'pengaturan' ? 'beranda' : seg;
  }

  kirim(): void {
    this.ai.tanya(this.ai.draf());
  }

  tekan(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.kirim();
    }
  }

  setMode(m: 'lokal' | 'cloud'): void {
    if (m === 'cloud' && !this.ai.info()?.cloud.aktif) return;
    this.ai.mode.set(m);
  }

  @HostListener('document:keydown.escape')
  esc(): void {
    if (this.ai.terbuka() && !this.dialogBanding() && !this.dialogRekaman() && !this.dialogTools()) this.ai.terbuka.set(false);
  }

  // ---- rekaman ------------------------------------------------------------
  async bukaRekaman(): Promise<void> {
    this.rekaman.set(await this.ai.daftarRekaman());
    this.dialogRekaman.set(true);
  }

  rekamanDemo = computed(() => this.rekaman().filter((r) => r.sumber === 'demo'));
  rekamanErp = computed(() => this.rekaman().filter((r) => r.sumber === 'erp').slice(0, 12));

  putar(r: Rekaman): void {
    this.dialogRekaman.set(false);
    this.ai.putar(r, this.kecepatan());
  }

  // ---- bandingkan lokal vs cloud -----------------------------------------
  bukaBanding(): void {
    const terakhir = [...this.ai.pesan()].reverse().find((p) => p.peran === 'user')?.teks;
    this.bandingTanya.set(this.ai.draf().trim() || terakhir || this.saran()[0]?.teks || '');
    this.banding.set({ lokal: null, cloud: null });
    this.dialogBanding.set(true);
  }

  async jalankanBanding(): Promise<void> {
    const teks = this.bandingTanya().trim();
    if (!teks) return;
    const awal = { lokal: pesanAIBaru(), cloud: pesanAIBaru() };
    this.banding.set(awal);
    const info = this.ai.info();
    await Promise.all((['lokal', 'cloud'] as const).map(async (mode) => {
      const ubah = (f: (p: PesanChat) => PesanChat) => this.banding.update((b) => ({ ...b, [mode]: f(b[mode]!) }));
      if (!info?.[mode].aktif) {
        ubah((p) => ({ ...p, error: (mode === 'cloud' && info?.cloud.alasan) || `Model ${mode} belum dikonfigurasi (.env di kit).`, selesai: true, fase: '' }));
        return;
      }
      await alirkan(teks, mode, [], (ev) => ubah((p) => terapkanEvent(p, ev)));
    }));
  }

  detik(ms: number): string {
    return (ms / 1000).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' dtk';
  }
}
