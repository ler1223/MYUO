// Редактор анимаций, эффектов навыков и фонов боя UO (tools/uo_extract/anim_editor.py).
'use strict';
const $ = id => document.getElementById(id);
const TICKS = 60;
const STATE_LABELS = { idle: 'стойка (по кругу)', attack: 'атака', skill: 'каст (запасной)', hit: 'попадание',
  avoid: 'уклонение', guard: 'защита', cover: 'прикрытие', die: 'смерть', victory: 'победа' };
const VARIANT_GROUPS = [0xFF, 0xC00, 0x3000, 0xC000, 0x30000, 0xFE000000];   // как в puppet.py
const TALK = /^(D_|FACE_|EP_|HG_D_)/;
const BG_FRONT = /^(kinkei|maekusa|zenkei)|temae/i, BG_HIDDEN = /^effect/i;    // как bg_role в engine/uo/library.py
const BG_BOX = [-1376, -800, 1376, 720];
const ROLE_LABELS = { back: 'задний', front: 'передний', hidden: 'скрыт' };

const E = {
  config: null, units: {}, files: {}, skills: {}, scenes: {}, tab: 'chars',
  cls: null, skill: null, bgName: null,
  ctx: null, models: new Map(),
  slot: null, selPart: null, preview: null,
  t: 0, playing: true, last: 0, cam: { x: 0, y: -150, zoom: 1 }, dirty: false, token: 0,
};
let R;

// ---------- общее ----------
async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
function button(text, title, onclick) { const b = document.createElement('button'); b.textContent = text; b.title = title; b.onclick = onclick; return b; }
function markDirty(on = true) { E.dirty = on; $('dirty').textContent = on ? '● есть несохранённые изменения' : 'сохранено'; $('dirty').classList.toggle('on', on); }
let toastTimer;
function toast(text, ms) { clearTimeout(toastTimer); $('toast').hidden = !text; $('toast').textContent = text || ''; if (text && ms) toastTimer = setTimeout(() => { $('toast').hidden = true; }, ms); }
function natural(name) { const m = /^(.*?)(\d*)$/.exec(name); return [m[1], parseInt(m[2] || '0', 10)]; }
function normalize(e) { return typeof e === 'string' ? { anim: e } : { ...e }; }
function compact(p) {
  const out = { anim: p.anim };
  if (p.from != null && p.from > 0) out.from = Math.round(p.from);
  if (p.to != null) out.to = Math.round(p.to);
  const zones = (p.speed || []).filter(z => z.to > z.from && z.rate > 0 && z.rate !== 1);
  if (zones.length) out.speed = zones.map(z => ({ from: Math.round(z.from), to: Math.round(z.to), rate: +(+z.rate).toFixed(2) }));
  return Object.keys(out).length === 1 ? p.anim : out;
}
function resolveChain(list, patterns) {          // как resolve_chain в engine/uo/library.py
  for (const p of patterns) {
    const re = new RegExp(p);
    const hits = list.filter(n => re.test(n)).sort((a, b) => { const [ba, na] = natural(a), [bb, nb] = natural(b); return ba < bb ? -1 : ba > bb ? 1 : na - nb; });
    if (hits.length) { const base = natural(hits[0])[0]; return hits.filter(n => natural(n)[0] === base); }
  }
  return [];
}

// ---------- модели (кукла + текстуры) ----------
async function loadModel(folder, file) {
  const key = folder + '/' + file;
  if (!E.models.has(key)) {
    E.models.set(key, (async () => {
      const buf = await (await fetch(`/game/${folder}/${file}.mbs`)).arrayBuffer();
      const skins = await api(`/api/skins?folder=${folder}&file=${file}`);
      const ctx = { key, folder, file, model: parseMBS(buf), skins, skin: skins.skins[0], pages: [] };
      await loadSkin(ctx, ctx.skin);
      return ctx;
    })());
  }
  return E.models.get(key);
}

async function loadSkin(ctx, skin) {
  const n = (ctx.skins.pages || {})[skin] || 1, urls = [];
  for (let i = 0; i < n; i++) urls.push(`/tex/${ctx.folder}/${skin}.${i}.png`);
  ctx.skin = skin;
  ctx.pages = await Promise.all(urls.map(u => R.loadTexture(u).catch(() => null)));
}

function names() { return E.ctx ? E.ctx.model.anims.map(a => a.name).filter(n => !n.startsWith('#')) : []; }
function animByName(n) { return E.ctx && E.ctx.model.anims.find(a => a.name === n); }

function variantBits(model) {
  let used = 0;
  for (const f of model.parts.flags) used |= f;
  return VARIANT_GROUPS.map(g => { const b = []; for (let i = 0; i < 32; i++) if ((g >>> i) & 1 && (used >>> i) & 1) b.push(i); return b; });
}
function computeVisible(ctx, variant) {
  const groups = variantBits(ctx.model);
  const active = groups.map((bits, gi) => !bits.length ? 0 : ((1 << (gi === 0 ? bits[Math.min(variant, bits.length - 1)] : bits[0])) >>> 0));
  const P = ctx.model.parts, vis = new Uint8Array(P.flags.length);
  for (let i = 0; i < vis.length; i++) {
    let ok = 1;
    for (let g = 0; g < VARIANT_GROUPS.length; g++) { const b = (P.flags[i] & VARIANT_GROUPS[g]) >>> 0; if (b && !((b & active[g]) >>> 0)) { ok = 0; break; } }
    vis[i] = ok;
  }
  ctx.visible = vis;
}

// ---------- слоты: что редактируется ----------
// {kind: 'state'|'skill', key} — у класса; {kind: 'cast'|'hit', key: навык} — эффекты навыка
function spec() { return E.cls ? E.config.classes[E.cls] : null; }
function broken() { return new Set((E.config.broken || {})[E.ctx?.file] || []); }
function isManual(slot) {
  if (slot.kind !== 'state') return true;
  const s = spec(); return !!(s && s.states && s.states[slot.key] !== undefined);
}
function slotParts(slot) {
  const all = names();
  let raw;
  if (slot.kind === 'state') {
    const s = spec(); if (!s) return [];
    if (!isManual(slot)) {
      const bad = broken();
      return resolveChain(all.filter(n => !bad.has(n)), (E.config.states[slot.key] || {}).chain || []).map(anim => ({ anim }));
    }
    raw = s.states[slot.key];
  } else if (slot.kind === 'skill') raw = (spec()?.skills || {})[slot.key] || [];
  else raw = (E.config.skill_fx?.[slot.key] || {})[slot.kind] || [];
  return raw.map(normalize).filter(p => all.includes(p.anim));
}
function setSlotParts(slot, parts) {
  const list = parts.map(compact);
  if (slot.kind === 'state') { const s = spec(); s.states = s.states || {}; s.states[slot.key] = list; }
  else if (slot.kind === 'skill') { const s = spec(); s.skills = s.skills || {}; s.skills[slot.key] = list; }
  else {
    const fx = E.config.skill_fx = E.config.skill_fx || {};
    const entry = fx[slot.key] = fx[slot.key] || { cast: [], hit: [] };
    entry[slot.kind] = list; delete entry.generic;
  }
  markDirty();
}
function slotLabel(slot) {
  if (slot.kind === 'state') return STATE_LABELS[slot.key] || slot.key;
  if (slot.kind === 'skill') return E.skills[slot.key]?.name || slot.key;
  return slot.kind === 'cast' ? 'каст' : 'попадание';
}
function sameSlot(a, b) { return a && b && a.kind === b.kind && a.key === b.key; }

// отрезки части [a, b) со скоростью: зоны (speed) поверх обрезки; как speed_segments в engine/uo/library.py
function speedSegments(start, end, zones) {
  const marks = new Set([start, end]), clean = [];
  for (const z of zones || []) {
    const a = Math.max(z.from || 0, start), b = Math.min(z.to ?? end, end), rate = +z.rate || 1;
    if (b > a && rate > 0) { clean.push([a, b, rate]); marks.add(a); marks.add(b); }
  }
  const pts = [...marks].sort((x, y) => x - y), out = [];
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i], b = pts[i + 1], z = clean.find(c => c[0] <= a && b <= c[1]);
    out.push([a, b, z ? z[2] : 1]);
  }
  return out;
}
function partRange(p) {
  const len = Math.max(1, animByName(p.anim)?.length || 1);
  const from = Math.min(len - 1, p.from || 0);
  return [from, Math.max(from + 1, p.to != null ? Math.min(p.to, len) : len)];
}
function partLength(p) {
  const a = animByName(p.anim); if (!a) return 0;
  const [from, to] = partRange(p);
  return Math.max(1, Math.round(speedSegments(from, to, p.speed).reduce((s, [x, y, r]) => s + (y - x) / r, 0)));
}
function partTick(p, t) {               // тик анимации в момент t (тики времени от начала части)
  const [from, to] = partRange(p);
  let left = t;
  for (const [a, b, r] of speedSegments(from, to, p.speed)) {
    const span = (b - a) / r;
    if (left < span) return Math.floor(a + left * r);
    left -= span;
  }
  return to - 1;
}

function slotBox(slot, title, extra) {
  const manual = isManual(slot), parts = slotParts(slot);
  const div = document.createElement('div');
  div.className = 'state' + (sameSlot(slot, E.slot) ? ' selected' : '');
  div.onclick = () => selectSlot(slot);
  const top = document.createElement('div'); top.className = 'top';
  top.innerHTML = `<b>${title}</b>${slot.kind === 'state' ? `<span class="mode ${manual ? 'manual' : ''}">${manual ? 'задано' : 'по правилам'}</span>` : ''}${extra || ''}
    <span class="muted">${(parts.reduce((s, p) => s + partLength(p), 0) / TICKS).toFixed(2)} с</span><span class="spacer"></span>`;
  top.appendChild(button('▶', 'Проиграть', e => { e.stopPropagation(); selectSlot(slot); }));
  if (slot.kind === 'state' && manual) top.appendChild(button('сбросить', 'Вернуть выбор по общим правилам', e => {
    e.stopPropagation(); delete spec().states[slot.key]; markDirty(); renderMiddle(); selectSlot(slot);
  }));
  top.appendChild(button('очистить', 'Ничего не играть', e => { e.stopPropagation(); setSlotParts(slot, []); renderMiddle(); selectSlot(slot); }));
  div.appendChild(top);
  const chain = document.createElement('div'); chain.className = 'chain';
  if (!parts.length) chain.innerHTML = `<span class="empty">пусто — выберите анимации справа и нажмите «+»</span>`;
  parts.forEach((p, i) => {
    const chip = document.createElement('span');
    chip.className = 'part' + (sameSlot(slot, E.slot) && i === E.selPart ? ' sel' : '');
    const [rf, rt] = partRange(p);
    const range = p.from != null || p.to != null ? `<span class="range">[${rf}–${rt}]</span>` : '';
    const fast = (p.speed || []).length ? `<span class="range" title="зоны скорости">×${p.speed.length}</span>` : '';
    chip.innerHTML = `${p.anim}${range}${fast}`;
    chip.onclick = e => { e.stopPropagation(); E.slot = slot; E.selPart = i; renderMiddle(); previewParts([p]); };
    chip.appendChild(button('◀', 'Раньше', e => { e.stopPropagation(); movePart(slot, i, -1); }));
    chip.appendChild(button('▶', 'Позже', e => { e.stopPropagation(); movePart(slot, i, 1); }));
    chip.appendChild(button('×', 'Убрать', e => { e.stopPropagation(); const ps = slotParts(slot); ps.splice(i, 1); setSlotParts(slot, ps); E.selPart = null; renderMiddle(); selectSlot(slot); }));
    chain.appendChild(chip);
  });
  div.appendChild(chain);
  return div;
}

function selectSlot(slot) {
  E.slot = slot; E.selPart = null; cancelAdd();
  renderMiddle(); renderAnimList();
  previewParts(slotParts(slot), slot.kind === 'state' && slot.key === 'idle');
}
function movePart(slot, i, d) {
  const ps = slotParts(slot), j = i + d;
  if (j < 0 || j >= ps.length) return;
  [ps[i], ps[j]] = [ps[j], ps[i]];
  setSlotParts(slot, ps); E.slot = slot; E.selPart = j; renderMiddle();
}
function addPart(anim) {                 // «+» открывает окно выбора куска; в цепочку часть попадает по «Добавить»
  if (!E.slot) return toast('Сначала выберите, куда добавлять', 2000);
  const len = Math.max(1, animByName(anim)?.length || 1);
  E.pending = { anim, from: 0, to: len, len };
  $('addName').textContent = `${anim} → ${slotLabel(E.slot)}`;
  $('addFrom').value = 0; $('addTo').value = len;
  $('addLen').textContent = `длина ${len} тиков (${(len / TICKS).toFixed(2)} с)`;
  $('addDialog').hidden = false;
  previewParts([{ anim }]);
}
function pendingChanged() {
  const q = E.pending; if (!q) return;
  q.from = Math.max(0, Math.min(q.len - 1, Math.round(+$('addFrom').value || 0)));
  q.to = Math.max(q.from + 1, Math.min(q.len, Math.round(+$('addTo').value || q.len)));
  $('addFrom').value = q.from; $('addTo').value = q.to;
  previewParts([{ anim: q.anim, from: q.from || null, to: q.to >= q.len ? null : q.to }]);
}
function confirmAdd() {
  const q = E.pending; if (!q || !E.slot) return;
  const ps = slotParts(E.slot), part = { anim: q.anim };
  if (q.from > 0) part.from = q.from;
  if (q.to < q.len) part.to = q.to;
  ps.push(part); setSlotParts(E.slot, ps);
  E.pending = null; $('addDialog').hidden = true;
  E.selPart = ps.length - 1; renderMiddle(); renderAnimList(); renderLeft();
  previewParts(slotParts(E.slot), E.slot.kind === 'state' && E.slot.key === 'idle');
}
function cancelAdd() { E.pending = null; $('addDialog').hidden = true; }

// ---------- обрезка части ----------
function selectedPart() { return E.slot && E.selPart != null ? slotParts(E.slot)[E.selPart] : null; }
function showPartEditor() {
  const p = selectedPart();
  $('partEditor').hidden = !p || E.tab === 'bg';
  if (!p) return;
  const len = Math.max(1, animByName(p.anim)?.length || 1);
  $('partName').textContent = `${p.anim} (${slotLabel(E.slot)}, часть ${E.selPart + 1})`;
  $('partFrom').value = p.from || 0; $('partTo').value = p.to ?? len;
  $('partLen').textContent = `длина ${len} тиков (${(len / TICKS).toFixed(2)} с)`;
  renderZones();
}
function renderZones() {
  const p = selectedPart(), box = $('zones'); box.textContent = '';
  if (!p) return;
  (p.speed || []).forEach((z, i) => {
    const row = document.createElement('div'); row.className = 'row zone';
    const num = (value, step, onchange, title) => {
      const input = document.createElement('input'); input.type = 'number'; input.step = step; input.value = value; input.title = title;
      input.onchange = () => onchange(+input.value); return input;
    };
    row.append('с тика ', num(z.from, 1, v => setZone(i, { from: v }), 'начало зоны (тик анимации)'),
               ' по ', num(z.to, 1, v => setZone(i, { to: v }), 'конец зоны'),
               ' скорость ×', num(z.rate, 0.05, v => setZone(i, { rate: v }), '2 — вдвое быстрее, 0.5 — вдвое медленнее'));
    row.appendChild(button('×', 'Убрать зону', () => { p.speed.splice(i, 1); commitPart(p); }));
    box.appendChild(row);
  });
}
function setZone(i, patch) {
  const p = selectedPart(); if (!p || !p.speed[i]) return;
  Object.assign(p.speed[i], patch);
  const len = Math.max(1, animByName(p.anim)?.length || 1), z = p.speed[i];
  z.from = Math.max(0, Math.min(len - 1, Math.round(z.from))); z.to = Math.max(z.from + 1, Math.min(len, Math.round(z.to)));
  z.rate = Math.max(0.1, Math.min(8, +z.rate || 1));
  commitPart(p);
}
function commitPart(p) {
  const ps = slotParts(E.slot); ps[E.selPart] = p; setSlotParts(E.slot, ps);
  renderMiddle();
  // список анимаций справа не перерисовываем: правка зоны срабатывает на потере фокуса поля, и
  // перерисовка таблицы подменяла бы кнопку «+» под курсором (добавлялась соседняя анимация)
  E.preview = { parts: [{ ...p }], loop: false };
  E.t = 0; $('timeline').max = Math.max(0, previewLength() - 1);
}
function addZone() {
  const p = selectedPart(); if (!p) return;
  const [from, to] = partRange(p), now = E.preview ? previewAt(Math.floor(E.t)) : null;
  const a = Math.min(to - 1, Math.max(from, now ? now.tick : from));
  (p.speed = p.speed || []).push({ from: a, to: Math.min(to, a + Math.max(2, Math.round((to - from) / 4))), rate: 2 });
  commitPart(p);
}
function editPart(from, to) {
  const ps = slotParts(E.slot), p = ps[E.selPart]; if (!p) return;
  const len = Math.max(1, animByName(p.anim)?.length || 1);
  from = Math.max(0, Math.min(len - 1, Math.round(from))); to = Math.max(from + 1, Math.min(len, Math.round(to)));
  p.from = from || null; p.to = to >= len ? null : to;
  setSlotParts(E.slot, ps); renderMiddle(); previewParts([p]);
}

// ---------- левая колонка ----------
function renderLeft() {
  const q = $('leftSearch').value.trim().toLowerCase(), only = $('leftFilter').checked;
  const ul = $('leftList'); ul.textContent = '';
  const add = (id, html, cls, active, onclick) => {
    const li = document.createElement('li'); li.innerHTML = html; if (cls) li.className = cls;
    if (active) li.classList.add('active'); li.onclick = onclick; ul.appendChild(li);
  };
  if (E.tab === 'chars') {
    $('leftFilterText').textContent = 'только с файлом';
    for (const id of Object.keys(E.units).sort((a, b) => E.units[a].name.localeCompare(E.units[b].name))) {
      const s = E.config.classes[id];
      if (only && !s) continue;
      if (q && !(id + ' ' + E.units[id].name + ' ' + (s ? s.file : '')).toLowerCase().includes(q)) continue;
      add(id, `${E.units[id].name}<span class="f">${s ? (s.folder ? s.folder + '/' : '') + s.file : 'нет файла'}</span>`, s ? '' : 'none', id === E.cls, () => selectClass(id));
    }
  } else if (E.tab === 'fx') {
    $('leftFilterText').textContent = 'только общие (без своего эффекта)';
    const fx = E.config.skill_fx || {};
    for (const id of Object.keys(E.skills).sort((a, b) => E.skills[a].name.localeCompare(E.skills[b].name))) {
      const f = fx[id] || {};
      if (only && !f.generic) continue;
      if (q && !(id + ' ' + E.skills[id].name).toLowerCase().includes(q)) continue;
      const what = [...(f.cast || []), ...(f.hit || [])].map(x => typeof x === 'string' ? x : x.anim).join(', ');
      add(id, `${E.skills[id].name}<span class="f">${f.generic ? 'общий: ' : ''}${what || 'нет'}</span>`, f.generic ? 'off' : '', id === E.skill, () => selectSkill(id));
    }
  } else {
    $('leftFilterText').textContent = 'только используемые';
    for (const [name, b] of Object.entries(E.config.backgrounds || {})) {
      if (only && !b.use) continue;
      if (q && !(name + ' ' + (b.scene || '')).toLowerCase().includes(q)) continue;
      add(name, `${name.replace(/^BGBt/, '')}<span class="f">${b.use ? (E.scenes[b.scene] || b.scene || '—') : 'не используется'}</span>`, b.use ? '' : 'off', name === E.bgName, () => selectBg(name));
    }
  }
}

// ---------- вкладка «Персонажи» ----------
async function selectClass(id) {
  E.cls = id; E.slot = { kind: 'state', key: 'idle' }; E.selPart = null;
  renderLeft();
  $('className').textContent = `${E.units[id].name} (${id})`;
  const fs = $('fileSelect'); fs.textContent = '';
  fs.add(new Option('— нет (обычный спрайт) —', ''));
  for (const [folder, list] of Object.entries(E.files)) {
    if (folder === 'Effect' || folder === 'BattleBG') continue;
    const g = document.createElement('optgroup'); g.label = folder;
    for (const f of list) g.appendChild(new Option(f, folder + '/' + f));
    fs.appendChild(g);
  }
  const s = spec();
  fs.value = s ? (s.folder || 'Chara') + '/' + s.file : '';
  await openClassModel();
}

async function openClassModel() {
  const token = ++E.token, s = spec();
  E.ctx = null; $('variantSelect').textContent = ''; $('skinSelect').textContent = '';
  if (!s) { renderMiddle(); renderAnimList(); E.preview = null; return; }
  toast('Загрузка ' + s.file + '…');
  try {
    const ctx = await loadModel(s.folder || 'Chara', s.file);
    if (token !== E.token) return;
    E.ctx = ctx;
    for (const k of ctx.skins.skins) $('skinSelect').add(new Option(k, k));
    $('skinSelect').value = ctx.skin;
    const first = variantBits(ctx.model)[0];
    if (!first.length) $('variantSelect').add(new Option('один', '0'));
    first.forEach((_, i) => $('variantSelect').add(new Option(`вариант ${i + 1}`, String(i))));
    $('variantSelect').value = String(Math.min(s.variant || 0, Math.max(0, first.length - 1)));
    computeVisible(ctx, +$('variantSelect').value || 0);
    renderMiddle(); renderAnimList(); selectSlot(E.slot);
    toast(null);
  } catch (err) { toast('Ошибка: ' + err.message); console.error(err); }
}

function classSkills(id) {
  const u = E.units[id] || {}, own = new Set([...(u.skills || [])]);
  for (const p of u.passives || []) for (const sid of Object.keys(E.skills)) if (sid.startsWith(p + '_')) own.add(sid);
  for (const sid of Object.keys(spec()?.skills || {})) own.add(sid);
  return [...own];
}

// ---------- вкладка «Эффекты навыков» ----------
async function selectSkill(id) {
  E.skill = id; E.slot = { kind: 'cast', key: id }; E.selPart = null;
  renderLeft();
  const token = ++E.token;
  const ctx = await loadModel('Effect', E.config.effects_file || 'Battle_Effect');
  if (token !== E.token) return;
  E.ctx = ctx; computeVisible(ctx, 0);
  renderMiddle(); renderAnimList(); previewSkillFx();
}
function previewSkillFx() {
  const parts = [...slotParts({ kind: 'cast', key: E.skill }), ...slotParts({ kind: 'hit', key: E.skill })];
  previewParts(parts);
}

// ---------- вкладка «Фоны» ----------
function bgConf() { return E.config.backgrounds[E.bgName]; }
function layerRole(anim) {
  const own = (bgConf().layers || {})[anim];
  return own || (BG_HIDDEN.test(anim) ? 'hidden' : BG_FRONT.test(anim) ? 'front' : 'back');
}
async function selectBg(name) {
  E.bgName = name; E.slot = null; E.selPart = null;
  renderLeft();
  const token = ++E.token;
  toast('Загрузка ' + name + '…');
  const ctx = await loadModel('BattleBG', name);
  if (token !== E.token) return;
  E.ctx = ctx; computeVisible(ctx, 0); toast(null);
  E.preview = { scene: true, length: Math.max(...ctx.model.anims.map(a => a.length), 1) };
  E.t = 0; $('timeline').max = E.preview.length - 1;
  fitBox(BG_BOX);
  renderMiddle(); renderAnimList();
}
function setLayerRole(anim, role) {
  const b = bgConf(); b.layers = b.layers || {};
  const auto = BG_HIDDEN.test(anim) ? 'hidden' : BG_FRONT.test(anim) ? 'front' : 'back';
  if (role === auto) delete b.layers[anim]; else b.layers[anim] = role;
  if (!Object.keys(b.layers).length) delete b.layers;
  markDirty(); renderMiddle();
}

// ---------- середина ----------
function renderMiddle() {
  $('charsPanel').hidden = E.tab !== 'chars'; $('fxPanel').hidden = E.tab !== 'fx'; $('bgPanel').hidden = E.tab !== 'bg';
  if (E.tab === 'chars') {
    const box = $('states'), sk = $('skills'); box.textContent = ''; sk.textContent = '';
    if (!spec()) { box.innerHTML = '<p class="muted">У класса нет файла — в игре он рисуется обычным спрайтом. Выберите файл выше.</p>'; }
    else if (E.ctx) {
      for (const state of Object.keys(E.config.states)) box.appendChild(slotBox({ kind: 'state', key: state }, STATE_LABELS[state] || state));
      const list = classSkills(E.cls);
      if (!list.length) sk.innerHTML = '<p class="muted">У класса в проекте нет навыков.</p>';
      for (const sid of list) sk.appendChild(slotBox({ kind: 'skill', key: sid }, E.skills[sid]?.name || sid,
        (spec().skills || {})[sid] ? '' : ' <span class="badge">как атака</span>'));
    }
  } else if (E.tab === 'fx') {
    const box = $('fxSlots'); box.textContent = '';
    if (!E.skill || !E.ctx) return;
    const f = (E.config.skill_fx || {})[E.skill] || {};
    $('fxName').textContent = `${E.skills[E.skill].name} (${E.skill})`;
    $('fxNote').textContent = f.generic ? 'Своего эффекта у навыка в игре не нашлось — стоит общий удар по стихии и виду удара. Можно выбрать другой.' : '';
    box.appendChild(slotBox({ kind: 'cast', key: E.skill }, 'Каст — на применившем'));
    box.appendChild(slotBox({ kind: 'hit', key: E.skill }, 'Попадание — на цели'));
  } else if (E.tab === 'bg') {
    const box = $('layers'); box.textContent = '';
    if (!E.bgName) return;
    const b = bgConf();
    $('bgName').textContent = E.bgName;
    $('bgUse').checked = !!b.use;
    $('bgScene').value = b.scene || '';
    $('bgFloor').value = b.floor ?? 420; $('bgFloorRange').value = b.floor ?? 420;
    if (!E.ctx) return;
    for (const a of E.ctx.model.anims) {
      if (a.name.startsWith('#')) continue;
      const role = layerRole(a.name), row = document.createElement('div');
      row.className = 'layer ' + role;
      row.innerHTML = `<span class="n">${a.name}${a.length > 1 ? ` <span class="muted">${(a.length / TICKS).toFixed(1)} с</span>` : ''}</span>`;
      for (const r of ['back', 'front', 'hidden']) {
        const lb = document.createElement('label'); lb.className = 'chk';
        const rb = document.createElement('input'); rb.type = 'radio'; rb.name = 'role_' + a.name; rb.checked = role === r;
        rb.onchange = () => setLayerRole(a.name, r);
        lb.append(rb, ROLE_LABELS[r]); row.appendChild(lb);
      }
      box.appendChild(row);
    }
  }
  showPartEditor();
}

// ---------- список анимаций ----------
function renderAnimList() {
  const tb = document.querySelector('#animList tbody'); tb.textContent = '';
  $('animTools').hidden = $('animListWrap').hidden = E.tab === 'bg';
  $('hideTalkLabel').hidden = E.tab !== 'chars';
  if (!E.ctx || E.tab === 'bg') return;
  const tokens = $('animSearch').value.trim().toUpperCase().split(/\s+/).filter(Boolean);
  const hideTalk = $('hideTalk').checked && E.tab === 'chars', bad = E.tab === 'chars' ? broken() : new Set();
  const uses = {};
  const note = (slot, label) => { for (const p of slotParts(slot)) (uses[p.anim] = uses[p.anim] || []).push(label); };
  if (E.tab === 'chars' && spec()) {
    for (const s of Object.keys(E.config.states)) note({ kind: 'state', key: s }, STATE_LABELS[s] || s);
    for (const sid of Object.keys(spec().skills || {})) note({ kind: 'skill', key: sid }, E.skills[sid]?.name || sid);
  } else if (E.tab === 'fx' && E.skill) { note({ kind: 'cast', key: E.skill }, 'каст'); note({ kind: 'hit', key: E.skill }, 'попадание'); }
  const target = E.slot ? slotLabel(E.slot) : '';
  for (const name of names()) {
    if (hideTalk && TALK.test(name) && !uses[name]) continue;
    if (!tokens.every(t => t.startsWith('-') ? !name.includes(t.slice(1)) : name.includes(t))) continue;
    const a = animByName(name), tr = document.createElement('tr');
    if (bad.has(name)) tr.classList.add('broken');
    if (E.preview && E.preview.parts && E.preview.parts.length === 1 && E.preview.parts[0].anim === name) tr.classList.add('cur');
    tr.innerHTML = `<td>${name}</td><td>${a.length}</td><td>${(a.length / TICKS).toFixed(2)}</td><td class="uses">${(uses[name] || []).join(', ')}</td><td class="acts"></td>`;
    tr.onclick = () => { previewParts([{ anim: name }]); renderAnimList(); };
    const acts = tr.querySelector('.acts');
    if (E.slot) acts.appendChild(button(`+ ${target}`, 'Добавить в выбранное', e => { e.stopPropagation(); addPart(name); }));
    if (E.tab === 'chars') acts.appendChild(button(bad.has(name) ? 'не битая' : 'битая', 'Битые анимации правила не выбирают', e => { e.stopPropagation(); toggleBroken(name); }));
    tb.appendChild(tr);
  }
}
function toggleBroken(name) {
  const all = E.config.broken = E.config.broken || {}, list = new Set(all[E.ctx.file] || []);
  list.has(name) ? list.delete(name) : list.add(name);
  if (list.size) all[E.ctx.file] = [...list].sort(); else delete all[E.ctx.file];
  markDirty(); renderMiddle(); renderAnimList();
}

// ---------- просмотр ----------
function previewParts(parts, loop = false) {
  E.preview = parts.length ? { parts: parts.map(p => ({ ...p })), loop } : null;
  E.t = 0; $('timeline').max = Math.max(0, previewLength() - 1);
  fit(); if (!E.playing) togglePlay(); renderAnimList();
}
function previewLength() {
  if (!E.preview) return 0;
  return E.preview.scene ? E.preview.length : E.preview.parts.reduce((s, p) => s + partLength(p), 0);
}
function previewAt(t) {
  let acc = 0;
  for (let i = 0; i < E.preview.parts.length; i++) {
    const p = E.preview.parts[i], len = partLength(p);
    if (t < acc + len || i === E.preview.parts.length - 1) return { i, p, tick: partTick(p, Math.min(len - 1, t - acc)) };
    acc += len;
  }
  return null;
}
function items(t, role) {
  if (!E.ctx || !E.preview) return [];
  const m = E.ctx.model;
  if (E.preview.scene) {            // фон: все слои сцены своей роли, каждый по кругу
    const out = [];
    for (const a of m.anims) if (!a.name.startsWith('#') && layerRole(a.name) === role)
      for (const it of evalAnim(m, a, Math.floor(t) % Math.max(1, a.length), { loop: true, interp: true })) out.push(it);
    return out;
  }
  const at = previewAt(Math.floor(t)), a = at && animByName(at.p.anim);
  return a ? evalAnim(m, a, at.tick, { loop: E.preview.loop, interp: true }) : [];
}
function fitBox(b) {
  const st = $('stage');
  E.cam.x = (b[0] + b[2]) / 2; E.cam.y = (b[1] + b[3]) / 2;
  E.cam.zoom = Math.min(3, Math.min(st.clientWidth / Math.max(1, b[2] - b[0]), st.clientHeight / Math.max(1, b[3] - b[1])) * 0.92);
}
function fit() {
  if (!E.preview || !E.ctx) return;
  if (E.preview.scene) return fitBox(BG_BOX);
  let b = null;
  const total = previewLength();
  for (let t = 0; t < total; t += Math.max(1, Math.floor(total / 40))) {
    const bb = itemsBBox(E.ctx.model, items(t), E.ctx.visible);
    if (bb) b = b ? [Math.min(b[0], bb[0]), Math.min(b[1], bb[1]), Math.max(b[2], bb[2]), Math.max(b[3], bb[3])] : bb;
  }
  fitBox(b || [-100, -300, 100, 0]);
}
function loop(ts) {
  const dt = E.last ? Math.min(0.1, (ts - E.last) / 1000) : 0; E.last = ts;
  const total = previewLength();
  if (E.playing && total) E.t = (E.t + dt * TICKS * +$('speed').value) % total;
  draw(); requestAnimationFrame(loop);
}
function draw() {
  const cv = $('view'), st = $('stage'), dpr = window.devicePixelRatio || 1;
  const w = Math.round(st.clientWidth * dpr), h = Math.round(st.clientHeight * dpr);
  if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
  const ctx = cv.getContext('2d'), bg = $('bg').value;
  if (bg === 'checker') { ctx.fillStyle = '#555'; ctx.fillRect(0, 0, w, h); ctx.fillStyle = '#444'; for (let y = 0; y < h; y += 16) for (let x = (y / 16) % 2 ? 16 : 0; x < w; x += 32) ctx.fillRect(x, y, 16, 16); }
  else { ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h); }
  if (!E.ctx || !E.preview) { $('hud').textContent = E.ctx ? 'нечего показывать' : ''; return; }
  const z = E.cam.zoom * dpr, view = { w, h, scale: z, ox: w / 2 - E.cam.x * z, oy: h / 2 - E.cam.y * z };
  const opts = { visible: E.ctx.visible, masks: true };
  const total = previewLength();
  if (E.preview.scene) {
    R.draw(E.ctx.model, E.ctx.pages, items(E.t, 'back'), view, opts); ctx.drawImage(R.canvas, 0, 0);
    drawFloor(ctx, view);
    R.draw(E.ctx.model, E.ctx.pages, items(E.t, 'front'), view, opts); ctx.drawImage(R.canvas, 0, 0);
    $('hud').textContent = `${E.bgName}  ${(E.t / TICKS).toFixed(1)} / ${(total / TICKS).toFixed(1)} с`;
  } else {
    R.draw(E.ctx.model, E.ctx.pages, items(E.t), view, opts); ctx.drawImage(R.canvas, 0, 0);
    ctx.strokeStyle = 'rgba(255,255,255,.3)'; ctx.beginPath();
    ctx.moveTo(view.ox, 0); ctx.lineTo(view.ox, h); ctx.moveTo(0, view.oy); ctx.lineTo(w, view.oy); ctx.stroke();
    const at = previewAt(Math.floor(E.t));
    $('hud').textContent = `часть ${at.i + 1}/${E.preview.parts.length}  ${at.p.anim}  тик ${Math.floor(at.tick)}\nвремя ${(E.t / TICKS).toFixed(2)} / ${(total / TICKS).toFixed(2)} с`;
  }
  $('timeline').value = Math.floor(E.t); $('timeText').textContent = `${Math.floor(E.t)} / ${total}`;
}
function drawFloor(ctx, view) {          // пол и силуэты роста человека: три колонны с каждой стороны
  const floor = bgConf().floor ?? 420, z = view.scale, y = floor * z + view.oy;
  ctx.strokeStyle = '#ffcc33'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(view.w, y); ctx.stroke();
  ctx.fillStyle = 'rgba(200,210,230,.35)'; ctx.strokeStyle = 'rgba(255,255,255,.6)'; ctx.lineWidth = 1;
  for (const x of [-620, -420, -220, 220, 420, 620]) {
    const cx = x * z + view.ox, hh = 300 * z, ww = 90 * z;
    ctx.beginPath(); ctx.ellipse(cx, y - hh * 0.88, ww * 0.22, hh * 0.1, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillRect(cx - ww / 2, y - hh * 0.76, ww, hh * 0.76); ctx.strokeRect(cx - ww / 2, y - hh * 0.76, ww, hh * 0.76);
  }
}
function togglePlay() { E.playing = !E.playing; $('play').textContent = E.playing ? '⏸' : '▶'; }
function step(d) { if (E.playing) togglePlay(); const total = previewLength(); if (total) E.t = (Math.floor(E.t) + d + total) % total; }

// ---------- сохранение ----------
async function save() { await api('/api/config', E.config); markDirty(false); renderLeft(); toast('Сохранено в data/uo_anim.json', 1500); }
// ---------- вкладки и запуск ----------
function switchTab(tab) {
  cancelAdd();
  E.tab = tab; E.ctx = null; E.preview = null; E.slot = null; E.selPart = null; E.token++;
  for (const b of document.querySelectorAll('#tabs button')) b.classList.toggle('active', b.dataset.tab === tab);
  $('leftSearch').value = ''; $('leftFilter').checked = false;
  renderLeft(); renderMiddle(); renderAnimList();
  if (tab === 'chars' && E.cls) selectClass(E.cls);
  if (tab === 'fx' && E.skill) selectSkill(E.skill);
  if (tab === 'bg' && E.bgName) selectBg(E.bgName);
}

async function init() {
  try { R = new Renderer(); } catch (e) { alert(e.message); return; }
  [E.config, E.units, E.files, E.skills, E.scenes] = await Promise.all(
    [api('/api/config'), api('/api/units'), api('/api/files'), api('/api/skills'), api('/api/scenes')]);
  E.config.backgrounds = E.config.backgrounds || {};
  markDirty(false);
  for (const b of document.querySelectorAll('#tabs button')) b.onclick = () => switchTab(b.dataset.tab);
  $('leftSearch').oninput = renderLeft; $('leftFilter').onchange = renderLeft;
  $('animSearch').oninput = renderAnimList; $('hideTalk').onchange = renderAnimList;
  $('save').onclick = save;
  $('play').onclick = togglePlay; $('stepBack').onclick = () => step(-1); $('stepFwd').onclick = () => step(1);
  $('timeline').oninput = () => { if (E.playing) togglePlay(); E.t = +$('timeline').value; };
  $('fileSelect').onchange = async () => {
    const v = $('fileSelect').value;
    if (!v) delete E.config.classes[E.cls];
    else {
      const [folder, file] = v.split('/'), old = spec() || {};
      E.config.classes[E.cls] = { ...old, file }; if (folder !== 'Chara') E.config.classes[E.cls].folder = folder; else delete E.config.classes[E.cls].folder;
      if (old.file && old.file !== file && (old.states || old.skills)) toast('Файл другой: выбранные анимации, которых в нём нет, не будут использованы', 4000);
    }
    markDirty(); renderLeft(); await openClassModel();
  };
  $('variantSelect').onchange = () => { const v = +$('variantSelect').value; if (v) spec().variant = v; else delete spec().variant; computeVisible(E.ctx, v); markDirty(); fit(); };
  $('skinSelect').onchange = async () => { await loadSkin(E.ctx, $('skinSelect').value); };
  $('partFrom').onchange = () => editPart(+$('partFrom').value, +$('partTo').value);
  $('partTo').onchange = () => editPart(+$('partFrom').value, +$('partTo').value);
  $('addZone').onclick = addZone;
  $('addFrom').onchange = pendingChanged; $('addTo').onchange = pendingChanged;
  $('addNow1').onclick = () => { const a = previewAt(Math.floor(E.t)); if (a && E.pending) { $('addFrom').value = a.tick; pendingChanged(); } };
  $('addNow2').onclick = () => { const a = previewAt(Math.floor(E.t)); if (a && E.pending) { $('addTo').value = a.tick + 1; pendingChanged(); } };
  $('addOk').onclick = confirmAdd; $('addCancel').onclick = cancelAdd;
  $('partFromNow').onclick = () => { const p = selectedPart(); if (p && E.preview) editPart(previewAt(Math.floor(E.t)).tick, p.to ?? 1e9); };
  $('partToNow').onclick = () => { const p = selectedPart(); if (p && E.preview) editPart(p.from || 0, previewAt(Math.floor(E.t)).tick + 1); };
  $('partReset').onclick = () => editPart(0, 1e9);
  $('bgScene').add(new Option('—', ''));
  for (const [id, name] of Object.entries(E.scenes)) $('bgScene').add(new Option(`${name} (${id})`, id));
  $('bgUse').onchange = () => { bgConf().use = $('bgUse').checked; markDirty(); renderLeft(); };
  $('bgScene').onchange = () => { bgConf().scene = $('bgScene').value || null; markDirty(); renderLeft(); };
  const setFloor = v => { bgConf().floor = Math.round(+v); $('bgFloor').value = bgConf().floor; $('bgFloorRange').value = bgConf().floor; markDirty(); };
  $('bgFloor').onchange = () => setFloor($('bgFloor').value); $('bgFloorRange').oninput = () => setFloor($('bgFloorRange').value);
  const st = $('stage'); let drag = null;
  st.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, cx: E.cam.x, cy: E.cam.y }; st.setPointerCapture(e.pointerId); });
  st.addEventListener('pointermove', e => { if (drag) { E.cam.x = drag.cx - (e.clientX - drag.x) / E.cam.zoom; E.cam.y = drag.cy - (e.clientY - drag.y) / E.cam.zoom; } });
  st.addEventListener('pointerup', () => { drag = null; });
  st.addEventListener('wheel', e => { e.preventDefault(); E.cam.zoom = Math.max(0.05, Math.min(20, E.cam.zoom * Math.exp(-e.deltaY * 0.0015))); }, { passive: false });
  st.addEventListener('dblclick', fit);
  window.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') { e.preventDefault(); save(); return; }
    if (e.target.tagName === 'INPUT' && !['checkbox', 'range', 'radio'].includes(e.target.type)) return;
    if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
    else if (e.code === 'ArrowLeft') step(-1); else if (e.code === 'ArrowRight') step(1);
  });
  window.addEventListener('beforeunload', e => { if (E.dirty) { e.preventDefault(); e.returnValue = ''; } });
  renderLeft(); requestAnimationFrame(loop);
  const tab = new URLSearchParams(location.search).get('tab');
  if (tab) switchTab(tab);
  if (E.tab === 'chars') { const first = Object.keys(E.units).find(id => E.config.classes[id]); if (first) selectClass(first); }
  if (E.tab === 'fx') selectSkill(Object.keys(E.skills).find(id => !(E.config.skill_fx?.[id]?.generic)) || Object.keys(E.skills)[0]);
  if (E.tab === 'bg') selectBg(Object.keys(E.config.backgrounds)[0]);
}

init();
