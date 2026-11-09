import { Component, computed, ElementRef, HostListener, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { MenuModule } from 'primeng/menu';
import { PopoverModule } from 'primeng/popover';
import { TooltipModule } from 'primeng/tooltip';
import { Asisten } from '../ai/asisten';
import { PanelAI } from '../ai/panel-ai';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { Notifikasi } from '../core/model';
import { BulanPipe } from '../core/pipes';
import { Tampilan } from '../core/tampilan';
import { Ikon } from '../shared/ikon';
import { Avatar, Jejak } from '../shared/ui';
import { MENU } from './menu';

interface HasilCari {
  jenis: string;
  judul: string;
  sub: string;
  tautan: string;
}

const IKON_JENIS: Record<string, string> = {
  Halaman: 'panah', Produk: 'produk', Customer: 'customer', Faktur: 'faktur', 'Sales Order': 'so', 'Bahan baku': 'bahan',
};

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, FormsModule, PanelAI, MenuModule, PopoverModule, DialogModule,
            TooltipModule, Avatar, Ikon, BulanPipe],
  templateUrl: './shell.html',
})
export class Shell {
  readonly auth = inject(Auth);
  readonly ai = inject(Asisten);
  readonly tampilan = inject(Tampilan);
  readonly jejak = inject(Jejak);
  private api = inject(Api);
  private router = inject(Router);

  readonly lebarLayar = signal(window.innerWidth);
  /** Sidebar diringkas otomatis saat panel Asisten terbuka di layar sempit (mis. proyektor 1366 px). */
  readonly ringkas = computed(() => this.tampilan.sidebarRingkas() || (this.ai.terbuka() && this.lebarLayar() < 1520));

  readonly notif = signal<Notifikasi[]>([]);
  readonly hitung = signal<{ so_saya: number; so_menunggu: number }>({ so_saya: 0, so_menunggu: 0 });

  readonly menu = computed(() =>
    MENU.map((g) => ({ ...g, item: g.item.filter((i) => !i.izin.length || this.auth.punya(...i.izin)) })).filter((g) => g.item.length));

  readonly menuUser = computed<MenuItem[]>(() => [
    { label: this.tampilan.gelap() ? 'Mode terang' : 'Mode gelap', icon: this.tampilan.gelap() ? 'matahari' : 'bulan', command: () => this.tampilan.alihTema() },
    { label: this.tampilan.sidebarRingkas() ? 'Lebarkan sidebar' : 'Ringkas sidebar', icon: 'sidebar', command: () => this.tampilan.alihSidebar() },
    { separator: true },
    { label: 'Ganti pengguna', icon: 'customer', command: () => this.keluar() },
    { label: 'Keluar', icon: 'keluar', command: () => this.keluar() },
  ]);

  // pencarian global
  readonly cariBuka = signal(false);
  readonly q = signal('');
  readonly hasil = signal<HasilCari[]>([]);
  readonly pilih = signal(0);
  private kotakCari = viewChild<ElementRef<HTMLInputElement>>('kotakCari');
  private tunda?: ReturnType<typeof setTimeout>;

  constructor() {
    if (this.auth.punya('ai')) this.ai.muatInfo().catch(() => undefined);
    this.muatNotif();
    setInterval(() => this.muatNotif(), 45_000);
  }

  @HostListener('window:resize')
  ukur(): void {
    this.lebarLayar.set(window.innerWidth);
  }

  async muatNotif(): Promise<void> {
    try {
      const d = await this.api.get<{ item: Notifikasi[]; hitung: { so_saya: number; so_menunggu: number } }>('/notifikasi');
      this.notif.set(d.item);
      this.hitung.set(d.hitung);
    } catch {
      /* diabaikan */
    }
  }

  ikonNotif(n: Notifikasi): string {
    return ({ persetujuan: 'setuju', stok: 'stok', hpp: 'hpp', info: 'jam' } as Record<string, string>)[n.jenis] ?? 'info';
  }

  buka(n: Notifikasi, pop: { hide: () => void }): void {
    pop.hide();
    this.router.navigateByUrl(n.tautan);
  }

  async keluar(): Promise<void> {
    await this.auth.logout();
    this.ai.pesan.set([]);
    this.ai.terbuka.set(false);
    this.router.navigate(['/login']);
  }

  @HostListener('document:keydown', ['$event'])
  pintasan(e: KeyboardEvent): void {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      this.bukaCari();
    } else if (mod && e.key.toLowerCase() === 'j' && this.auth.punya('ai')) {
      e.preventDefault();
      this.ai.alih();
    }
  }

  bukaCari(): void {
    this.q.set('');
    this.hasil.set(this.halamanCocok(''));
    this.pilih.set(0);
    this.cariBuka.set(true);
    setTimeout(() => this.kotakCari()?.nativeElement.focus(), 60);
  }

  private halamanCocok(q: string): HasilCari[] {
    const k = q.toLowerCase();
    return this.menu().flatMap((g) => g.item.map((i) => ({ jenis: 'Halaman', judul: i.label, sub: g.judul || '', tautan: i.tautan })))
      .filter((h) => !k || h.judul.toLowerCase().includes(k)).slice(0, k ? 4 : 7);
  }

  readonly grupHasil = computed(() => {
    const g = new Map<string, { h: HasilCari; i: number }[]>();
    this.hasil().forEach((h, i) => g.set(h.jenis, [...(g.get(h.jenis) ?? []), { h, i }]));
    return [...g.entries()].map(([jenis, isi]) => ({ jenis, isi }));
  });

  ketik(q: string): void {
    this.q.set(q);
    clearTimeout(this.tunda);
    this.tunda = setTimeout(async () => {
      let data: HasilCari[] = [];
      if (q.trim().length >= 2) {
        try {
          data = (await this.api.get<{ hasil: HasilCari[] }>('/cari', { q })).hasil;
        } catch {
          data = [];
        }
      }
      this.hasil.set([...this.halamanCocok(q), ...data]);
      this.pilih.set(0);
    }, 150);
  }

  navCari(e: KeyboardEvent): void {
    const n = this.hasil().length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.pilih.set((this.pilih() + 1) % Math.max(n, 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.pilih.set((this.pilih() - 1 + n) % Math.max(n, 1));
    } else if (e.key === 'Enter') {
      if (n) this.ke(this.hasil()[this.pilih()]);
      else if (this.q().trim() && this.auth.punya('ai')) this.tanyaAIDariCari();
    }
  }

  ke(h: HasilCari): void {
    this.cariBuka.set(false);
    this.router.navigateByUrl(h.tautan);
  }

  tanyaAIDariCari(): void {
    const q = this.q().trim();
    this.cariBuka.set(false);
    if (q) this.ai.tanya(q);
    else this.ai.buka();
  }

  ikonJenis(j: string): string {
    return IKON_JENIS[j] ?? 'titik';
  }

  hitungMenu(tautan: string): { n: number; penting: boolean } | null {
    if (tautan !== '/penjualan/sales-order') return null;
    const h = this.hitung();
    if (h.so_saya) return { n: h.so_saya, penting: true };
    return h.so_menunggu ? { n: h.so_menunggu, penting: false } : null;
  }
}
