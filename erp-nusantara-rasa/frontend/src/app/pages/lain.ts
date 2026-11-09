import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Ikon } from '../shared/ikon';

@Component({
  selector: 'app-akses-ditolak',
  imports: [RouterLink, Ikon],
  template: `
    <div class="halaman-galat">
      <app-ikon n="kunci" [ukuran]="28" />
      <h1>Tidak ada akses</h1>
      <p>Hak akses Anda tidak mencakup halaman ini. Ajukan permintaan akses melalui atasan atau administrator ERP.</p>
      <a class="btn" routerLink="/">Kembali ke ringkasan</a>
    </div>`,
})
export class AksesDitolak {}

@Component({
  selector: 'app-tidak-ditemukan',
  imports: [RouterLink, Ikon],
  template: `
    <div class="halaman-galat">
      <app-ikon n="cari" [ukuran]="28" />
      <h1>Halaman tidak ditemukan</h1>
      <p>Alamat yang Anda buka tidak tersedia.</p>
      <a class="btn" routerLink="/">Kembali ke ringkasan</a>
    </div>`,
})
export class TidakDitemukan {}
