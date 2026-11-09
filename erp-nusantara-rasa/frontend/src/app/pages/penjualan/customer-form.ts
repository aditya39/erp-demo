import { Component, computed, inject, model, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MessageService } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectModule } from 'primeng/select';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { Api, pesanGalat } from '../../core/api';
import { Auth } from '../../core/auth';
import { Ikon } from '../../shared/ikon';

export interface DataCustomer {
  id?: number;
  nama: string;
  kota: string;
  segmen: string;
  alamat: string;
  kontak: string;
  telepon: string;
  limit_kredit: number | null;
  aktif: boolean;
}

/** Dialog tambah / ubah customer. Limit kredit hanya bisa diubah Divisi Finance. */
@Component({
  selector: 'app-customer-form',
  imports: [FormsModule, DialogModule, SelectModule, InputNumberModule, ToggleSwitchModule, Ikon],
  template: `
    <p-dialog [header]="data()?.id ? 'Ubah customer' : 'Customer baru'" [visible]="!!data()" (visibleChange)="!$event && data.set(null)"
              [modal]="true" [style]="{ width: '600px' }" appendTo="body">
      @if (data(); as d) {
        <div class="form-grid">
          <label class="isian penuh">Nama customer<input [(ngModel)]="d.nama" [disabled]="!bolehProfil" placeholder="mis. Toko Sumber Rejeki" /></label>
          <label class="isian">Segmen
            <p-select [options]="segmen()" optionLabel="nama" optionValue="nama" [(ngModel)]="d.segmen" (ngModelChange)="gantiSegmen($event)"
                      [disabled]="!bolehProfil" appendTo="body" /></label>
          <label class="isian">Kota<p-select [options]="auth.meta()!.kota" [(ngModel)]="d.kota" [editable]="true" [disabled]="!bolehProfil" appendTo="body" /></label>
          <label class="isian penuh">Alamat<input [(ngModel)]="d.alamat" [disabled]="!bolehProfil" /></label>
          <label class="isian">Kontak (PIC)<input [(ngModel)]="d.kontak" [disabled]="!bolehProfil" /></label>
          <label class="isian">Telepon<input [(ngModel)]="d.telepon" [disabled]="!bolehProfil" /></label>
          <label class="isian">Limit kredit
            <p-inputnumber [(ngModel)]="d.limit_kredit" mode="currency" currency="IDR" locale="id-ID" [maxFractionDigits]="0" [disabled]="!bolehLimit" />
            <small>{{ bolehLimit ? 'Perubahan limit tercatat di log aktivitas.' : 'Mengikuti segmen. Perubahan limit disetujui Divisi Finance.' }}</small>
          </label>
          <label class="isian">Termin & diskon standar
            <input [value]="infoSegmen()" disabled /><small>Ditetapkan dari segmen.</small></label>
          @if (d.id) {
            <label class="isian penuh baris-toggle"><p-toggleswitch [(ngModel)]="d.aktif" [disabled]="!bolehProfil" /> Customer aktif</label>
          }
        </div>
        @if (galat()) { <div class="galat-form" style="margin-top: 12px"><app-ikon n="galat" [ukuran]="15" /> {{ galat() }}</div> }
        <div class="dialog-aksi">
          <button class="btn" (click)="data.set(null)">Batal</button>
          <button class="btn-utama" (click)="simpan()" [disabled]="proses()">Simpan</button>
        </div>
      }
    </p-dialog>`,
})
export class CustomerForm {
  readonly data = model<DataCustomer | null>(null);
  readonly tersimpan = output<number>();
  readonly auth = inject(Auth);
  private api = inject(Api);
  private pesan = inject(MessageService);
  readonly galat = signal('');
  readonly proses = signal(false);
  readonly segmen = computed(() => this.auth.meta()!.segmen);
  readonly infoSegmen = computed(() => {
    const s = this.segmen().find((x) => x.nama === this.data()?.segmen);
    return s ? `${s.termin} hari · diskon ${s.diskon}%` : '–';
  });

  get bolehProfil(): boolean {
    return this.auth.punya('customer_kelola');
  }

  get bolehLimit(): boolean {
    return this.auth.punya('limit_kredit');
  }

  gantiSegmen(nama: string): void {
    const s = this.segmen().find((x) => x.nama === nama);
    const d = this.data();
    if (s && d && !d.id) d.limit_kredit = s.limit;
  }

  async simpan(): Promise<void> {
    const d = this.data()!;
    this.galat.set('');
    this.proses.set(true);
    try {
      const r = d.id
        ? await this.api.put<{ ok: boolean }>(`/customer/${d.id}`, d)
        : await this.api.post<{ id: number; kode: string }>('/customer', d);
      const id = d.id ?? (r as { id: number }).id;
      this.pesan.add({ severity: 'success', summary: d.id ? 'Customer diperbarui' : 'Customer ditambahkan', detail: d.nama, life: 4000 });
      this.data.set(null);
      this.tersimpan.emit(id);
    } catch (e) {
      this.galat.set(pesanGalat(e));
    } finally {
      this.proses.set(false);
    }
  }
}

export function customerKosong(segmen = 'Toko', limit = 40_000_000): DataCustomer {
  return { nama: '', kota: 'Jakarta', segmen, alamat: '', kontak: '', telepon: '', limit_kredit: limit, aktif: true };
}
