import { computed, inject, Injectable, signal } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Api } from './api';
import { Meta, Pengguna } from './model';

@Injectable({ providedIn: 'root' })
export class Auth {
  private api = inject(Api);
  readonly user = signal<Pengguna | null>(null);
  readonly meta = signal<Meta | null>(null);
  readonly namaDepan = computed(() => this.user()?.nama.split(' ')[0] ?? '');

  async muat(): Promise<boolean> {
    try {
      this.user.set(await this.api.get<Pengguna>('/auth/me'));
      if (!this.meta()) this.meta.set(await this.api.get<Meta>('/meta'));
      return true;
    } catch {
      this.user.set(null);
      return false;
    }
  }

  async login(kode: string, password: string): Promise<void> {
    this.user.set(await this.api.post<Pengguna>('/auth/login', { kode, password }));
    this.meta.set(await this.api.get<Meta>('/meta'));
  }

  async logout(): Promise<void> {
    await this.api.post('/auth/logout', {});
    this.user.set(null);
  }

  /** true bila user memiliki salah satu izin. */
  punya(...izin: string[]): boolean {
    const u = this.user();
    return !!u && izin.some((i) => u.izin.includes(i));
  }
}

export const harusLogin: CanActivateFn = async (route) => {
  const auth = inject(Auth);
  const router = inject(Router);
  if (!auth.user() && !(await auth.muat())) return router.parseUrl('/login');
  const izin = route.data?.['izin'] as string[] | undefined;
  if (izin?.length && !auth.punya(...izin)) return router.parseUrl('/akses-ditolak');
  return true;
};
