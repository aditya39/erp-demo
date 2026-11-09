/** Format angka, rupiah, dan tanggal gaya Indonesia. */
const BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];

export function angka(n: number | null | undefined, desimal = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '–';
  return Number(n).toLocaleString('id-ID', { minimumFractionDigits: desimal, maximumFractionDigits: desimal });
}

export function rupiah(n: number | null | undefined): string {
  if (n === null || n === undefined) return '–';
  return (n < 0 ? '-Rp ' : 'Rp ') + angka(Math.abs(n));
}

/** Rp 2,67 M · Rp 281,2 jt · Rp 950 rb */
export function rupiahRingkas(n: number | null | undefined): string {
  if (n === null || n === undefined) return '–';
  const a = Math.abs(n);
  const tanda = n < 0 ? '-' : '';
  if (a >= 1e9) return `${tanda}Rp ${angka(a / 1e9, 2)} M`;
  if (a >= 1e6) return `${tanda}Rp ${angka(a / 1e6, 1)} jt`;
  if (a >= 1e3) return `${tanda}Rp ${angka(a / 1e3, 0)} rb`;
  return `${tanda}Rp ${angka(a)}`;
}

export function persen(n: number | null | undefined, tanda = true, desimal = 1): string {
  if (n === null || n === undefined) return '–';
  return (tanda && n > 0 ? '+' : '') + angka(n, desimal) + '%';
}

function keTanggal(s: string | Date): Date {
  if (s instanceof Date) return s;
  return s.length <= 10 ? new Date(s + 'T00:00:00') : new Date(s);
}

export function tanggal(s: string | Date | null | undefined, gaya: 'pendek' | 'panjang' | 'waktu' = 'pendek'): string {
  if (!s) return '–';
  const d = keTanggal(s);
  if (gaya === 'panjang') return d.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  if (gaya === 'waktu')
    return d.toLocaleString('id-ID', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).replace('.', ':');
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function bulan(s: string | null | undefined, pendek = false): string {
  if (!s) return '–';
  const d = keTanggal(s);
  return pendek ? `${BULAN[d.getMonth()].slice(0, 3)} ${String(d.getFullYear()).slice(2)}` : `${BULAN[d.getMonth()]} ${d.getFullYear()}`;
}

export function relatif(s: string | null | undefined): string {
  if (!s) return '–';
  const detik = (Date.now() - keTanggal(s).getTime()) / 1000;
  if (detik < 60) return 'baru saja';
  if (detik < 3600) return `${Math.floor(detik / 60)} menit lalu`;
  if (detik < 86400) return `${Math.floor(detik / 3600)} jam lalu`;
  if (detik < 86400 * 7) return `${Math.floor(detik / 86400)} hari lalu`;
  return tanggal(s);
}

export function inisial(nama: string): string {
  return nama.split(/\s+/).slice(0, 2).map((k) => k[0]).join('').toUpperCase();
}
