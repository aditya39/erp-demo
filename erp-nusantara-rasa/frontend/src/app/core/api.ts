import { HttpClient, HttpErrorResponse, HttpInterceptorFn, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { MessageService } from 'primeng/api';
import { catchError, firstValueFrom, throwError } from 'rxjs';

type Param = Record<string, string | number | boolean | null | undefined>;

/** Ambil pesan galat dari respons API (format {pesan} atau validasi FastAPI {detail}). */
export function pesanGalat(e: unknown): string {
  if (e instanceof HttpErrorResponse) {
    const b = e.error;
    if (b?.pesan) return b.pesan;
    if (Array.isArray(b?.detail)) return b.detail.map((d: { msg: string }) => d.msg).join('; ');
    if (typeof b?.detail === 'string') return b.detail;
    if (e.status === 0) return 'Server ERP tidak dapat dihubungi.';
    return `Terjadi kesalahan (${e.status}).`;
  }
  return String(e);
}

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);

  get<T>(url: string, param: Param = {}): Promise<T> {
    let params = new HttpParams();
    for (const [k, v] of Object.entries(param)) if (v !== null && v !== undefined && v !== '') params = params.set(k, String(v));
    return firstValueFrom(this.http.get<T>('/api' + url, { params }));
  }

  post<T>(url: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.post<T>('/api' + url, body));
  }

  put<T>(url: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.put<T>('/api' + url, body));
  }
}

/** 401 -> halaman login. 403/500/jaringan -> notifikasi. 422 (aturan bisnis) ditangani halaman. */
export const galatInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const pesan = inject(MessageService);
  return next(req).pipe(
    catchError((e: HttpErrorResponse) => {
      if (e.status === 401 && !req.url.includes('/auth/')) {
        router.navigate(['/login'], { queryParams: { kembali: router.url } });
      } else if (e.status === 403) {
        pesan.add({ severity: 'warn', summary: 'Akses ditolak', detail: pesanGalat(e), life: 5000 });
      } else if (e.status === 0 || e.status >= 500) {
        pesan.add({ severity: 'error', summary: 'Gagal', detail: pesanGalat(e), life: 6000 });
      }
      return throwError(() => e);
    }),
  );
};
