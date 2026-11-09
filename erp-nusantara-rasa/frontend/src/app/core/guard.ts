import { inject } from '@angular/core';
import { CanDeactivateFn } from '@angular/router';
import { ConfirmationService } from 'primeng/api';

/** Konfirmasi sebelum meninggalkan form yang belum disimpan. */
export const konfirmasiTinggalkan: CanDeactivateFn<{ adaPerubahan?: () => boolean }> = (c) => {
  if (!c.adaPerubahan?.()) return true;
  const konfirmasi = inject(ConfirmationService);
  return new Promise<boolean>((ok) =>
    konfirmasi.confirm({
      header: 'Tinggalkan halaman?', message: 'Isian sales order belum disimpan dan akan hilang.',
      acceptButtonProps: { label: 'Tinggalkan', severity: 'danger', size: 'small' },
      rejectButtonProps: { label: 'Tetap di sini', severity: 'secondary', outlined: true, size: 'small' },
      accept: () => ok(true), reject: () => ok(false),
    }));
};
