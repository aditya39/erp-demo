import { Pipe, PipeTransform } from '@angular/core';

/** Escape HTML lebih dulu: teks dari model AI / dokumen tidak pernah dirender mentah (cegah XSS). */
function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}

function inline(s: string): string {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, '$1<i>$2</i>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

/** Markdown sederhana: judul, paragraf, daftar, tebal/miring, kode inline. */
export function markdown(teks: string): string {
  let html = '';
  let list: 'ul' | 'ol' | null = null;
  const tutup = () => {
    if (list) html += `</${list}>`;
    list = null;
  };
  for (const b of (teks || '').split('\n')) {
    const h = b.match(/^(#{1,4})\s+(.*)/);
    const ul = b.match(/^\s*[-*•]\s+(.*)/);
    const ol = b.match(/^\s*\d+[.)]\s+(.*)/);
    if (h) {
      tutup();
      const lv = Math.min(h[1].length + 1, 5);
      html += `<h${lv}>${inline(h[2])}</h${lv}>`;
    } else if (ul || ol) {
      const jenis = ul ? 'ul' : 'ol';
      if (list !== jenis) {
        tutup();
        html += `<${jenis}>`;
        list = jenis;
      }
      html += `<li>${inline((ul || ol)![1])}</li>`;
    } else if (b.trim() === '') {
      tutup();
    } else {
      tutup();
      html += `<p>${inline(b)}</p>`;
    }
  }
  tutup();
  return html;
}

@Pipe({ name: 'markdown' })
export class MarkdownPipe implements PipeTransform {
  transform(teks: string | null | undefined): string {
    return markdown(teks ?? '');
  }
}
