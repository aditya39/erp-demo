import { Component, effect, ElementRef, inject, input } from '@angular/core';
import {
  AlertTriangle, ArrowDownRight, ArrowLeftRight, ArrowRight, ArrowUpRight, Ban, Bell, BookOpen, Boxes, Calendar, Check,
  CheckCheck, ChevronDown, ChevronRight, ChevronsUpDown, CircleAlert, CircleCheck, CircleDashed, CircleDot, CirclePause,
  CircleX, Clock, Cloud, Columns2, Command, Copy, Database, Download, Ellipsis, FileText, FlaskConical, Hourglass, Inbox,
  Info, LayoutDashboard, LineChart, ListChecks, Lock, LogOut, Moon, Package, PanelLeft, PanelRightClose, Pencil, Play,
  Plus, Printer, Receipt, ScrollText, Search, Send, Settings2, ShieldCheck, ShoppingBasket, SlidersHorizontal, Sparkles,
  SquarePen, Sun, Tag, Tags, Trash2, TrendingDown, TrendingUp, User, UserCheck, Users, Wallet, Banknote, Workflow, Wrench,
  X, BarChart3, IconNode, Wifi, WifiOff, History, Store, Truck, FileCheck2, CornerDownLeft,
} from 'lucide';

/** Ikon yang dipakai aplikasi (Lucide, lisensi ISC). Nama pendek → node SVG. */
const IKON: Record<string, IconNode> = {
  dashboard: LayoutDashboard, so: SquarePen, faktur: Receipt, customer: Users, laporan: BarChart3, piutang: Wallet,
  bayar: Banknote, stok: Package, mutasi: ArrowLeftRight, produk: Tags, bahan: ShoppingBasket, hpp: LineChart,
  dokumen: BookOpen, akses: ShieldCheck, aktivitas: History, asisten: Sparkles, cari: Search, bel: Bell, plus: Plus,
  panah: ArrowRight, kanan: ChevronRight, bawah: ChevronDown, pilih: ChevronsUpDown, naik: ArrowUpRight, turun: ArrowDownRight,
  centang: Check, centang2: CheckCheck, ok: CircleCheck, x: X, gagal: CircleX, tolak: Ban, kunci: Lock, info: Info,
  awas: AlertTriangle, galat: CircleAlert, jam: Clock, pasir: Hourglass, jeda: CirclePause, titik: CircleDot, kosong: CircleDashed,
  kalender: Calendar, cetak: Printer, unduh: Download, edit: Pencil, hapus: Trash2, tag: Tag, user: User, setuju: UserCheck,
  keluar: LogOut, bulan: Moon, matahari: Sun, sidebar: PanelLeft, tutup_panel: PanelRightClose, lainnya: Ellipsis,
  kirim: Send, putar: Play, banding: Columns2, alat: Wrench, db: Database, awan: Cloud, salin: Copy, inbox: Inbox,
  daftar: ListChecks, alur: Workflow, atur: Settings2, filter: SlidersHorizontal, perintah: Command, gudang: Boxes,
  trend_naik: TrendingUp, trend_turun: TrendingDown, teks: FileText, kebijakan: ScrollText, uji: FlaskConical,
  online: Wifi, offline: WifiOff, toko: Store, kirim_barang: Truck, dokumen_ok: FileCheck2, enter: CornerDownLeft,
};

const SVG = 'http://www.w3.org/2000/svg';

@Component({
  selector: 'app-ikon',
  template: '',
  host: { class: 'ikon', '[style.width.px]': 'ukuran()', '[style.height.px]': 'ukuran()' },
  styles: `:host { display: inline-flex; flex: none; align-items: center; justify-content: center; line-height: 0; }
           :host ::ng-deep svg { width: 100%; height: 100%; }`,
})
export class Ikon {
  readonly n = input.required<string>();
  readonly ukuran = input(16);
  readonly tebal = input(1.75);
  private el = inject(ElementRef<HTMLElement>);

  constructor() {
    effect(() => {
      const host = this.el.nativeElement as HTMLElement;
      const node = IKON[this.n()] ?? CircleDashed;
      const svg = document.createElementNS(SVG, 'svg');
      for (const [k, v] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
        'stroke-width': String(this.tebal()), 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) {
        svg.setAttribute(k, v);
      }
      for (const [tag, attrs] of node) {
        const child = document.createElementNS(SVG, tag);
        for (const [k, v] of Object.entries(attrs)) child.setAttribute(k, String(v));
        svg.appendChild(child);
      }
      host.replaceChildren(svg);
    });
  }
}
