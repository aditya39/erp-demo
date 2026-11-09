import { Pipe, PipeTransform } from '@angular/core';
import { angka, bulan, persen, relatif, rupiah, rupiahRingkas, tanggal } from './format';

@Pipe({ name: 'rupiah' })
export class RupiahPipe implements PipeTransform {
  transform(n: number | null | undefined, ringkas = false): string {
    return ringkas ? rupiahRingkas(n) : rupiah(n);
  }
}

@Pipe({ name: 'angka' })
export class AngkaPipe implements PipeTransform {
  transform(n: number | null | undefined, desimal = 0): string {
    return angka(n, desimal);
  }
}

@Pipe({ name: 'persen' })
export class PersenPipe implements PipeTransform {
  transform(n: number | null | undefined, tanda = true, desimal = 1): string {
    return persen(n, tanda, desimal);
  }
}

@Pipe({ name: 'tgl' })
export class TanggalPipe implements PipeTransform {
  transform(s: string | null | undefined, gaya: 'pendek' | 'panjang' | 'waktu' = 'pendek'): string {
    return tanggal(s, gaya);
  }
}

@Pipe({ name: 'bulan' })
export class BulanPipe implements PipeTransform {
  transform(s: string | null | undefined, pendek = false): string {
    return bulan(s, pendek);
  }
}

@Pipe({ name: 'relatif' })
export class RelatifPipe implements PipeTransform {
  transform(s: string | null | undefined): string {
    return relatif(s);
  }
}

export const PIPES = [RupiahPipe, AngkaPipe, PersenPipe, TanggalPipe, BulanPipe, RelatifPipe];
