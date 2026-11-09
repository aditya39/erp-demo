/* Layar ERP contoh + panel Asisten AI. Tanpa framework, tanpa akses internet. */
const $ = (s, el = document) => el.querySelector(s);
const WARNA = ["#0d9488", "#0f2a44", "#f59e0b", "#6366f1", "#ec4899", "#64748b"];
const SARAN = [
  "Bagaimana tren penjualan Biskuit Kelapa 3 bulan terakhir?",
  "Kenapa HPP Roti Cokelat naik bulan ini? Produk apa lagi yang terdampak?",
  "Berapa lama batas retur untuk roti yang rusak?",
  "Lima customer dengan penjualan terbesar 3 bulan terakhir?",
];

const state = { info: null, pengguna: "budi", mode: "lokal", riwayat: [], sibuk: false };

/* ---------- util ---------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
/* Markdown sederhana. Teks dari model selalu di-escape dulu (cegah XSS). */
function markdown(teks) {
  const inline = (s) => esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<i>$2</i>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  const baris = String(teks || "").split("\n");
  let html = "", list = null;
  const tutup = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const b of baris) {
    const ul = b.match(/^\s*[-*•]\s+(.*)/), ol = b.match(/^\s*\d+[.)]\s+(.*)/);
    if (ul || ol) {
      const jenis = ul ? "ul" : "ol";
      if (list !== jenis) { tutup(); html += `<${jenis}>`; list = jenis; }
      html += `<li>${inline((ul || ol)[1])}</li>`;
    } else if (b.trim() === "") { tutup(); }
    else { tutup(); html += `<p>${inline(b)}</p>`; }
  }
  tutup();
  return html;
}
const detik = (ms) => (ms / 1000).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " dtk";
const angka = (n) => Number(n || 0).toLocaleString("id-ID");

function buatGrafik(canvas, g) {
  const horizontal = !!g.horizontal;
  return new Chart(canvas, {
    type: g.tipe === "bar" ? "bar" : "line",
    data: {
      labels: g.label,
      datasets: g.seri.map((s, i) => ({
        label: s.nama, data: s.data, borderColor: WARNA[i % WARNA.length],
        backgroundColor: g.tipe === "bar" ? WARNA[i % WARNA.length] : WARNA[i % WARNA.length] + "22",
        borderWidth: 2, tension: 0.3, fill: g.tipe !== "bar" && g.seri.length === 1, pointRadius: 3, borderRadius: 4,
      })),
    },
    options: {
      indexAxis: horizontal ? "y" : "x", maintainAspectRatio: false, animation: { duration: 500 },
      plugins: {
        title: { display: !!g.judul, text: g.judul, font: { size: 12, weight: "600" }, color: "#1e293b" },
        legend: { display: g.seri.length > 1, position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { font: { size: 10 }, callback: (v, i, t) => horizontal ? (g.label[v] || "").slice(0, 22) : angka(v) }, grid: { color: "#eef2f6" } },
      },
    },
  });
}

/* SQL yang dijalankan tool (field "query" pada event tool; tidak dikirim ke model). */
function teksSQL(query) {
  return (query || []).map((q, i) => `-- query ${i + 1}${q.params ? " · params " + JSON.stringify(q.params) : ""}\n`
    + q.sql.replace(/\s+(FROM|WHERE|GROUP BY|ORDER BY|LIMIT|JOIN)\b/g, "\n  $1")).join("\n\n");
}

/* Kartu draft sales order: hanya tampilan. Asisten tidak menyimpan; simpan lewat aplikasi ERP. */
function kartuDraft(d, peringatan) {
  const c = d.customer;
  const baris = d.item.map((x) => `<tr><td>${esc(x.nama)}<small>${esc(x.kode)}</small></td>
    <td class="r">${angka(x.qty)} ${esc(x.satuan)}</td><td class="r">${esc(x.harga_daftar_fmt)}</td>
    <td class="r ${x.stok_gudang != null && x.stok_gudang < x.qty ? "down" : ""}">${x.stok_gudang == null ? "—" : angka(x.stok_gudang)}</td></tr>`).join("");
  return `<div class="ds-head"><span class="ds-title">Draft sales order</span><span class="ds-badge">Belum disimpan</span></div>
    <div class="ds-cust"><b>${esc(c.nama)}</b> · ${esc(c.kode)} · ${esc(c.segmen)} · ${esc(c.kota)} · termin ${angka(c.termin_hari)} hari</div>
    <div class="ds-meta">${esc(d.gudang)}${d.gudang_otomatis ? " (otomatis dari kota customer)" : ""}${d.diskon_tambahan ? ` · diskon tambahan ${esc(String(d.diskon_tambahan).replace(".", ","))}%` : ""}${d.catatan ? ` · catatan: ${esc(d.catatan)}` : ""}</div>
    <table class="ds-item"><thead><tr><th>Produk</th><th class="r">Qty</th><th class="r">Harga daftar</th><th class="r">Stok gudang</th></tr></thead><tbody>${baris}</tbody></table>
    <div class="ds-total"><span>Nilai bruto (perkiraan, sebelum diskon)</span><b>${esc(d.nilai_bruto_fmt)}</b></div>
    ${(peringatan || []).map((p) => `<div class="ds-warn">⚠ ${esc(p)}</div>`).join("")}
    <div class="ds-foot">Simpan lewat aplikasi ERP. Harga akhir, diskon segmen, dan persetujuan dihitung oleh sistem ERP.</div>`;
}

/* ---------- kartu jawaban AI: dipakai di chat, mode bandingkan, dan putar rekaman ---------- */
function kartuAI(wadah) {
  const el = document.createElement("div");
  el.className = "msg-ai";
  el.innerHTML = `<div class="steps closed" hidden><div class="steps-head"><span class="sh-l">Langkah agent</span><span class="sh-r">▸</span></div><div class="steps-list"></div></div>
    <div class="thinking"><div class="spinner"></div><span>Menyiapkan…</span></div>
    <div class="charts"></div><div class="drafts"></div><div class="answer"></div><div class="meta"></div>`;
  wadah.appendChild(el);
  const steps = $(".steps", el), list = $(".steps-list", el), thinking = $(".thinking", el);
  let jumlahTool = 0, mode = "", model = "", jawaban = "", peringatan = [];
  $(".steps-head", el).onclick = () => {
    steps.classList.toggle("closed");
    $(".sh-r", el).textContent = steps.classList.contains("closed") ? "▸" : "▾";
  };
  const gulir = () => { wadah.scrollTop = wadah.scrollHeight; };

  function event(ev) {
    if (ev.tipe === "mulai") { mode = ev.mode; model = ev.model; }
    else if (ev.tipe === "berpikir") {
      $("span", thinking).textContent = ev.langkah === 1 ? "Model sedang memilih langkah…" : `Model memproses hasil (langkah ${ev.langkah})…`;
      thinking.hidden = false;
    } else if (ev.tipe === "tool") {
      jumlahTool++;
      steps.hidden = false;
      steps.classList.remove("closed");
      $(".sh-r", el).textContent = "▾";
      const ikon = { ok: "✓", ditolak: "⛔", error: "✗" }[ev.status];
      const sql = teksSQL(ev.query);
      peringatan = ev.hasil?.peringatan || [];
      const row = document.createElement("div");
      row.className = "step " + ev.status;
      row.innerHTML = `<span class="ico">${ikon}</span>
        <div><div class="nm">${esc(ev.nama)}</div><div class="arg">${esc(JSON.stringify(ev.argumen))}</div><div class="rk">${esc(ev.ringkas)}${sql ? ` · ${ev.query.length} query SQL` : ""}</div></div>
        <span class="ms">${angka(ev.durasi_ms)} ms</span>
        ${sql ? `<pre class="sql">${esc(sql)}</pre>` : ""}<pre>${esc(JSON.stringify(ev.hasil, null, 2))}</pre>`;
      row.onclick = () => row.classList.toggle("open");
      list.appendChild(row);
      $(".sh-l", el).textContent = `Langkah agent · ${jumlahTool} tool`;
    } else if (ev.tipe === "draft_so") {
      const box = document.createElement("div");
      box.className = "draft-so";
      box.innerHTML = kartuDraft(ev.draft, peringatan);
      $(".drafts", el).appendChild(box);
    } else if (ev.tipe === "grafik") {
      const box = document.createElement("div");
      box.className = "ai-chart";
      box.innerHTML = "<canvas></canvas>";
      $(".charts", el).appendChild(box);
      buatGrafik($("canvas", box), ev.grafik);
    } else if (ev.tipe === "jawaban") {
      thinking.hidden = true;
      jawaban = ev.teks;
      $(".answer", el).innerHTML = markdown(ev.teks);
    } else if (ev.tipe === "error") {
      thinking.hidden = true;
      $(".answer", el).innerHTML = `<div class="err">${esc(ev.pesan)}</div>`;
    } else if (ev.tipe === "selesai") {
      thinking.hidden = true;
      if (jumlahTool) { steps.classList.add("closed"); $(".sh-r", el).textContent = "▸"; }
      $(".meta", el).innerHTML = `<span class="badge ${mode}">${mode === "lokal" ? "Lokal" : "Cloud"}</span>
        <span>${esc(model)}</span><span>· ${detik(ev.durasi_ms)}</span>
        <span>· ${angka(ev.token_masuk + ev.token_keluar)} token</span>`;
    }
    gulir();
  }
  return { el, event, jawaban: () => jawaban };
}

/* ---------- streaming dari server (Server-Sent Events lewat fetch) ---------- */
async function alirkan(pesan, mode, riwayat, onEvent) {
  const resp = await fetch("/api/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pesan, pengguna: state.pengguna, mode, riwayat }),
  });
  if (!resp.ok) { onEvent({ tipe: "error", pesan: `Server error ${resp.status}` }); onEvent({ tipe: "selesai", durasi_ms: 0, token_masuk: 0, token_keluar: 0 }); return; }
  const reader = resp.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const blok = buf.slice(0, i); buf = buf.slice(i + 2);
      for (const line of blok.split("\n")) if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

/* ---------- chat ---------- */
function kosongkan() {
  state.riwayat = [];
  const u = state.info.pengguna.find((p) => p.kode === state.pengguna);
  $("#messages").innerHTML = `<div class="empty"><b>Halo, ${esc(u.nama.split(" ")[0])} 👋</b>
    Tanyakan data penjualan, HPP, atau kebijakan perusahaan.<br>Asisten hanya membaca data sesuai hak akses Anda
    (${esc(u.izin.join(", "))}).</div>`;
  $("#chips").innerHTML = SARAN.map((s) => `<button class="chip">${esc(s)}</button>`).join("");
  $("#chips").querySelectorAll(".chip").forEach((c) => (c.onclick = () => kirim(c.textContent)));
}

async function kirim(teks) {
  teks = (teks || "").trim();
  if (!teks || state.sibuk) return;
  state.sibuk = true;
  $("#kirim").disabled = true;
  $("#input").value = "";
  const msgs = $("#messages");
  $(".empty", msgs)?.remove();
  $("#chips").innerHTML = "";
  const u = document.createElement("div");
  u.className = "msg-user"; u.textContent = teks;
  msgs.appendChild(u);
  const kartu = kartuAI(msgs);
  try {
    await alirkan(teks, state.mode, state.riwayat.slice(-6), kartu.event);
    if (kartu.jawaban()) state.riwayat.push({ role: "user", content: teks }, { role: "assistant", content: kartu.jawaban() });
  } catch (e) {
    kartu.event({ tipe: "error", pesan: "Tidak dapat terhubung ke server aplikasi: " + e.message });
    kartu.event({ tipe: "selesai", durasi_ms: 0, token_masuk: 0, token_keluar: 0 });
  }
  state.sibuk = false;
  $("#kirim").disabled = false;
  $("#input").focus();
}

/* ---------- bandingkan lokal vs cloud ---------- */
async function bandingkan() {
  const teks = $("#input").value.trim() || [...state.riwayat].reverse().find((m) => m.role === "user")?.content || SARAN[1];
  $("#banding-q").textContent = "❝ " + teks;
  const kolom = { lokal: $("#kolom-lokal"), cloud: $("#kolom-cloud") };
  for (const [mode, el] of Object.entries(kolom)) {
    const info = state.info[mode];
    el.innerHTML = `<div class="kolom-head"><span class="badge ${mode}">${mode === "lokal" ? "Lokal" : "Cloud"} · ${esc(info.model)}</span><span class="kolom-stat"></span></div>`;
  }
  $("#modal-banding").classList.add("open");
  await Promise.all(Object.entries(kolom).map(async ([mode, el]) => {
    if (!state.info[mode].aktif) { el.insertAdjacentHTML("beforeend", `<div class="err">Model ${mode} belum dikonfigurasi di .env</div>`); return; }
    const kartu = kartuAI(el);
    try { await alirkan(teks, mode, [], kartu.event); }
    catch (e) { kartu.event({ tipe: "error", pesan: e.message }); }
  }));
}

/* ---------- putar rekaman (cadangan bila demo live bermasalah) ---------- */
async function bukaRekaman() {
  const daftar = await (await fetch("/api/rekaman")).json();
  $("#rekaman-list").innerHTML = daftar.length ? daftar.map((r) =>
    `<button class="rekaman-item" data-file="${esc(r.file)}">${esc(r.pesan)}<small>${esc(r.pengguna)} · ${esc(r.mode)} · ${esc(r.file.slice(0, 15))}</small></button>`).join("")
    : `<div class="empty">Belum ada rekaman. Setiap pertanyaan yang dijalankan otomatis direkam ke folder rekaman/.</div>`;
  $("#rekaman-list").querySelectorAll(".rekaman-item").forEach((b) => (b.onclick = () => putar(b.dataset.file)));
  $("#modal-rekaman").classList.add("open");
}
async function putar(file) {
  $("#modal-rekaman").classList.remove("open");
  const r = await (await fetch("/api/rekaman/" + encodeURIComponent(file))).json();
  if (r.pengguna !== state.pengguna) { state.pengguna = r.pengguna; $("#pengguna").value = r.pengguna; await muatDashboard(); }
  const msgs = $("#messages");
  $(".empty", msgs)?.remove();
  $("#chips").innerHTML = "";
  const u = document.createElement("div");
  u.className = "msg-user"; u.textContent = r.pesan;
  msgs.appendChild(u);
  const kartu = kartuAI(msgs);
  const kecepatan = Number(new URLSearchParams(location.search).get("kecepatan") || 1);
  let sebelum = 0;
  for (const ev of r.events) {
    await new Promise((ok) => setTimeout(ok, Math.min(ev.t - sebelum, 8000) / kecepatan));
    sebelum = ev.t;
    kartu.event(ev);
  }
}

/* ---------- dashboard ERP ---------- */
let grafikOmzet;
async function muatDashboard() {
  const d = await (await fetch("/api/dashboard?pengguna_kode=" + state.pengguna)).json();
  $("#kartu").innerHTML = d.kartu.map((k) => `<div class="card ${k.terkunci ? "locked" : ""}"><div class="lbl">${esc(k.label)}${k.terkunci ? " 🔒" : ""}</div>
    <div class="val" title="${esc(k.nilai)}">${esc(k.nilai)}</div><div class="cat">${esc(k.catatan)}</div></div>`).join("");
  $("#judul-bulan").textContent = d.judul_bulan;
  $("#tabel-produk tbody").innerHTML = d.produk.map((p) => `<tr><td>${esc(p.produk)}</td><td>${esc(p.kategori)}</td>
    <td class="r">${angka(p.qty)}</td><td class="r">${esc(p.nilai_fmt)}</td>
    <td class="r ${p.perubahan.startsWith("+") ? "up" : p.perubahan.startsWith("-") ? "down" : ""}">${esc(p.perubahan)}</td></tr>`).join("");
  grafikOmzet?.destroy();
  grafikOmzet = buatGrafik($("#grafik-omzet"), { tipe: "bar", label: d.grafik.label, seri: [{ nama: "Omzet (Rp juta)", data: d.grafik.data }] });
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
  const i = state.info[mode];
  $("#model-line").innerHTML = mode === "lokal"
    ? `<span class="badge lokal">● Lokal</span> ${esc(i.model)} · berjalan di perangkat/server sendiri, data tidak keluar`
    : `<span class="badge cloud">● Cloud</span> ${esc(i.model)} · lewat internet ke penyedia model`;
}

function statusJaringan() {
  const on = navigator.onLine;
  $("#net").classList.toggle("off", !on);
  $("#net-label").textContent = on ? "Online" : "Offline · AI lokal tetap berjalan";
}

async function init() {
  state.info = await (await fetch("/api/info")).json();
  $("#perusahaan").textContent = state.info.perusahaan;
  $("#posisi").textContent = "Posisi data: " + new Date(state.info.tanggal_posisi).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  $("#pengguna").innerHTML = state.info.pengguna.map((p) => `<option value="${p.kode}">${esc(p.nama)} — ${esc(p.jabatan)}</option>`).join("");
  $("#pengguna").value = state.pengguna;
  $("#pengguna").onchange = async (e) => { state.pengguna = e.target.value; kosongkan(); await muatDashboard(); };
  const cloudBtn = $('#mode button[data-mode="cloud"]');
  cloudBtn.disabled = !state.info.cloud.aktif;
  if (!state.info.cloud.aktif) cloudBtn.title = state.info.cloud.penyedia === "claude-code"
    ? "Instal Claude Code lalu login (claude → /login), atau atur CLOUD_* di .env"
    : "Isi CLOUD_BASE_URL, CLOUD_MODEL, CLOUD_API_KEY di .env";
  document.querySelectorAll("#mode button").forEach((b) => (b.onclick = () => !b.disabled && setMode(b.dataset.mode)));
  setMode("lokal");
  $("#menu-btn").onclick = (e) => { e.stopPropagation(); $("#menu").classList.toggle("open"); };
  document.addEventListener("click", () => $("#menu").classList.remove("open"));
  $("#menu").querySelectorAll("button").forEach((b) => (b.onclick = () => {
    $("#menu").classList.remove("open");
    ({ bandingkan, rekaman: bukaRekaman, bersihkan: kosongkan })[b.dataset.aksi]();
  }));
  document.querySelectorAll("[data-tutup]").forEach((b) => (b.onclick = () => b.closest(".modal").classList.remove("open")));
  $("#composer").onsubmit = (e) => { e.preventDefault(); kirim($("#input").value); };
  $("#input").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); kirim($("#input").value); } };
  window.addEventListener("online", statusJaringan);
  window.addEventListener("offline", statusJaringan);
  statusJaringan();
  kosongkan();
  await muatDashboard();
  const q = new URLSearchParams(location.search);
  if (q.get("putar")) putar(q.get("putar"));
}
init();
