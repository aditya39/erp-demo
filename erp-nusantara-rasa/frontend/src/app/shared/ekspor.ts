/** Ekspor tabel ke CSV (pemisah titik koma, terbaca langsung oleh Excel versi Indonesia). */
export interface KolomCsv<T> {
  label: string;
  nilai: (r: T) => string | number | null | undefined;
}

function sel(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return '';
  const s = typeof v === 'number' ? String(v).replace('.', ',') : v;
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function unduhCsv<T>(nama: string, kolom: KolomCsv<T>[], baris: T[]): void {
  const isi = [kolom.map((k) => sel(k.label)).join(';'), ...baris.map((r) => kolom.map((k) => sel(k.nilai(r))).join(';'))].join('\r\n');
  const blob = new Blob(['﻿' + isi], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${nama}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
