import { inject, Injectable, signal } from '@angular/core';
import { Api } from '../core/api';
import { DraftSO, EventAI, GrafikAI, PayloadSO, QueryAI } from '../core/model';

export interface LangkahAI {
  nama: string;
  argumen: Record<string, unknown>;
  status: 'ok' | 'ditolak' | 'error';
  ringkas: string;
  durasi_ms: number;
  hasil: unknown;
  query?: QueryAI[];
}

export interface PesanChat {
  id: number;
  peran: 'user' | 'ai';
  teks: string;
  langkah: LangkahAI[];
  grafik: GrafikAI[];
  draft: DraftSO[];
  fase: string;
  selesai: boolean;
  error?: string;
  mode?: string;
  model?: string;
  durasi_ms?: number;
  token?: number;
  rekaman?: string;
}

export interface InfoAI {
  lokal: { model: string; aktif: boolean };
  cloud: { model: string; aktif: boolean; alasan?: string };
  tools: { nama: string; izin: string; label_izin: string; boleh: boolean; deskripsi: string }[];
  maks_langkah: number;
}

export interface Rekaman {
  sumber: 'demo' | 'erp';
  file: string;
  pesan: string;
  pengguna: string;
  mode: string;
  durasi_ms: number;
}

let urut = 0;

export function pesanAIBaru(rekaman?: string): PesanChat {
  return { id: ++urut, peran: 'ai', teks: '', langkah: [], grafik: [], draft: [], fase: 'Menghubungi asisten…', selesai: false, rekaman };
}

/** Terapkan satu event agent ke pesan (fungsi murni, dipakai chat, mode bandingkan, dan putar rekaman). */
export function terapkanEvent(p: PesanChat, ev: EventAI): PesanChat {
  switch (ev.tipe) {
    case 'mulai':
      return { ...p, mode: ev['mode'] as string, model: ev['model'] as string };
    case 'berpikir': {
      const n = ev['langkah'] as number;
      return { ...p, fase: n === 1 ? 'Memahami pertanyaan & memilih tool…' : `Membaca hasil tool · langkah ${n}…` };
    }
    case 'tool':
      return {
        ...p,
        langkah: [...p.langkah, {
          nama: ev['nama'] as string, argumen: (ev['argumen'] as Record<string, unknown>) ?? {},
          status: ev['status'] as LangkahAI['status'], ringkas: ev['ringkas'] as string,
          durasi_ms: ev['durasi_ms'] as number, hasil: ev['hasil'], query: ev['query'] as QueryAI[] | undefined,
        }],
      };
    case 'grafik':
      return { ...p, grafik: [...p.grafik, ev['grafik'] as GrafikAI] };
    case 'draft_so':
      // draft transaksi: hanya ditampilkan; menyimpan tetap lewat tombol Simpan (sesi & izin user)
      return { ...p, draft: [...(p.draft ?? []), ev['draft'] as DraftSO] };
    case 'jawaban':
      return { ...p, teks: ev['teks'] as string, fase: '' };
    case 'error':
      return { ...p, error: ev['pesan'] as string, fase: '' };
    case 'selesai':
      return {
        ...p, selesai: true, fase: '', durasi_ms: ev['durasi_ms'] as number,
        token: ((ev['token_masuk'] as number) ?? 0) + ((ev['token_keluar'] as number) ?? 0),
      };
  }
  return p;
}

/** Kirim pertanyaan ke /api/ai/chat dan alirkan event (Server-Sent Events lewat fetch). */
export async function alirkan(pesan: string, mode: string, riwayat: { role: string; content: string }[],
                              onEvent: (ev: EventAI) => void): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch('/api/ai/chat', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pesan, mode, riwayat }),
    });
  } catch {
    onEvent({ tipe: 'error', pesan: 'Server ERP tidak dapat dihubungi.' });
    onEvent({ tipe: 'selesai', durasi_ms: 0 });
    return;
  }
  if (!resp.ok || !resp.body) {
    const b = await resp.json().catch(() => ({}));
    onEvent({ tipe: 'error', pesan: b.pesan ?? `Server error ${resp.status}` });
    onEvent({ tipe: 'selesai', durasi_ms: 0 });
    return;
  }
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const blok = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const baris of blok.split('\n')) if (baris.startsWith('data: ')) onEvent(JSON.parse(baris.slice(6)));
    }
  }
}

/** Status panel Asisten AI (dipakai bersama oleh panel, topbar, dan tombol "Tanya AI" di halaman). */
@Injectable({ providedIn: 'root' })
export class Asisten {
  private api = inject(Api);
  readonly terbuka = signal(false);
  readonly pesan = signal<PesanChat[]>([]);
  readonly sibuk = signal(false);
  readonly mode = signal<'lokal' | 'cloud'>('lokal');
  readonly info = signal<InfoAI | null>(null);
  readonly draf = signal('');
  /** Draft SO yang dibawa ke form "Sales order baru" (tombol "Ubah di form" di kartu draft). */
  readonly draftForm = signal<PayloadSO | null>(null);

  async muatInfo(): Promise<void> {
    if (!this.info()) this.info.set(await this.api.get<InfoAI>('/ai/info'));
  }

  buka(): void {
    this.terbuka.set(true);
    this.muatInfo().catch(() => undefined);
  }

  alih(): void {
    if (this.terbuka()) this.terbuka.set(false);
    else this.buka();
  }

  bersihkan(): void {
    if (!this.sibuk()) this.pesan.set([]);
  }

  private ubah(id: number, f: (p: PesanChat) => PesanChat): void {
    this.pesan.update((list) => list.map((p) => (p.id === id ? f(p) : p)));
  }

  /** Buka panel lalu kirim pertanyaan (dipakai juga oleh tombol "Tanya AI" di halaman lain). */
  async tanya(teks: string): Promise<void> {
    teks = teks.trim();
    this.buka();
    if (!teks || this.sibuk()) return;
    this.sibuk.set(true);
    this.draf.set('');
    const riwayat = this.pesan()
      .filter((p) => p.selesai || p.peran === 'user')
      .filter((p) => !p.rekaman && (p.peran === 'user' || p.teks))
      .slice(-6)
      .map((p) => ({ role: p.peran === 'user' ? 'user' : 'assistant', content: p.teks }));
    const ai = pesanAIBaru();
    this.pesan.update((l) => [...l, { ...pesanAIBaru(), peran: 'user', teks, selesai: true, fase: '' }, ai]);
    try {
      await alirkan(teks, this.mode(), riwayat, (ev) => this.ubah(ai.id, (p) => terapkanEvent(p, ev)));
    } finally {
      this.ubah(ai.id, (p) => (p.selesai ? p : { ...p, selesai: true, fase: '' }));
      this.sibuk.set(false);
    }
  }

  daftarRekaman(): Promise<Rekaman[]> {
    return this.api.get<Rekaman[]>('/ai/rekaman');
  }

  /** Putar ulang rekaman demo (cadangan bila model lokal lambat/bermasalah saat presentasi). */
  async putar(r: Rekaman, kecepatan = 1): Promise<void> {
    if (this.sibuk()) return;
    this.buka();
    this.sibuk.set(true);
    try {
      const data = await this.api.get<{ pesan: string; events: EventAI[] }>(
        `/ai/rekaman/${r.sumber}/${encodeURIComponent(r.file)}`);
      const ai = pesanAIBaru(r.file);
      this.pesan.update((l) => [...l, { ...pesanAIBaru(r.file), peran: 'user', teks: data.pesan, selesai: true, fase: '' }, ai]);
      let sebelum = 0;
      for (const ev of data.events) {
        const t = ev.t ?? sebelum;
        await new Promise((ok) => setTimeout(ok, Math.min(Math.max(t - sebelum, 0), 8000) / kecepatan));
        sebelum = t;
        this.ubah(ai.id, (p) => terapkanEvent(p, ev));
      }
    } finally {
      this.sibuk.set(false);
    }
  }
}
