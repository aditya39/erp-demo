import { Directive, ElementRef, inject, OnDestroy } from '@angular/core';
import { InputNumber } from 'primeng/inputnumber';

/**
 * Untuk p-inputnumber berlocale "id-ID" (koma = desimal): titik juga diterima sebagai tanda desimal.
 * Tanpa ini PrimeNG menganggap titik pemisah ribuan dan membuangnya, sehingga "1.5" diam-diam menjadi 15.
 * Hasil: "1,5" dan "1.5" -> 1,5; "2" -> 2 (diketik maupun ditempel).
 */
@Directive({ selector: 'p-inputnumber[titikDesimal]' })
export class TitikDesimal implements OnDestroy {
  private komp = inject(InputNumber);
  private host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;

  // fase capture: berjalan sebelum handler PrimeNG pada <input> di dalamnya
  private ketik = (e: KeyboardEvent) => {
    if (e.key !== '.' || e.code === 'NumpadDecimal' || e.ctrlKey || e.metaKey || e.altKey) return;
    e.preventDefault();   // keypress tidak terjadi -> titik tidak dibuang; sisipkan koma desimal
    this.komp.insert(e, ',', { isDecimalSign: true, isMinusSign: false });
  };

  private tempel = (e: ClipboardEvent) => {
    const teks = (e.clipboardData?.getData('text') ?? '').replace(/[\s%]/g, '');
    if (!/^\d+[.,]\d+$/.test(teks)) return;   // selain angka desimal sederhana: perilaku bawaan PrimeNG
    e.preventDefault();
    e.stopPropagation();
    const n = this.komp.validateValue(Math.round(Number(teks.replace(',', '.')) * 100) / 100);
    this.komp.handleOnInput(e, this.komp.input.nativeElement.value, n);
  };

  constructor() {
    this.host.addEventListener('keydown', this.ketik, true);
    this.host.addEventListener('paste', this.tempel, true);
  }

  ngOnDestroy(): void {
    this.host.removeEventListener('keydown', this.ketik, true);
    this.host.removeEventListener('paste', this.tempel, true);
  }
}
