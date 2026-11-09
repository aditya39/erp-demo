import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, Injectable, LOCALE_ID, provideBrowserGlobalErrorListeners } from '@angular/core';
import { registerLocaleData } from '@angular/common';
import localeId from '@angular/common/locales/id';
import { provideRouter, RouterStateSnapshot, TitleStrategy, withComponentInputBinding } from '@angular/router';
import { Title } from '@angular/platform-browser';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { routes } from './app.routes';
import { galatInterceptor } from './core/api';
import { TemaNusantara } from './core/tema';

registerLocaleData(localeId);

@Injectable({ providedIn: 'root' })
class JudulHalaman extends TitleStrategy {
  constructor(private readonly title: Title) {
    super();
  }
  override updateTitle(state: RouterStateSnapshot): void {
    const t = this.buildTitle(state);
    this.title.setTitle(t ? `${t} · Nusantara Rasa ERP` : 'Nusantara Rasa ERP');
  }
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([galatInterceptor])),
    { provide: LOCALE_ID, useValue: 'id' },
    { provide: TitleStrategy, useClass: JudulHalaman },
    MessageService,
    ConfirmationService,
    providePrimeNG({
      theme: { preset: TemaNusantara, options: { darkModeSelector: '.app-dark', cssLayer: { name: 'primeng', order: 'base, primeng, app' } } },
      ripple: false,
      translation: {
        accept: 'Ya', reject: 'Batal', dayNames: ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'],
        dayNamesShort: ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab'], dayNamesMin: ['Mi', 'Se', 'Sl', 'Ra', 'Ka', 'Ju', 'Sa'],
        monthNames: ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'],
        monthNamesShort: ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        today: 'Hari ini', clear: 'Hapus', emptyMessage: 'Tidak ada data', emptySearchMessage: 'Tidak ditemukan',
        firstDayOfWeek: 1, dateFormat: 'dd/mm/yy',
      },
    }),
  ],
};
