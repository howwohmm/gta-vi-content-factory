// GTA VI Content Factory — local web app. Plain JS, no build step.
const $ = (s, el = document) => el.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const media = (p) => "/media?path=" + encodeURIComponent(p);
let S = null;            // last /api/state
let view = location.hash.slice(1) || "home";
let wizardStep = 0;
let openProject = null;

async function api(path, body) {
  const opt = body instanceof FormData
    ? { method: "POST", body, headers: { "x-gvcf": "1" } }
    : body !== undefined ? { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json", "x-gvcf": "1" } } : {};
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || j.error || r.statusText);
  return j;
}
function toast(msg, ms = 4000) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), ms);
}
const fmtMin = (s) => (s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m` : `${Math.round(s / 60)} min`);
const countdown = (until) => { if (!until) return ""; const s = Math.max(0, Math.round(until - Date.now() / 1000)); return s > 3600 ? `${Math.floor(s/3600)}h ${Math.floor(s%3600/60)}m` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

// ------------------------------------------------------------ shell
const NAV = [
  ["home", "🏠", "Home"], ["videos", "🎮", "Videos"], ["review", "✅", "Review"], ["accounts", "🔗", "Accounts"],
  ["covers", "🖼️", "Covers"], ["youtube", "▶️", "YouTube"], ["settings", "⚙️", "Settings"],
];
function shell(content) {
  const toReview = S.projects.reduce((a, p) => a + Math.max(0, p.reels - p.approved), 0);
  return `<div class="app"><nav>
    <div class="logo">CONTENT FACTORY<span>${esc(S.settings.game || "GTA VI")} EDITION</span></div>
    ${NAV.map(([id, ic, label]) => `<button class="${view === id ? "on" : ""}" onclick="go('${id}')">${ic} ${label}${id === "review" && toReview ? `<span class="badge">${toReview}</span>` : ""}</button>`).join("")}
    <div style="position:absolute;bottom:18px;left:14px;right:14px" class="muted">
      <button class="btn small" onclick="openFolder('home')">📂 Open factory folder</button>
    </div></nav><main>${content}</main></div>`;
}
function go(v) { view = v; location.hash = v; render(); }
window.addEventListener("hashchange", () => { view = location.hash.slice(1) || "home"; render(); });
async function openFolder(f) { const r = await api("/api/open", { folder: f }); toast("Opened " + r.path); }

// ------------------------------------------------------------ onboarding wizard
const STEPS = ["Your page", "Tools", "AI", "Accounts", "Covers", "First video"];
function wizard() {
  const s = S.settings;
  const dots = `<div class="dots">${STEPS.map((_, i) => `<i class="${i <= wizardStep ? "on" : ""}"></i>`).join("")}</div>`;
  const nav = (next = "Continue", canSkip = false) => `<div class="row" style="margin-top:18px">
      ${wizardStep ? `<button class="btn" onclick="wizardStep--;render()">Back</button>` : ""}<span class="spacer"></span>
      ${canSkip ? `<button class="btn" onclick="wizardStep++;render()">Skip for now</button>` : ""}
      <button class="btn primary" onclick="wizardNext()">${next}</button></div>`;
  let body = "";
  if (wizardStep === 0) body = `
    <h1>Let's set up your content factory 🎮</h1><p class="sub">Five minutes. Everything runs on your Mac; nothing is shared with us.</p>
    <div class="card"><label>Your page's name (as people see it)</label><input id="w_page" value="${esc(s.page_name)}" placeholder="Page for GTA VI">
    <label>Your handle on Instagram / Threads (no @)</label><input id="w_handle" value="${esc(s.handle)}" placeholder="pageforgtavi">
    <label>Text on top of every reel</label><input id="w_header" value="${esc(s.header)}">
    <p class="muted">Reels look like: <b>${esc(s.header)}</b>, if you wreck Brian's seaplane, he's waiting at the dock to ask what happened 😭</p></div>
    <div class="card"><b>Only use footage you're allowed to use.</b><p class="muted" style="margin:6px 0 0">Best: record or stream your own gameplay. Clipping other creators needs their permission (many run clipping programs) and a credit. Copyright strikes kill pages fast.</p></div>${nav()}`;
  if (wizardStep === 1) {
    const t = S.tools, line = (k, label, fix) => `<div class="row" style="padding:6px 0"><span class="pill ${t[k] ? "ok" : "no"}">${t[k] ? "ready" : "missing"}</span> ${label}<span class="spacer"></span>${t[k] ? "" : `<span class="muted">${fix}</span>`}</div>`;
    body = `<h1>Checking your Mac</h1><p class="sub">The installer sets these up. If something says missing, run <code>./install.sh</code> again.</p>
      <div class="card">${line("ffmpeg", "ffmpeg (cuts and renders video)", "brew install ffmpeg")}${line("yt-dlp", "yt-dlp (downloads your streams from links)", "brew install yt-dlp")}${line("cloudflared", "cloudflared (Threads needs a temporary link to your video)", "brew install cloudflared")}${line("ollama", "Ollama (optional: free local AI)", "ollama.com/download")}
      ${t.apple_silicon ? `<p class="muted">Apple Silicon detected 👍 local AI will run fast.</p>` : ""}</div>${nav()}`;
  }
  if (wizardStep === 2) body = aiPicker(true) + nav("Continue", true);
  if (wizardStep === 3) body = `<h1>Connect your accounts</h1><p class="sub">Posting uses the official Instagram, Facebook and Threads APIs. You can do this later from the Accounts tab.</p>${accountsBody()}${nav("Continue", true)}`;
  if (wizardStep === 4) body = coversBody(true) + nav("Continue", true);
  if (wizardStep === 5) body = `<h1>Add your first long video</h1><p class="sub">A stream VOD, a playthrough, a 3-hour session. The factory finds the best moments, writes hooks, renders reels and long parts.</p>${addVideoBody()}${nav("Finish setup")}`;
  return `<div class="wizard">${dots}${body}</div>`;
}
async function wizardNext() {
  if (wizardStep === 0) await api("/api/settings", { page_name: $("#w_page").value.trim(), handle: $("#w_handle").value.trim().replace(/^@/, ""), header: $("#w_header").value.trim() || "In GTA VI" });
  if (wizardStep === STEPS.length - 1) { await api("/api/settings", { setup_done: true }); go("home"); return; }
  wizardStep++; await refresh(); render();
}

// ------------------------------------------------------------ AI picker
const AIS = [
  ["claude", "Claude (best hooks)", "Paste an Anthropic API key. Costs a few cents per long video.", true],
  ["openai", "OpenAI", "Paste an OpenAI API key. Similar cost.", true],
  ["ollama", "Free, on your Mac", "Uses Ollama with a vision model. Slower, no cost, works offline.", false],
  ["none", "No AI", "The factory still finds loud/busy moments; you write the hooks.", false],
];
let aiChoice = null;
function aiPicker(inWizard) {
  const cur = aiChoice || (S.settings.ai_provider === "auto" ? S.ai.provider : S.settings.ai_provider);
  const pick = AIS.find((a) => a[0] === cur) || AIS[0];
  return `${inWizard ? `<h1>Pick the brain</h1><p class="sub">It watches each moment and writes the hook. You can change this any time.</p>` : ""}
    <div class="grid g2">${AIS.map(([id, t, d]) => `<div class="card choice ${id === cur ? "on" : ""}" onclick="aiChoice='${id}';render()"><h3>${t}</h3><p>${d}</p></div>`).join("")}</div>
    <div class="card">${pick[3] ? `<label>${pick[1]} API key ${S.ai[cur] ? '<span class="pill ok">saved</span>' : ""}</label>
      <input id="ai_key" type="password" placeholder="${S.ai[cur] ? "saved (paste a new one to replace)" : "paste your key"}">
      <p class="muted">${cur === "claude" ? 'Get one at <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com</a> → API keys.' : 'Get one at <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com/api-keys</a>.'} It stays in a hidden file on your Mac.</p>`
      : cur === "ollama" ? `<ol class="steps"><li>Install Ollama from <a href="https://ollama.com/download" target="_blank">ollama.com/download</a> and open it.</li><li>In Terminal run <code>ollama pull ${esc(S.settings.ollama_model)}</code> (one time, ~6 GB).</li><li>Press Test below.</li></ol>`
      : `<p class="muted">Nothing to set up.</p>`}
      <div class="row" style="margin-top:10px"><button class="btn primary" onclick="saveAI('${cur}')">Save & test</button><span id="ai_msg" class="muted"></span></div></div>`;
}
async function saveAI(p) {
  $("#ai_msg").textContent = "Testing…";
  const r = await api("/api/ai", { provider: p, key: $("#ai_key")?.value || "" });
  $("#ai_msg").innerHTML = `<span class="pill ${r.ok ? "ok" : "no"}">${r.ok ? "works" : "problem"}</span> ${esc(r.message)}`;
  await refresh();
}

// ------------------------------------------------------------ accounts
function accountsBody() {
  const a = S.accounts, st = (k) => `<span class="pill ${a[k] ? "ok" : "no"}">${k[0].toUpperCase() + k.slice(1)}: ${a[k] ? "connected" : "not connected"}</span>`;
  return `
  <div class="card"><div class="row"><h3 style="margin:0">1. Your Meta app (one time, ~5 min)</h3><span class="spacer"></span><span class="pill ${a.meta_app ? "ok" : "warn"}">${a.meta_app ? "saved" : "recommended"}</span></div>
    <p class="muted">Meta only lets tools post through an app you own. It's free. Saving its ID and secret lets the factory turn short keys into 60-day keys and refresh Threads by itself, so you rarely touch this again.</p>
    <details><summary>Show me how</summary><ol class="steps" style="margin-top:12px">
      <li>Make your Instagram a <b>Professional</b> account (Instagram → Settings → Account type) and link it to your Facebook Page (Page settings → Linked accounts → Instagram).</li>
      <li>Open <a href="https://developers.facebook.com/apps" target="_blank">developers.facebook.com/apps</a> → <b>Create app</b>. Name it anything (e.g. “${esc(S.settings.page_name || "my page")} poster”).</li>
      <li>Add the use cases <b>Manage everything on your Page</b>, <b>Instagram API</b> and <b>Access the Threads API</b>.</li>
      <li>App settings → Basic: copy the <b>App ID</b> and <b>App secret</b> into the boxes below.</li>
    </ol></details>
    <div class="grid g2"><div><label>App ID</label><input id="m_id" placeholder="1234567890"></div><div><label>App secret</label><input id="m_secret" type="password" placeholder="${a.meta_app ? "saved" : ""}"></div></div>
    <div class="row" style="margin-top:10px"><button class="btn" onclick="saveMetaApp()">Save app</button>
    <span class="muted">Have Claude in your browser? Ask it to “set up my Meta app with the content-factory meta-setup skill”.</span></div></div>

  <div class="card"><div class="row"><h3 style="margin:0">2. Instagram + Facebook Page</h3><span class="spacer"></span>${st("instagram")} ${st("facebook")}</div>
    <details><summary>Get the key</summary><ol class="steps" style="margin-top:12px">
      <li>Open the <a href="https://developers.facebook.com/tools/explorer/" target="_blank">Graph API Explorer</a> and pick your app at the top right.</li>
      <li>Add permissions: <code>pages_show_list</code> <code>pages_read_engagement</code> <code>pages_manage_posts</code> <code>instagram_basic</code> <code>instagram_content_publish</code> <code>business_management</code>.</li>
      <li>Click <b>Generate Access Token</b>, tick your Page and your Instagram, approve.</li>
      <li>Copy the key (starts with <code>EAA</code>) and paste it below. One key covers both.</li>
    </ol></details>
    <label>Meta key</label><input id="k_fb" type="password" placeholder="EAA…">
    <label>Facebook Page ID (only if you manage several Pages)</label><input id="k_page" placeholder="optional">
    <div class="row" style="margin-top:10px"><button class="btn primary" onclick="connect('facebook')">Connect Instagram + Facebook</button><span id="msg_facebook" class="muted"></span></div></div>

  <div class="card"><div class="row"><h3 style="margin:0">3. Threads</h3><span class="spacer"></span>${st("threads")}</div>
    <details><summary>Get the key</summary><ol class="steps" style="margin-top:12px">
      <li>In your app: <b>Use cases → Access the Threads API → Customize</b>. Add <code>threads_basic</code> and <code>threads_content_publish</code>.</li>
      <li><b>Roles → Threads testers</b>: add your Threads username. In the Threads app accept it (Settings → Account → Website permissions → Invites).</li>
      <li>Back in Threads API settings → <b>User Token Generator</b> → Generate Access Token → copy it.</li>
    </ol></details>
    <label>Threads key</label><input id="k_th" type="password" placeholder="THAA…">
    <div class="row" style="margin-top:10px"><button class="btn primary" onclick="connect('threads')">Connect Threads</button><span id="msg_threads" class="muted"></span></div></div>

  <div class="card"><h3 style="margin:0 0 6px">4. YouTube</h3><p class="muted" style="margin:0">YouTube makes script uploads private until your app passes a Google audit, so the factory builds ready-to-drag Day folders (YouTube tab). Drag them into YouTube Studio; Claude can set the details and schedule them with the youtube-studio-scheduler skill.</p></div>`;
}
async function saveMetaApp() { await api("/api/accounts/meta_app", { app_id: $("#m_id").value.trim(), app_secret: $("#m_secret").value.trim() }); toast("Meta app saved"); await refresh(); render(); }
async function connect(p) {
  const el = $("#msg_" + p); el.textContent = "Checking…";
  const body = p === "threads" ? { token: $("#k_th").value } : { token: $("#k_fb").value, page_id: $("#k_page").value };
  const r = await api("/api/accounts/" + p, body);
  let msg = `<span class="pill ${r.ok ? "ok" : "no"}">${r.ok ? "connected" : "problem"}</span> ${esc(r.message)}`;
  if (p === "facebook") { const ig = await api("/api/accounts/instagram", {}); msg += `<br><span class="pill ${ig.ok ? "ok" : "no"}">Instagram</span> ${esc(ig.message)}`; }
  el.innerHTML = msg; await refresh();
}

// ------------------------------------------------------------ add video
function addVideoBody() {
  return `<div class="grid g2">
    <div class="card"><h3 style="margin-top:0">From a link</h3><p class="muted">Your YouTube/Twitch stream VOD or any video you have rights to.</p>
      <input id="v_link" placeholder="https://www.youtube.com/watch?v=…"><div class="row" style="margin-top:10px"><button class="btn primary" onclick="addLink()">Download & clip</button></div>
      <p class="muted">Tip: on PS5/Xbox, stream straight to YouTube while you play, then paste the stream link here.</p></div>
    <div class="card"><h3 style="margin-top:0">From your Mac</h3>
      <div class="drop" id="drop" ondragover="event.preventDefault();this.classList.add('hover')" ondragleave="this.classList.remove('hover')" ondrop="dropFile(event)">
        Drop a video here<br><span class="muted">or put it in the <a href="#" onclick="openFolder('inbox');return false">Drop videos here</a> folder; it's picked up within 20 seconds</span></div>
      <input type="file" id="v_file" accept="video/*" style="margin-top:10px" onchange="uploadFile(this.files[0])"></div></div>`;
}
async function addLink() { const url = $("#v_link").value.trim(); if (!url) return; await api("/api/videos/link", { url }); toast("Started. Follow progress on Home."); $("#v_link").value = ""; await refresh(); }
function dropFile(e) { e.preventDefault(); $("#drop").classList.remove("hover"); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); }
async function uploadFile(f) {
  if (!f) return; toast(`Copying ${f.name} into the factory…`, 60000);
  const fd = new FormData(); fd.append("file", f); await api("/api/videos/upload", fd);
  toast("Added. Clipping starts in a few seconds; follow it on Home.");
}

// ------------------------------------------------------------ pages
function home() {
  const P = S.posting, plat = [["instagram", "IG", "Instagram"], ["facebook", "FB", "Facebook"], ["threads", "TH", "Threads"]];
  const anyRunning = Object.values(P.running).some(Boolean);
  const jobs = S.jobs.filter((j) => j.status !== "done").slice(0, 5);
  return `<h1>${esc(S.settings.page_name || "Your page")}</h1><p class="sub">Keep this Mac on and plugged in; the factory clips and posts while it runs.</p>
  <div class="card hero"><div class="row"><div><div class="stat">${anyRunning ? "🟢 Posting is ON" : "⏸ Posting is off"}<small>${anyRunning ? "videos go out on your schedule" : "approve some reels, connect accounts, then start"}</small></div></div><span class="spacer"></span>
    ${anyRunning ? `<button class="btn bad" onclick="postStop()">Stop posting</button>` : `<button class="btn primary" onclick="postStart()">▶ Start posting</button>`}</div></div>
  <div class="grid g3">${plat.map(([p, tag, label]) => { const st = P.status[tag] || {}, c = S.counts[p] || { posted: 0, waiting: 0, error: 0 };
    const kind = st.kind === "dead" ? "no" : st.kind === "busy" ? "busy" : S.accounts[p] ? "ok" : "no";
    return `<div class="card"><div class="row"><b>${label}</b><span class="spacer"></span><span class="pill ${kind}">${esc(st.state || (S.accounts[p] ? "ready" : "not connected"))}</span></div>
      <div class="row" style="margin-top:10px"><div class="stat">${c.posted}<small>posted</small></div><div class="stat" style="margin-left:18px">${c.waiting}<small>waiting</small></div>${c.error ? `<div class="stat" style="margin-left:18px;color:var(--red)">${c.error}<small>failed</small></div>` : ""}</div>
      <div class="muted" id="cd_${tag}">${st.until ? "next in " + countdown(st.until) : esc(st.account || "")}</div></div>`; }).join("")}</div>
  <h2>Working on</h2>${jobs.length ? jobs.map((j) => `<div class="card"><div class="row"><b>${esc(j.title)}</b><span class="spacer"></span><span class="pill ${j.status === "failed" ? "no" : "busy"}">${j.status}</span></div>
    <div class="muted">${esc(j.error || j.step)}</div><div class="bar"><i style="width:${Math.round(j.progress * 100)}%"></i></div></div>`).join("") : `<p class="muted">Nothing running. <a href="#videos">Add a video</a>.</p>`}
  <h2>Live feed</h2><div class="feed" id="feed">${feedHTML()}</div>`;
}
const feedHTML = () => S.feed.slice().reverse().map((l) => `<div class="${l.level}">${esc(l.t.slice(11))} <b>${esc(l.tag)}</b> ${esc(l.msg)}</div>`).join("");
async function postStart() { await api("/api/posting/start", {}); toast("Posting started"); await refresh(); render(); }
async function postStop() { await api("/api/posting/stop", {}); toast("Posting will stop after the current upload"); await refresh(); render(); }

function videos() {
  return `<h1>Videos</h1><p class="sub">Each long video becomes ~${S.settings.reels_per_hour} reels per hour of footage${S.settings.make_long ? ` plus ${S.settings.long_minutes}-minute long parts` : ""}.</p>
  ${addVideoBody()}
  <h2>Your videos</h2>${S.projects.length ? S.projects.map((p) => `<div class="card"><div class="row"><div><b>${esc(p.title)}</b><div class="muted">${fmtMin(p.duration)} · ${p.reels} reels (${p.approved} approved) · ${p.longs} long parts · ${esc(p.status)}</div></div><span class="spacer"></span>
    <button class="btn small" onclick="openProject='${p.id}';go('review')">Review</button><button class="btn small" onclick="reclip('${p.id}')">Re-clip</button></div></div>`).join("") : `<p class="muted">No videos yet.</p>`}`;
}
async function reclip(id) { if (!confirm("Find moments again and re-render? Already-posted reels stay posted.")) return; await api(`/api/projects/${id}/process`, {}); toast("Re-clipping started"); }

let P = null;
async function loadProject() { if (!openProject && S.projects[0]) openProject = S.projects[0].id; P = openProject ? await api(`/api/projects/${openProject}`) : null; }
function review() {
  if (!P) return `<h1>Review</h1><p class="sub">Nothing to review yet. <a href="#videos">Add a video</a>.</p>`;
  const pending = P.moments.filter((m) => m.status === "review").length;
  return `<div class="row"><div><h1>Review</h1><p class="sub">Only approved videos get posted. Edit a hook and it re-renders.</p></div><span class="spacer"></span>
    <select style="width:auto" onchange="openProject=this.value;loadProject().then(render)">${S.projects.map((p) => `<option value="${p.id}" ${p.id === P.id ? "selected" : ""}>${esc(p.title.slice(0, 50))}</option>`).join("")}</select>
    <button class="btn good" onclick="approveAll()" ${pending ? "" : "disabled"}>Approve all ${pending ? `(${pending})` : ""}</button></div>
  <div class="reels">${P.moments.map((m) => `<div class="reel ${m.status}" id="m_${m.id}">
    ${m.reel ? `<video src="${media(m.reel)}#t=1" controls preload="metadata"></video>` : `<div style="aspect-ratio:9/16;display:grid;place-items:center;background:#000" class="muted">needs a hook</div>`}
    <div class="body"><div class="row"><span class="pill ${m.status === "approved" ? "ok" : m.status === "rejected" ? "no" : "warn"}">${m.status}</span><span class="spacer"></span><span class="muted">${m.score && m.why !== "loud / busy moment" ? Math.round(m.score) + "/10 · " : ""}at ${fmtMin(m.start)}</span></div>
    <textarea id="h_${m.id}">${esc(m.hook)}</textarea>
    <div class="row"><input id="e_${m.id}" value="${esc(m.emoji)}" style="width:60px" title="emoji"><button class="btn small" onclick="saveHook('${m.id}')">Save hook</button></div>
    <div class="row"><button class="btn small good" onclick="setM('${m.id}',true)">Approve</button><button class="btn small bad" onclick="setM('${m.id}',false)">Reject</button></div>
    ${m.why ? `<div class="muted">${esc(m.why)}</div>` : ""}</div></div>`).join("")}</div>
  ${P.long_parts.length ? `<h2>Long parts</h2>${P.long_parts.map((l) => `<div class="card long">${l.cover ? `<img src="${media(l.cover)}">` : "<div></div>"}
    <div><b>${esc(l.title)}</b><div class="muted">${fmtMin(l.duration)}</div></div>
    <button class="btn ${l.approved ? "good" : ""}" onclick="setLong(${l.n},${!l.approved})">${l.approved ? "✓ Approved" : "Approve"}</button></div>`).join("")}` : ""}`;
}
async function saveHook(id) { await api("/api/moments", { pid: P.id, mid: id, hook: $("#h_" + id).value, emoji: $("#e_" + id).value }); toast("Re-rendering with the new hook…"); }
async function setM(id, ok) { await api("/api/moments", { pid: P.id, mid: id, approved: ok }); await loadProject(); render(); }
async function setLong(n, ok) { await api("/api/longs", { pid: P.id, n, approved: ok }); await loadProject(); render(); }
async function approveAll() { await api(`/api/projects/${P.id}/approve_all`, {}); await loadProject(); await refresh(); render(); toast("Approved. They'll post on your schedule."); }

let coverPreview = null;
function coversBody(inWizard) {
  const s = S.settings;
  return `${inWizard ? `<h1>Thumbnails</h1><p class="sub">For your long gameplay parts (YouTube + Facebook). Pick a style and, if you like, your own background art.</p>` : `<h1>Covers</h1><p class="sub">Thumbnails for long parts.</p>`}
  <div class="grid g3">${Object.entries(S.cover_styles).map(([id, d]) => `<div class="card choice ${s.cover_style === id ? "on" : ""}" onclick="setStyle('${id}')"><h3>${id}</h3><p>${esc(d)}</p></div>`).join("")}</div>
  <div class="card"><label>Background</label><select id="c_bg" onchange="setBg(this.value)"><option value="">A frame from the video</option>${S.cover_backgrounds.filter((f) => f !== "_preview.jpg").map((f) => `<option ${f === s.cover_background ? "selected" : ""}>${esc(f)}</option>`).join("")}</select>
    <label>Upload your own art (1280×720 or bigger looks best)</label><input type="file" accept="image/*" onchange="uploadBg(this.files[0])">
    <div class="row" style="margin-top:12px"><button class="btn primary" onclick="previewCover()">Preview</button></div>
    ${coverPreview ? `<img class="cover" style="margin-top:12px" src="${media(coverPreview)}&t=${Date.now()}">` : ""}</div>`;
}
async function setStyle(id) { await api("/api/settings", { cover_style: id }); await refresh(); render(); }
async function setBg(v) { await api("/api/settings", { cover_background: v }); await refresh(); }
async function uploadBg(f) { if (!f) return; const fd = new FormData(); fd.append("file", f); await api("/api/covers/upload", fd); await refresh(); render(); toast("Background saved"); }
async function previewCover() { const r = await api("/api/covers/preview", { style: S.settings.cover_style, background: $("#c_bg").value }); if (!r.ok) return toast(r.message); coverPreview = r.path; render(); }

function youtube() {
  return `<h1>YouTube</h1><p class="sub">Google keeps script uploads private unless your app passes its audit, so you drag; the factory does the rest.</p>
  <div class="card"><ol class="steps">
    <li>Press <b>Make Day folders</b>. Each folder has ${S.settings.youtube_per_day} videos (Shorts + up to 2 long parts), named with their titles, plus thumbnails and a descriptions file.</li>
    <li>Open <a href="https://studio.youtube.com" target="_blank">YouTube Studio</a> → Create → Upload, and drag a Day folder's videos in. They land as drafts.</li>
    <li>Ask Claude (with the <code>youtube-studio-scheduler</code> skill) to “schedule my drafts every 30 minutes”, or schedule them yourself.</li></ol>
    <div class="row"><button class="btn primary" onclick="ytBuild()">Make Day folders</button><button class="btn" onclick="openFolder('youtube')">Open YouTube uploads folder</button></div></div>
  <div class="card"><b>Tip</b><p class="muted" style="margin:6px 0 0">Verify your channel (YouTube Studio → Settings → Channel → Feature eligibility → Advanced features) to lift the ~15 uploads/day limit.</p></div>`;
}
async function ytBuild() { const r = await api("/api/youtube/build", { days: 7 }); toast(r.made.length ? "Made " + r.made.join(", ") : "Nothing new to add: approve more videos first"); }

function settings() {
  const s = S.settings, n = (k, label, help = "") => `<label>${label}</label><input type="number" id="s_${k}" value="${esc(s[k])}">${help ? `<div class="muted">${help}</div>` : ""}`;
  const t = (k, label) => `<label>${label}</label><textarea id="s_${k}">${esc(s[k])}</textarea>`;
  return `<h1>Settings</h1>
  <div class="card"><h3 style="margin-top:0">AI</h3>${aiPicker(false)}</div>
  <div class="grid g2"><div class="card"><h3 style="margin-top:0">Clipping</h3>${n("reel_seconds", "Reel length (seconds)", "Instagram's API refuses longer reels on some accounts; 25 is safe.")}${n("reels_per_hour", "Reels per hour of footage")}${n("long_minutes", "Long part length (minutes)")}
    <label>Credit line on reels (when clipping someone else, with permission)</label><input id="s_credit_line" value="${esc(s.credit_line)}" placeholder="gameplay: @creator"></div>
    <div class="card"><h3 style="margin-top:0">Posting</h3>
      <label>Minutes between posts</label><div class="grid g3">${["instagram", "facebook", "threads"].map((p) => `<div><span class="muted">${p}</span><input type="number" id="pe_${p}" value="${s.post_every_min[p]}"></div>`).join("")}</div>
      <label>Post only between these hours (24h, your Mac's time)</label><div class="grid g2"><input type="number" id="ph_a" value="${s.post_hours[0]}"><input type="number" id="ph_b" value="${s.post_hours[1]}"></div>
      <label>Platforms on</label>${["instagram", "facebook", "threads"].map((p) => `<label style="display:inline-flex;gap:6px;margin-right:14px"><input type="checkbox" style="width:auto" id="po_${p}" ${s.platforms_on[p] ? "checked" : ""}>${p}</label>`).join("")}
      <p class="muted">Instagram allows ~50 posts a day via the API, Facebook ~30 reels, Threads 250.</p></div></div>
  <div class="card"><h3 style="margin-top:0">Captions</h3><p class="muted">Placeholders: {hook} {handle} {page} {game} {keywords} {hashtags}</p>${t("caption_instagram", "Instagram")}${t("caption_facebook", "Facebook")}${t("caption_threads", "Threads")}<label>Hashtags</label><input id="s_hashtags" value="${esc(s.hashtags)}"></div>
  <button class="btn primary" onclick="saveSettings()">Save settings</button> <button class="btn" onclick="wizardStep=0;api('/api/settings',{setup_done:false}).then(refresh).then(render)">Run setup again</button>`;
}
async function saveSettings() {
  const v = (k) => $("#s_" + k).value, num = (k) => Number(v(k));
  await api("/api/settings", {
    reel_seconds: num("reel_seconds"), reels_per_hour: num("reels_per_hour"), long_minutes: num("long_minutes"), credit_line: v("credit_line"),
    caption_instagram: v("caption_instagram"), caption_facebook: v("caption_facebook"), caption_threads: v("caption_threads"), hashtags: v("hashtags"),
    post_every_min: Object.fromEntries(["instagram", "facebook", "threads"].map((p) => [p, Number($("#pe_" + p).value)])),
    post_hours: [Number($("#ph_a").value), Number($("#ph_b").value)],
    platforms_on: Object.fromEntries(["instagram", "facebook", "threads"].map((p) => [p, $("#po_" + p).checked])),
  });
  toast("Saved"); await refresh();
}

// ------------------------------------------------------------ render + polling
async function render() {
  if (!S) return;
  if (!S.settings.setup_done) { $("#root").innerHTML = wizard(); return; }
  if (view === "review") await loadProject();
  const pages = { home, videos, review, accounts: () => `<h1>Accounts</h1><p class="sub">Keys live in a hidden folder on your Mac, never anywhere else.</p>${accountsBody()}`, covers: () => coversBody(false), youtube, settings };
  $("#root").innerHTML = shell((pages[view] || home)());
}
async function refresh() { S = await api("/api/state"); }
async function tick() {
  try {
    await refresh();
    if (view === "home" && S.settings.setup_done && !document.activeElement?.matches("input,textarea,select")) render();
    else if ($("#feed")) $("#feed").innerHTML = feedHTML();
  } catch (e) { toast("Lost connection to the factory. Is it still running?"); }
}
refresh().then(render);
setInterval(tick, 3000);
