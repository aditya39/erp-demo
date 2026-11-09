import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Api, pesanGalat } from '../core/api';
import { Auth } from '../core/auth';
import { Ikon } from '../shared/ikon';
import { Avatar } from '../shared/ui';

interface AkunDemo {
  kode: string;
  nama: string;
  jabatan: string;
  divisi: string;
}

@Component({
  selector: 'app-login',
  imports: [FormsModule, Avatar, Ikon],
  template: `
    <div class="login">
      <section class="login-kartu">
        <div class="login-merek">
          <span class="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 3.5c3.7 2.9 5.8 6.2 5.8 9.6 0 3.8-2.6 6.8-5.8 7.4-3.2-.6-5.8-3.6-5.8-7.4 0-3.4 2.1-6.7 5.8-9.6Z" /><path d="M12 8.5v12" /><path d="M12 13l2.8-2.2M12 16.6l-2.8-2.2" />
            </svg>
          </span>
          <div><b>Nusantara Rasa</b><small>Enterprise Resource Planning</small></div>
        </div>
        <h1>Masuk</h1>
        <p class="sub">Gunakan akun ERP Anda.</p>
        <form (ngSubmit)="masuk()">
          <label class="isian">Nama pengguna
            <input name="kode" [(ngModel)]="kode" autocomplete="username" autofocus />
          </label>
          <label class="isian">Password
            <input name="password" type="password" [(ngModel)]="password" autocomplete="current-password" />
          </label>
          @if (galat()) { <div class="galat-form"><app-ikon n="galat" [ukuran]="15" /> {{ galat() }}</div> }
          <button class="btn-utama lebar" type="submit" [disabled]="proses() || !kode || !password">
            {{ proses() ? 'Memproses…' : 'Masuk' }}
          </button>
        </form>
      </section>

      @if (akun().length) {
        <section class="login-demo">
          <div class="login-demo-head"><b>Akun demo</b><small>password {{ passwordDemo() }}</small></div>
          @for (a of akun(); track a.kode) {
            <button (click)="masukCepat(a)" [disabled]="proses()">
              <app-avatar [nama]="a.nama" />
              <span><b>{{ a.nama }}</b><small>{{ a.jabatan }} · {{ a.kode }}</small></span>
              <app-ikon n="kanan" />
            </button>
          }
        </section>
      }
      <p class="login-kaki">Lingkungan demo workshop. PT Nusantara Rasa adalah perusahaan fiktif dan seluruh datanya dummy.</p>
    </div>`,
})
export class Login implements OnInit {
  private api = inject(Api);
  private auth = inject(Auth);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  kode = '';
  password = '';
  readonly galat = signal('');
  readonly proses = signal(false);
  readonly akun = signal<AkunDemo[]>([]);
  readonly passwordDemo = signal('');

  async ngOnInit(): Promise<void> {
    try {
      const d = await this.api.get<{ password: string; akun: AkunDemo[] }>('/auth/akun-demo');
      this.akun.set(d.akun);
      this.passwordDemo.set(d.password);
    } catch {
      this.galat.set('Server ERP tidak dapat dihubungi. Jalankan: python -m server');
    }
  }

  async masuk(): Promise<void> {
    this.galat.set('');
    this.proses.set(true);
    try {
      await this.auth.login(this.kode, this.password);
      const kembali = this.route.snapshot.queryParamMap.get('kembali');
      this.router.navigateByUrl(kembali && kembali !== '/login' ? kembali : '/');
    } catch (e) {
      this.galat.set(pesanGalat(e));
    } finally {
      this.proses.set(false);
    }
  }

  masukCepat(a: AkunDemo): void {
    this.kode = a.kode;
    this.password = this.passwordDemo();
    this.masuk();
  }
}
