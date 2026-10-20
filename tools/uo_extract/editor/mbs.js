// Vanillaware FMBS parser + animation evaluator (Unicorn Overlord, Switch).
// See tools/mbs.py for the section layout notes.
'use strict';

function parseMBS(buf) {
  const dv = new DataView(buf);
  const magic = String.fromCharCode(...new Uint8Array(buf, 0, 4));
  if (magic !== 'FMBS') throw new Error('not FMBS');
  const offs = [];
  for (let i = 0; i < 12; i++) offs.push(Number(dv.getBigUint64(0xB0 + 8 * i, true)));
  const nParts = dv.getUint32(0x50, true), nCol = dv.getUint32(0x54, true),
    nUV = dv.getUint32(0x58, true), nXY = dv.getUint32(0x5C, true), nBox = dv.getUint32(0x60, true);
  const n5 = dv.getUint16(0x64, true), nTr = dv.getUint16(0x66, true), nKey = dv.getUint16(0x68, true),
    nFrame = dv.getUint16(0x6A, true), nAnim = dv.getUint16(0x6C, true), nTrack = dv.getUint16(0x6E, true),
    n11 = dv.getUint16(0x72, true);
  const f32 = (o, n) => new Float32Array(buf.slice(o, o + n * 4));
  const dec = new TextDecoder('ascii');
  const cstr = (o, n) => { const b = new Uint8Array(buf, o, n); let e = b.indexOf(0); if (e < 0) e = n; return dec.decode(b.subarray(0, e)); };

  const m = {
    name: cstr(0x80, 0x30),
    counts: { parts: nParts, colors: nCol, uv: nUV, xy: nXY, boxes: nBox, s5: n5, transforms: nTr, keys: nKey, frames: nFrame, anims: nAnim, tracks: nTrack, s11: n11 },
    colors: new Uint8Array(buf.slice(offs[0], offs[0] + nCol * 24)),
    uv: f32(offs[1], nUV * 12),
    xy: f32(offs[2], nXY * 12),
  };
  // parts (20 B)
  const P = { id: new Uint32Array(nParts), grp: new Uint8Array(nParts), blend: new Uint8Array(nParts), page: new Uint8Array(nParts),
    sub: new Uint8Array(nParts), flags: new Uint32Array(nParts), uv: new Uint32Array(nParts), col: new Uint32Array(nParts), xy: new Uint32Array(nParts) };
  for (let i = 0, o = offs[4]; i < nParts; i++, o += 20) {
    P.id[i] = dv.getUint32(o, true); P.grp[i] = dv.getUint8(o + 4); P.blend[i] = dv.getUint8(o + 5);
    P.sub[i] = dv.getUint8(o + 6); P.page[i] = dv.getUint8(o + 7); P.flags[i] = dv.getUint32(o + 8, true);
    const uc = dv.getUint32(o + 12, true); P.uv[i] = uc & 0xFFFF; P.col[i] = uc >>> 16; P.xy[i] = dv.getUint32(o + 16, true);
  }
  m.parts = P;
  m.frames = [];
  for (let i = 0, o = offs[6]; i < nFrame; i++, o += 28) {
    const info = dv.getUint32(o + 20, true);
    m.frames.push({ bbox: [dv.getFloat32(o, true), dv.getFloat32(o + 4, true), dv.getFloat32(o + 8, true), dv.getFloat32(o + 12, true)],
      start: dv.getUint32(o + 16, true), count: info >>> 16, info: info & 0xFFFF, flags: dv.getUint32(o + 24, true) });
  }
  m.transforms = [];
  for (let i = 0, o = offs[7]; i < nTr; i++, o += 36) {
    m.transforms.push({ tx: dv.getFloat32(o, true), ty: dv.getFloat32(o + 4, true), tz: dv.getFloat32(o + 8, true),
      rx: dv.getFloat32(o + 12, true), ry: dv.getFloat32(o + 16, true), rz: dv.getFloat32(o + 20, true),
      sx: dv.getFloat32(o + 24, true), sy: dv.getFloat32(o + 28, true),
      r: dv.getUint8(o + 32) / 255, g: dv.getUint8(o + 33) / 255, b: dv.getUint8(o + 34) / 255, a: dv.getUint8(o + 35) / 255 });
  }
  m.keys = [];
  for (let i = 0, o = offs[8]; i < nKey; i++, o += 32) {
    m.keys.push({ frame: dv.getUint32(o, true), tr: dv.getUint16(o + 4, true), dur: dv.getUint16(o + 6, true),
      flags: dv.getUint32(o + 8, true), f2: dv.getUint32(o + 12, true), f3: dv.getUint32(o + 16, true) });
  }
  m.tracks = [];
  for (let i = 0, o = offs[10]; i < nTrack; i++, o += 24) {
    const t = { kstart: dv.getUint16(o, true), kcount: dv.getUint16(o + 2, true), length: dv.getUint32(o + 4, true),
      loopKey: dv.getInt32(o + 8, true), i1: dv.getInt32(o + 12, true), flags: dv.getUint32(o + 16, true), layer: dv.getUint32(o + 20, true) };
    // порядок показа ключей: с ключа st, прыжки (0x4) на ключ st+loop, конец по 0x800 или возврату на пройденный
    const st = (t.flags >>> 24) & 0xFF, first = st < t.kcount ? st : 0;
    const order = [], seen = new Map();
    let i2 = first, loopIdx = -1;
    while (i2 >= 0 && i2 < t.kcount && order.length < t.kcount) {
      if (seen.has(i2)) { loopIdx = seen.get(i2); break; }
      seen.set(i2, order.length); order.push(i2);
      const key = m.keys[t.kstart + i2];
      if (key.flags & 0x4) i2 = first + (key.f2 & 0xFFFF);
      else if (key.flags & 0x800) break;
      else i2++;
    }
    t.order = order; t.loopIdx = loopIdx;
    // cumulative key start times
    t.times = []; let acc = 0;
    for (const k of order) { t.times.push(acc); acc += Math.max(1, m.keys[t.kstart + k].dur); }
    t.total = acc;
    t.loopTick = loopIdx >= 0 ? t.times[loopIdx] : -1;
    m.tracks.push(t);
  }
  m.anims = [];
  for (let i = 0, o = offs[9]; i < nAnim; i++, o += 48) {
    const a = { index: i, bbox: [dv.getFloat32(o, true), dv.getFloat32(o + 4, true), dv.getFloat32(o + 8, true), dv.getFloat32(o + 12, true)],
      name: cstr(o + 16, 24), tstart: dv.getUint16(o + 40, true), tcount: dv.getUint8(o + 42), aflags: dv.getUint8(o + 43) };
    a.length = 0;
    for (let t = 0; t < a.tcount; t++) a.length = Math.max(a.length, m.tracks[a.tstart + t]?.total || 0);
    if (!a.name) a.name = `#${i}`;
    m.anims.push(a);
  }
  return m;
}

// Matrix [a,b,c,d,e,f]: x' = a*x + c*y + e ; y' = b*x + d*y + f
function transformMatrix(t) {
  const cx = Math.cos(t.rx), sx = Math.sin(t.rx), cy = Math.cos(t.ry), sy = Math.sin(t.ry),
    cz = Math.cos(t.rz), sz = Math.sin(t.rz);
  // R = Rx * Ry * Rz (orthographic projection keeps the x/y rows)
  const r00 = cy * cz, r01 = -cy * sz;
  const r10 = sx * sy * cz + cx * sz, r11 = -sx * sy * sz + cx * cz;
  return [r00 * t.sx, r10 * t.sx, r01 * t.sy, r11 * t.sy, t.tx, t.ty];
}

function lerpTransform(a, b, f) {
  const L = (x, y) => x + (y - x) * f;
  let dr = b.rz - a.rz;
  return { tx: L(a.tx, b.tx), ty: L(a.ty, b.ty), tz: 0, rx: L(a.rx, b.rx), ry: L(a.ry, b.ry), rz: a.rz + dr * f,
    sx: L(a.sx, b.sx), sy: L(a.sy, b.sy), r: L(a.r, b.r), g: L(a.g, b.g), b: L(a.b, b.b), a: L(a.a, b.a) };
}

// Find key index within a track for tick t (handles loop key / hold last)
function trackKeyAt(m, track, t, loop) {
  if (!track.order || !track.order.length) return null;
  let tt = t;
  const start = track.loopTick >= 0 ? track.loopTick : (track.loopKey >= 0 ? track.loopKey : (loop ? 0 : -1));
  if (tt >= track.total) {
    if (start >= 0) {
      const span = Math.max(1, track.total - start);
      tt = start + ((tt - start) % span);
    } else {
      return { k: track.order.length - 1, frac: 0, hold: true };
    }
  }
  // binary search
  let lo = 0, hi = track.order.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (track.times[mid] <= tt) lo = mid; else hi = mid - 1; }
  const dur = Math.max(1, m.keys[track.kstart + track.order[lo]].dur);
  return { k: lo, frac: (tt - track.times[lo]) / dur, hold: false };
}

// Evaluate animation at tick t -> list of {frame, matrix, color}
function evalAnim(m, anim, t, opts) {
  const out = [];
  for (let ti = 0; ti < anim.tcount; ti++) {
    const ix = anim.tstart + ti;
    if (opts.hiddenTracks && opts.hiddenTracks.has(ti)) continue;
    const track = m.tracks[ix];
    const pos = trackKeyAt(m, track, t, opts.loop);
    if (!pos) continue;
    const key = m.keys[track.kstart + track.order[pos.k]];
    if (key.flags & 0x40) continue; // key used as a pause: the track draws nothing
    let tr = m.transforms[key.tr] || IDENTITY_TR;
    let morph = null;
    if (opts.interp && !pos.hold) {
      let nk = pos.k + 1;
      if (nk >= track.order.length && track.loopIdx >= 0) nk = track.loopIdx;
      if (nk < track.order.length && nk !== pos.k) {
        const next = m.keys[track.kstart + track.order[nk]];
        if (key.flags & 0x400) tr = lerpTransform(tr, m.transforms[next.tr] || IDENTITY_TR, pos.frac);
        if (key.flags & 0x4) morph = { frame: next.frame, f: pos.frac };
      }
    }
    out.push({ track: ti, key: track.kstart + track.order[pos.k], frame: key.frame, tr, morph, keyFlags: key.flags });
  }
  return out;
}

const IDENTITY_TR = { tx: 0, ty: 0, tz: 0, rx: 0, ry: 0, rz: 0, sx: 1, sy: 1, r: 1, g: 1, b: 1, a: 1 };
