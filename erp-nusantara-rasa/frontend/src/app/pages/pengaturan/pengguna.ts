import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MessageService } from 'primeng/api';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { TooltipModule } from 'primeng/tooltip';
import { Asisten } from '../../ai/asisten';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { PIPES } from '../../core/pipes';
import { UI } from '../../shared/ui';

interface BarisPengguna {
  kode: string;
  nama: string;
  jabatan: string;
  divisi: string;
  email: string;
  izin: string[];
  aktif: boolean;
  login_terakhir: string | null;
}

@Component({
  selector: 'app-pengguna',
  imports: [FormsModule, ToggleSwitchModule, TooltipModule, ...UI, ...PIPES],
  template: `
    <app-judul judul="Pengguna & hak akses" [jejak]="[{ label: 'Pengaturan' }, { label: 'Pengguna & hak akses' }]">
      <ng-container meta><span>{{ pengguna().length }} pengguna</span><span>Perubahan langsung berlaku untuk menu ERP dan Asisten</span></ng-container>
    </app-judul>

    <div class="pita p-info"><app-ikon n="akses" />
      <div class="pita-isi"><b>Satu sumber hak akses</b>
        <p>Kolom <i>Akses data</i> juga mengatur fungsi yang boleh dijalankan Asisten. Contoh: cabut "HPP & harga bahan baku" dari Sari, lalu tanyakan HPP sebagai Sari — fungsi HPP ditolak oleh kode, bukan oleh prompt.</p></div></div>

    <section class="panel">
      <div class="gulir-x">
        <table class="tabel matriks">
          <thead>
            <tr class="kelompok"><th></th>
              @for (g of kelompok(); track g.nama) { <th [attr.colspan]="g.jumlah">{{ g.nama }}</th> }
            </tr>
            <tr><th class="kolom-user">Pengguna</th>
              @for (i of katalog(); track i.kode) { <th class="c izin-kolom" [pTooltip]="i.label" tooltipPosition="top">{{ i.label }}</th> }
            </tr>
          </thead>
          <tbody>
            @for (u of pengguna(); track u.kode) {
              <tr>
                <td class="kolom-user"><div class="sel-orang"><app-avatar [nama]="u.nama" ukuran="kecil" />
                  <div class="sel-utama"><b>{{ u.nama }}</b><small>{{ u.jabatan }}</small>
                    <small class="samar">login {{ u.login_terakhir ? (u.login_terakhir | relatif) : 'belum pernah' }}</small></div></div></td>
                @for (i of katalog(); track i.kode) {
                  <td class="c" [class.izin-ai]="i.kelompok === 'Akses data'">
                    <p-toggleswitch [ngModel]="u.izin.includes(i.kode)" (ngModelChange)="ubah(u, i.kode, $event)"
                                    [disabled]="menyimpan() === u.kode || (u.kode === auth.user()?.kode && i.kode === 'pengaturan')" />
                  </td>
                }
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
    <p class="catatan-tabel">Kolom berlatar ungu dipakai juga oleh Asisten. Setiap perubahan tercatat di log aktivitas.</p>`,
})
export class PenggunaHakAkses implements OnInit {
  private api = inject(Api);
  private pesan = inject(MessageService);
  readonly auth = inject(Auth);
  private ai = inject(Asisten);
  readonly pengguna = signal<BarisPengguna[]>([]);
  readonly menyimpan = signal('');
  readonly katalog = computed(() => this.auth.meta()!.katalog_izin);
  readonly kelompok = computed(() => {
    const out: { nama: string; jumlah: number }[] = [];
    for (const i of this.katalog()) {
      const g = out.at(-1);
      if (g?.nama === i.kelompok) g.jumlah++;
      else out.push({ nama: i.kelompok, jumlah: 1 });
    }
    return out;
  });

  async ngOnInit(): Promise<void> {
    this.pengguna.set((await this.api.get<{ data: BarisPengguna[] }>('/pengguna')).data);
  }

  async ubah(u: BarisPengguna, izin: string, aktif: boolean): Promise<void> {
    const baru = aktif ? [...new Set([...u.izin, izin])] : u.izin.filter((x) => x !== izin);
    this.menyimpan.set(u.kode);
    try {
      const r = await this.api.put<{ izin: string[] }>(`/pengguna/${u.kode}/izin`, { izin: baru });
      this.pengguna.update((l) => l.map((x) => (x.kode === u.kode ? { ...x, izin: r.izin } : x)));
      const label = this.katalog().find((k) => k.kode === izin)?.label;
      this.pesan.add({ severity: aktif ? 'success' : 'warn', summary: `${u.nama}: ${aktif ? 'izin ditambahkan' : 'izin dicabut'}`, detail: label, life: 3500 });
      if (u.kode === this.auth.user()?.kode) {
        await this.auth.muat();
        this.ai.info.set(null);
      }
    } catch (e) {
      this.pesan.add({ severity: 'error', summary: 'Gagal', detail: pesanGalat(e), life: 5000 });
      this.pengguna.update((l) => [...l]);
    } finally {
      this.menyimpan.set('');
    }
  }
}
