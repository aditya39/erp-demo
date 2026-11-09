import { Injectable, signal } from '@angular/core';

/** Preferensi tampilan per browser: mode gelap & sidebar ringkas. */
@Injectable({ providedIn: 'root' })
export class Tampilan {
  readonly gelap = signal(this.baca('erp-gelap') === '1');
  readonly sidebarRingkas = signal(this.baca('erp-sidebar') === '1');
  readonly online = signal(navigator.onLine);

  constructor() {
    this.terapkan();
    window.addEventListener('online', () => this.online.set(true));
    window.addEventListener('offline', () => this.online.set(false));
  }

  alihTema(): void {
    this.gelap.update((v) => !v);
    this.simpan('erp-gelap', this.gelap() ? '1' : '0');
    this.terapkan();
  }

  alihSidebar(): void {
    this.sidebarRingkas.update((v) => !v);
    this.simpan('erp-sidebar', this.sidebarRingkas() ? '1' : '0');
  }

  private terapkan(): void {
    document.documentElement.classList.toggle('app-dark', this.gelap());
  }

  private baca(k: string): string | null {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  }

  private simpan(k: string, v: string): void {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* mode privat: abaikan */
    }
  }
}
