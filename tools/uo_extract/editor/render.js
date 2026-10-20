// WebGL2 renderer for MBS frames. Draws into its own canvas; the app copies the result.
'use strict';

// blend mode = low byte of part field c: 0 normal, 1 additive (glows), 2 multiply (shading), 3 treated as additive
const BLEND_NORMAL = 0, BLEND_ADD = 1, BLEND_MUL = 2;

class Renderer {
  constructor() {
    this.canvas = document.createElement('canvas');
    const gl = this.gl = this.canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true, antialias: true, stencil: true });
    if (!gl) throw new Error('WebGL2 не поддерживается браузером');
    const vs = `#version 300 es
      in vec2 aPos; in vec2 aUV; in vec4 aCol;
      uniform vec4 uView; // scale, ox, oy, unused
      uniform vec2 uSize;
      out vec2 vUV; out vec4 vCol;
      void main() {
        vec2 p = aPos * uView.x + uView.yz;
        gl_Position = vec4(p.x / uSize.x * 2.0 - 1.0, 1.0 - p.y / uSize.y * 2.0, 0.0, 1.0);
        vUV = aUV; vCol = aCol;
      }`;
    const fs = `#version 300 es
      precision mediump float;
      in vec2 vUV; in vec4 vCol; uniform sampler2D uTex; uniform float uAlphaTest; out vec4 o;
      void main() { vec4 t = texture(uTex, vUV); o = vec4(t.rgb * vCol.rgb * vCol.a, t.a * vCol.a);
        if (o.a < uAlphaTest) discard; }`;
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    const p = this.prog = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    this.uView = gl.getUniformLocation(p, 'uView'); this.uSize = gl.getUniformLocation(p, 'uSize');
    this.uAlphaTest = gl.getUniformLocation(p, 'uAlphaTest');
    this.vbo = gl.createBuffer();
    this.vao = gl.createVertexArray();
    gl.bindVertexArray(this.vao); gl.bindBuffer(gl.ARRAY_BUFFER, this.vbo);
    const loc = n => gl.getAttribLocation(p, n);
    gl.enableVertexAttribArray(loc('aPos')); gl.vertexAttribPointer(loc('aPos'), 2, gl.FLOAT, false, 32, 0);
    gl.enableVertexAttribArray(loc('aUV')); gl.vertexAttribPointer(loc('aUV'), 2, gl.FLOAT, false, 32, 8);
    gl.enableVertexAttribArray(loc('aCol')); gl.vertexAttribPointer(loc('aCol'), 4, gl.FLOAT, false, 32, 16);
    this.verts = new Float32Array(1 << 18);
    this.textures = new Map();
    this.white = this._makeTex(null);
  }

  _makeTex(img) {
    const gl = this.gl, t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    if (img) {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    } else {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([255, 0, 255, 255]));
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    }
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }

  // returns Promise<{tex, img}>
  loadTexture(url) {
    if (!this.textures.has(url)) {
      this.textures.set(url, new Promise((res, rej) => {
        const img = new Image();
        img.onload = () => res({ tex: this._makeTex(img), img, url });
        img.onerror = () => rej(new Error('не удалось загрузить ' + url));
        img.src = url;
      }));
    }
    return this.textures.get(url);
  }

  dropTextures(keep) {
    for (const [url, pr] of this.textures) {
      if (keep.has(url)) continue;
      pr.then(t => this.gl.deleteTexture(t.tex)).catch(() => {});
      this.textures.delete(url);
    }
  }

  /**
   * items: [{frame, tr, morph}]  pages: [{tex}]  view: {w, h, scale, ox, oy}
   * opts: {hiddenGroups:Set, visible:Uint8Array (per part), masks:bool, collect:bool, clear:[r,g,b,a]}
   * Masks: in frames flagged 0x100, parts with (b & 2) only write the stencil buffer. When such a
   * frame starts with a mask, the rest of the frame is clipped to it (e.g. blinking eyelids).
   * returns collected screen-space polygons when opts.collect
   */
  draw(m, pages, items, view, opts = {}) {
    const gl = this.gl, c = this.canvas;
    const W = Math.max(1, Math.round(view.w)), H = Math.max(1, Math.round(view.h));
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    gl.viewport(0, 0, W, H);
    const cl = opts.clear || [0, 0, 0, 0];
    gl.clearColor(cl[0], cl[1], cl[2], cl[3]); gl.clearStencil(0); gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
    gl.useProgram(this.prog); gl.bindVertexArray(this.vao);
    gl.uniform4f(this.uView, view.scale, view.ox, view.oy, 0); gl.uniform2f(this.uSize, W, H);
    gl.enable(gl.BLEND);
    const P = m.parts, polys = opts.collect ? [] : null;
    let v = this.verts, n = 0, curPage = -1, curBlend = -1, curSt = -1;
    const ST_NONE = 0, ST_WRITE = 1, ST_TEST = 2;
    const flush = () => {
      if (!n) return;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.vbo);
      gl.bufferData(gl.ARRAY_BUFFER, v.subarray(0, n * 8), gl.STREAM_DRAW);
      gl.bindTexture(gl.TEXTURE_2D, pages[curPage]?.tex || this.white);
      if (curBlend === BLEND_ADD) gl.blendFunc(gl.ONE, gl.ONE);
      else if (curBlend === BLEND_MUL) gl.blendFunc(gl.DST_COLOR, gl.ONE_MINUS_SRC_ALPHA);
      else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      if (curSt === ST_WRITE) {
        gl.enable(gl.STENCIL_TEST); gl.stencilFunc(gl.ALWAYS, 1, 0xFF); gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
        gl.colorMask(false, false, false, false); gl.uniform1f(this.uAlphaTest, 0.1);
      } else if (curSt === ST_TEST) {
        gl.enable(gl.STENCIL_TEST); gl.stencilFunc(gl.EQUAL, 1, 0xFF); gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      }
      gl.drawArrays(gl.TRIANGLES, 0, n); n = 0;
      gl.disable(gl.STENCIL_TEST); gl.colorMask(true, true, true, true); gl.uniform1f(this.uAlphaTest, 0);
    };
    gl.uniform1f(this.uAlphaTest, 0);
    const xs = new Float32Array(6), ys = new Float32Array(6);
    for (const it of items) {
      const fr = m.frames[it.frame];
      if (!fr || !fr.count) continue;
      const M = transformMatrix(it.tr || IDENTITY_TR);
      const tr = it.tr || IDENTITY_TR;
      let mfr = null, mf = 0;
      if (it.morph) { const f2 = m.frames[it.morph.frame]; if (f2 && f2.count === fr.count && it.morph.frame !== it.frame) { mfr = f2; mf = it.morph.f; } }
      const maskFrame = opts.masks !== false && (fr.flags & 0x100);
      let clip = false, first = true;
      if (maskFrame) { flush(); gl.clear(gl.STENCIL_BUFFER_BIT); }
      for (let i = 0; i < fr.count; i++) {
        const p = fr.start + i;
        if (opts.hiddenGroups && opts.hiddenGroups.has(P.grp[p])) continue;
        if (opts.visible && !opts.visible[p]) continue;
        const isMask = maskFrame && (P.blend[p] & 2);
        if (first) { clip = !!isMask; first = false; }
        const st = isMask ? ST_WRITE : clip ? ST_TEST : ST_NONE;
        // part-level blend mode (c low byte)
        const page = P.page[p], blend = P.sub[p] === 2 ? BLEND_MUL : P.sub[p] ? BLEND_ADD : BLEND_NORMAL;
        if (page !== curPage || blend !== curBlend || st !== curSt || n + 12 > v.length / 8) { flush(); curPage = page; curBlend = blend; curSt = st; }
        const xo = P.xy[p] * 12, uo = P.uv[p] * 12, co = P.col[p] * 24;
        const xo2 = mfr ? P.xy[mfr.start + i] * 12 : -1;
        for (let k = 0; k < 6; k++) {
          let x = m.xy[xo + 2 * k], y = m.xy[xo + 2 * k + 1];
          if (xo2 >= 0) { x += (m.xy[xo2 + 2 * k] - x) * mf; y += (m.xy[xo2 + 2 * k + 1] - y) * mf; }
          if (it.keyFlags & 1) x = -x;   // key flags bit 0/1: mirror the frame horizontally/vertically
          if (it.keyFlags & 2) y = -y;
          xs[k] = M[0] * x + M[2] * y + M[4]; ys[k] = M[1] * x + M[3] * y + M[5];
        }
        if (polys && !isMask) polys.push({ part: p, xs: Array.from(xs, x => x * view.scale + view.ox), ys: Array.from(ys, y => y * view.scale + view.oy) });
        for (let t = 1; t <= 4; t++) {
          for (const k of [0, t, t + 1]) {
            const o = n * 8;
            v[o] = xs[k]; v[o + 1] = ys[k];
            v[o + 2] = m.uv[uo + 2 * k]; v[o + 3] = m.uv[uo + 2 * k + 1];
            const cb = m.colors.length ? co + 4 * k : -1;
            v[o + 4] = (cb >= 0 ? m.colors[cb] / 255 : 1) * tr.r;
            v[o + 5] = (cb >= 0 ? m.colors[cb + 1] / 255 : 1) * tr.g;
            v[o + 6] = (cb >= 0 ? m.colors[cb + 2] / 255 : 1) * tr.b;
            v[o + 7] = (cb >= 0 ? m.colors[cb + 3] / 255 : 1) * tr.a;
            n++;
          }
        }
      }
    }
    flush();
    return polys;
  }
}

// Bounding box (model units) of evaluated items
function itemsBBox(m, items, visible) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const it of items) {
    const fr = m.frames[it.frame]; if (!fr || !fr.count) continue;
    const M = transformMatrix(it.tr || IDENTITY_TR);
    for (let i = 0; i < fr.count; i++) {
      if (visible && !visible[fr.start + i]) continue;
      if ((fr.flags & 0x100) && (m.parts.blend[fr.start + i] & 2)) continue;
      const xo = m.parts.xy[fr.start + i] * 12;
      for (let k = 1; k < 5; k++) {
        const x = (it.keyFlags & 1 ? -1 : 1) * m.xy[xo + 2 * k], y = (it.keyFlags & 2 ? -1 : 1) * m.xy[xo + 2 * k + 1];
        const X = M[0] * x + M[2] * y + M[4], Y = M[1] * x + M[3] * y + M[5];
        if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
      }
    }
  }
  return x0 === Infinity ? null : [x0, y0, x1, y1];
}
