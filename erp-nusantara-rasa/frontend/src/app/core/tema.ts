import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

/** Tema PrimeNG: Aura dengan warna utama teal (identitas Nusantara Rasa). */
export const TemaNusantara = definePreset(Aura, {
  semantic: {
    primary: {
      50: '{teal.50}', 100: '{teal.100}', 200: '{teal.200}', 300: '{teal.300}', 400: '{teal.400}',
      500: '{teal.500}', 600: '{teal.600}', 700: '{teal.700}', 800: '{teal.800}', 900: '{teal.900}', 950: '{teal.950}',
    },
    colorScheme: {
      light: {
        primary: { color: '{teal.600}', contrastColor: '#ffffff', hoverColor: '{teal.700}', activeColor: '{teal.800}' },
        surface: {
          0: '#ffffff', 50: '{slate.50}', 100: '{slate.100}', 200: '{slate.200}', 300: '{slate.300}', 400: '{slate.400}',
          500: '{slate.500}', 600: '{slate.600}', 700: '{slate.700}', 800: '{slate.800}', 900: '{slate.900}', 950: '{slate.950}',
        },
      },
      dark: {
        primary: { color: '{teal.400}', contrastColor: '{slate.950}', hoverColor: '{teal.300}', activeColor: '{teal.200}' },
        surface: {
          0: '#ffffff', 50: '{slate.50}', 100: '{slate.100}', 200: '{slate.200}', 300: '{slate.300}', 400: '{slate.400}',
          500: '{slate.500}', 600: '{slate.600}', 700: '{slate.700}', 800: '{slate.800}', 900: '#111a2e', 950: '#0b1220',
        },
      },
    },
  },
});
