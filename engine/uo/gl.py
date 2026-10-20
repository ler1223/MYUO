"""Отрисовка кукол Unicorn Overlord видеокартой (moderngl).

Логика та же, что в программной отрисовке (engine/uo/puppet.py) и в редакторе
(tools/uo_extract/editor/render.js):
- деталь — веер из 4 треугольников вокруг центра, текстура атласа × цвета вершин × цвет трека;
- смешивание: обычное, сложение (свечение), умножение (тени) — младший байт поля c детали;
- маски: в кадре с флагом 0x100 детали с b & 2 пишут маску и не рисуются; если кадр начинается
  с маски, остальные детали кадра видны только внутри неё (моргание);
- варианты внешности, отражение, интерполяция — в Puppet.evaluate / item_polys.

Кадр куклы — сетка (Mesh): вершины в единицах куклы лежат на видеокарте, масштаб, сдвиг и
отражение задаются при рисовании. Сетки кэшируются по ключу кадра (кукла, анимация, тик), так
что повторный кадр рисуется без пересчёта. Рисовать можно в любой буфер (engine.uo.frame —
кадр поля боя целиком, без чтения обратно) или в картинку (render — с чтением в numpy).

Контекст — отдельный (без окна) или контекст окна pygame в режиме OPENGL (use_window_context:
тогда текстуры живут там же, где рисуется окно). Без moderngl или видеокарты get() даёт None —
вызывающий код рисует обычные спрайты.

Соглашение о строках: пиксель (x, y) картинки (y вниз) — это строка y буфера; так чтение буфера
сразу даёт картинку сверху вниз, а при выводе в окно кадр переворачивается.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Optional

import numpy as np

from .puppet import ADD, MULTIPLY, NORMAL, Item, Puppet

try:
    import moderngl
except ImportError:          # нет зависимости — кукол нет, игра работает со спрайтами
    moderngl = None

FAN = np.array([0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 5])       # веер детали: 4 треугольника из 6 вершин
DRAW, MASK_WRITE, MASK_TEST, MASK_OUT = 0, 1, 2, 3
# Правило масок кадра (флаг кадра 0x100, детали с b & 2 пишут маску и не рисуются):
#   layer — группа масок обрезает следующие детали той же тысячи номеров слоя (поле a), остальные — без
#   маски (подтверждено кадрами: подол мантии обрезан по силуэту, тело в кадре с маской-лоскутом цело);
#   group_out — группа масок вырезает свою область у деталей после неё (до следующей группы);
#   group_in  — детали после группы видны только внутри её области; first_clip — прежнее правило
#   (кадр начинается с маски — всё обрезать по ней); none — маски только не рисуются.
MASK_RULE = "layer"
MESH_MB = 192                # сколько сеток держать на видеокарте

VERTEX = """
#version 330
in vec2 in_pos; in vec2 in_uv; in vec4 in_col;
uniform vec4 xf;            // масштаб x (со знаком отражения), масштаб y, сдвиг x, сдвиг y — в пикселях
uniform vec2 view;
out vec2 uv; out vec4 col;
void main() {
    vec2 p = in_pos * xf.xy + xf.zw;
    gl_Position = vec4(p.x / view.x * 2.0 - 1.0, p.y / view.y * 2.0 - 1.0, 0.0, 1.0);
    uv = in_uv; col = in_col;
}
"""
FRAGMENT = """
#version 330
in vec2 uv; in vec4 col;
uniform sampler2D tex;
uniform sampler2D mask;
uniform int mode;
uniform int glow;
uniform vec2 size;
out vec4 o;
void main() {
    vec4 t = texture(tex, uv);                      // атлас уже premultiplied
    vec4 c = vec4(t.rgb * col.rgb * col.a, t.a * col.a);
    if (mode == 1) { if (c.a < 0.1) discard; o = vec4(1.0); return; }
    if (mode == 2 && texture(mask, gl_FragCoord.xy / size).a < 0.5) discard;
    if (mode == 3 && texture(mask, gl_FragCoord.xy / size).a >= 0.5) discard;
    // сложение света: чёрное ничего не добавляет — и непрозрачности тоже (иначе на прозрачном фоне
    // вокруг вспышек остаются чёрные квадраты)
    if (glow == 1) c.a = max(c.r, max(c.g, c.b));
    o = c;
}
"""
# Наложение готовой текстуры прямоугольником (повёрнутым): кадр куклы, картинка pygame, слой.
QUAD_VERTEX = """
#version 330
in vec2 in_pos; in vec2 in_uv;
uniform vec2 view;
uniform int screen;          // 1 — в окно: строка 0 картинки — верх окна
out vec2 uv;
void main() {
    float y = in_pos.y / view.y * 2.0 - 1.0;
    gl_Position = vec4(in_pos.x / view.x * 2.0 - 1.0, screen == 1 ? -y : y, 0.0, 1.0);
    uv = in_uv;
}
"""
QUAD_FRAGMENT = """
#version 330
in vec2 uv;
uniform sampler2D src;
uniform int kind;            // 0 — premultiplied, 1 — обычная прозрачность (pygame), 2 — слой pygame со сложением
uniform vec3 mul;            // множитель цвета (белые заготовки красятся)
uniform vec3 add;            // свечение цветом
uniform float flash;         // вспышка белым 0..1
uniform float alpha;
out vec4 o;
void main() {
    vec4 t = texture(src, uv);
    vec4 c = t;
    if (kind == 1) c = vec4(t.rgb * t.a, t.a);
    if (kind == 2) c = t.a > 0.004 ? vec4(t.rgb * t.a, t.a) : vec4(t.rgb, max(t.r, max(t.g, t.b)));
    c.rgb *= mul;
    c.rgb += add * c.a;
    c.rgb = mix(c.rgb, vec3(c.a), flash);
    o = c * alpha;
}
"""
STRAIGHT_VERTEX = """
#version 330
void main() {   // один треугольник на весь кадр
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""
STRAIGHT_FRAGMENT = """
#version 330
uniform sampler2D src;
out vec4 o;
void main() {   // premultiplied -> обычный цвет (pygame ждёт его); на видеокарте, а не numpy
    vec4 c = texelFetch(src, ivec2(gl_FragCoord.xy), 0);
    o = c.a > 0.0 ? vec4(min(c.rgb / c.a, 1.0), c.a) : vec4(0.0);
}
"""


@dataclass
class Mesh:
    """Кадр куклы на видеокарте: вершины в единицах куклы и куски одинакового состояния."""

    vbo: Any
    vao: Any
    runs: list                         # (страница, смешивание, режим, очистить маску, первая вершина, число)
    box: tuple[float, float, float, float]    # рамка видимого в единицах куклы (без отражения)
    nbytes: int

    def release(self) -> None:
        self.vao.release()
        self.vbo.release()

    def frame_box(self, scale: float, flip: bool, pad: int = 2) -> tuple[float, float, int, int]:
        """(сдвиг x, сдвиг y точки 0,0 куклы в картинке, ширина, высота) при масштабе scale."""
        x0, y0, x1, y1 = self.box
        if flip:
            x0, x1 = -x1, -x0
        w = max(1, math.ceil((x1 - x0) * scale) + 2 * pad)
        h = max(1, math.ceil((y1 - y0) * scale) + 2 * pad)
        return pad - x0 * scale, pad - y0 * scale, w, h


class GLRenderer:
    """Один контекст на процесс: шейдеры, кэш сеток, рабочие буферы."""

    _instance: Optional["GLRenderer"] = None

    @classmethod
    def get(cls) -> Optional["GLRenderer"]:
        if cls._instance is None and moderngl is not None:
            try:
                cls._instance = GLRenderer(moderngl.create_standalone_context(require=330))
            except Exception:       # нет OpenGL 3.3 — работаем без кукол
                cls._instance = False
        return cls._instance or None

    @classmethod
    def use_window_context(cls) -> Optional["GLRenderer"]:
        """Рисовать в контексте окна pygame (окно уже открыто с флагом OPENGL). Вызывать до первой
        загрузки кукол: текстуры прежнего контекста в новом не видны."""
        if moderngl is None:
            return None
        try:
            cls._instance = GLRenderer(moderngl.create_context(require=330))
        except Exception:
            cls._instance = False
        return cls._instance or None

    def __init__(self, ctx):
        self.ctx = ctx
        self.prog = ctx.program(vertex_shader=VERTEX, fragment_shader=FRAGMENT)
        self.prog["tex"].value = 0
        self.prog["mask"].value = 1
        self.quad_prog = ctx.program(vertex_shader=QUAD_VERTEX, fragment_shader=QUAD_FRAGMENT)
        self.quad_prog["src"].value = 0
        self.quad_vbo = ctx.buffer(reserve=4 * 6 * 4 * 64, dynamic=True)
        self.quad_vao = ctx.vertex_array(self.quad_prog, [(self.quad_vbo, "2f 2f", "in_pos", "in_uv")])
        self.straight = ctx.program(vertex_shader=STRAIGHT_VERTEX, fragment_shader=STRAIGHT_FRAGMENT)
        self.straight["src"].value = 0
        self.straight_vao = ctx.vertex_array(self.straight, [])
        self.white = ctx.texture((1, 1), 4, bytes([255, 0, 255, 255]))
        self.meshes: OrderedDict[Hashable, Optional[Mesh]] = OrderedDict()
        self._mesh_bytes = 0
        self.temp = self.temp_fbo = None       # кадр одной куклы (render и наложение с прозрачностью)
        self.out = self.out_fbo = None         # он же в обычном цвете — для чтения
        self.mask = self.mask_fbo = None       # маска: общая, не меньше любого буфера рисования
        self.temp_size = self.mask_size = (0, 0)

    # --- текстуры и буферы ---

    def texture(self, rgba: np.ndarray):
        """Текстура атласа из RGBA uint8 (не premultiplied) с мипмапами."""
        a = rgba[..., 3:4].astype(np.uint16)
        pre = rgba.copy()
        pre[..., :3] = (rgba[..., :3].astype(np.uint16) * a // 255).astype(np.uint8)
        tex = self.ctx.texture((rgba.shape[1], rgba.shape[0]), 4, np.ascontiguousarray(pre).tobytes())
        tex.build_mipmaps()
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        return tex

    def ensure_mask(self, w: int, h: int) -> None:
        if w <= self.mask_size[0] and h <= self.mask_size[1]:
            return
        w, h = max(w, self.mask_size[0], 256), max(h, self.mask_size[1], 256)
        for obj in (self.mask_fbo, self.mask):
            if obj is not None:
                obj.release()
        self.mask = self.ctx.texture((w, h), 4)
        self.mask_fbo = self.ctx.framebuffer(color_attachments=[self.mask])
        self.mask_size = (w, h)

    def ensure_temp(self, w: int, h: int) -> None:
        self.ensure_mask(w, h)
        if w <= self.temp_size[0] and h <= self.temp_size[1]:
            return
        w, h = max(w, self.temp_size[0], 256), max(h, self.temp_size[1], 256)
        for obj in (self.temp_fbo, self.out_fbo, self.temp, self.out):
            if obj is not None:
                obj.release()
        self.temp = self.ctx.texture((w, h), 4)
        self.temp.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.out = self.ctx.texture((w, h), 4)
        self.temp_fbo = self.ctx.framebuffer(color_attachments=[self.temp])
        self.out_fbo = self.ctx.framebuffer(color_attachments=[self.out])
        self.temp_size = (w, h)

    # --- сетки ---

    def mesh(self, key: Hashable, puppet: Puppet, items: Callable[[], list[Item]]) -> Optional[Mesh]:
        """Сетка кадра по ключу (из кэша или собранная из items())."""
        if key in self.meshes:
            self.meshes.move_to_end(key)
            return self.meshes[key]
        mesh = self.build_mesh(puppet, items())
        self.meshes[key] = mesh
        if mesh is not None:
            self._mesh_bytes += mesh.nbytes
        while self._mesh_bytes > MESH_MB * 2 ** 20 and len(self.meshes) > 1:
            _, old = self.meshes.popitem(last=False)
            if old is not None:
                self._mesh_bytes -= old.nbytes
                old.release()
        return mesh

    def forget_meshes(self) -> None:
        for mesh in self.meshes.values():
            if mesh is not None:
                mesh.release()
        self.meshes.clear()
        self._mesh_bytes = 0

    def build_mesh(self, puppet: Puppet, items: list[Item]) -> Optional[Mesh]:
        box = puppet.bbox(items)
        if box is None:
            return None
        chunks, runs, first = [], [], 0
        for it in items:
            for state, verts in self._item_runs(puppet, it):
                chunks.append(verts)
                runs.append((*state, first, len(verts)))
                first += len(verts)
        if not chunks:
            return None
        data = np.concatenate(chunks).astype("f4").tobytes()
        vbo = self.ctx.buffer(data)
        vao = self.ctx.vertex_array(self.prog, [(vbo, "2f 2f 4f", "in_pos", "in_uv", "in_col")])
        return Mesh(vbo, vao, runs, box, len(data))

    def draw_mesh(self, mesh: Mesh, pages: list, target, view: tuple[int, int], scale: float, flip: bool,
                  ox: float, oy: float) -> None:
        """Сетка в буфер target (его область view), точка 0,0 куклы — в пикселе (ox, oy)."""
        ctx = self.ctx
        self.ensure_mask(*view)
        self.prog["xf"].value = (-scale if flip else scale, scale, ox, oy)
        self.prog["view"].value = view
        self.prog["size"].value = self.mask_size
        ctx.enable(moderngl.BLEND)
        for page, blend, mode, mask_clear, first, count in mesh.runs:
            if mask_clear:
                self.mask_fbo.clear(0, 0, 0, 0, viewport=(0, 0, *view))
            (pages[page] if 0 <= page < len(pages) and pages[page] is not None else self.white).use(0)
            self.mask.use(1)
            self.prog["mode"].value = mode
            self.prog["glow"].value = int(blend == ADD)
            if mode == MASK_WRITE:
                self.mask_fbo.use()
                ctx.blend_func = moderngl.ONE, moderngl.ONE
            else:
                target.use()
                ctx.blend_func = {ADD: (moderngl.ONE, moderngl.ONE),
                                  MULTIPLY: (moderngl.DST_COLOR, moderngl.ONE_MINUS_SRC_ALPHA)}.get(
                    blend, (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA))
            ctx.viewport = (0, 0, *view)
            mesh.vao.render(moderngl.TRIANGLES, vertices=count, first=first)
        target.use()

    def draw_to_temp(self, mesh: Mesh, pages: list, scale: float, flip: bool, pad: int = 2,
                     box: Optional[tuple[float, float, float, float]] = None) -> Optional[tuple[float, float, int, int]]:
        """Кадр куклы в рабочий буфер (premultiplied): (точка 0,0 в нём x, y, ширина, высота) или None."""
        if box is not None:
            x0, y0, x1, y1 = box
            if flip:
                x0, x1 = -x1, -x0
            w = max(1, math.ceil((x1 - x0) * scale) + 2 * pad)
            h = max(1, math.ceil((y1 - y0) * scale) + 2 * pad)
            ox, oy = pad - x0 * scale, pad - y0 * scale
        else:
            ox, oy, w, h = mesh.frame_box(scale, flip, pad)
        if w * h > 4096 * 4096:
            return None
        self.ensure_temp(w, h)
        self.temp_fbo.use()
        self.temp_fbo.clear(0, 0, 0, 0, viewport=(0, 0, w, h))
        self.draw_mesh(mesh, pages, self.temp_fbo, (w, h), scale, flip, ox, oy)
        return ox, oy, w, h

    # --- кадр в картинку ---

    def render(self, puppet: Puppet, pages: list, items: list[Item], scale: float, flip: bool = False,
               box: Optional[tuple[float, float, float, float]] = None, pad: int = 2, premultiplied: bool = False):
        """(RGBA uint8 [h, w, 4], точка 0,0 персонажа в пикселях) или None — пусто. Цвет обычный (не
        premultiplied), premultiplied=True — как есть: для эффектов со сложением на чёрном фоне.
        box — рамка в единицах персонажа (по умолчанию — по видимым деталям)."""
        mesh = self.build_mesh(puppet, items)
        if mesh is None:
            return None
        try:
            placed = self.draw_to_temp(mesh, pages, scale, flip, pad, box)
            if placed is None:
                return None
            ox, oy, w, h = placed
            return self.read_temp(w, h, premultiplied), (ox, oy)
        finally:
            mesh.release()

    def read_temp(self, w: int, h: int, premultiplied: bool = False) -> np.ndarray:
        ctx, target = self.ctx, self.temp_fbo
        if not premultiplied:
            ctx.disable(moderngl.BLEND)
            self.out_fbo.use()
            ctx.viewport = (0, 0, w, h)
            self.temp.use(0)
            self.straight_vao.render(moderngl.TRIANGLES, vertices=3)
            target = self.out_fbo
        raw = np.frombuffer(target.read(viewport=(0, 0, w, h), components=4, alignment=1), np.uint8).reshape(h, w, 4)
        return raw.copy()

    # --- наложение текстуры ---

    def quad(self, texture, corners, uv: tuple[float, float, float, float], view: tuple[int, int], kind: int = 0,
             alpha: float = 1.0, mul=(1.0, 1.0, 1.0), add=(0.0, 0.0, 0.0), flash: float = 0.0,
             additive: bool = False, screen: bool = False) -> None:
        """Текстура в текущий буфер прямоугольником corners (4 точки: лв, пв, пн, лн — в пикселях),
        uv — (u0, v0, u1, v1) её части. kind: 0 premultiplied, 1 обычная прозрачность, 2 слой pygame."""
        ctx = self.ctx
        (ax, ay), (bx, by), (cx, cy), (dx, dy) = corners
        u0, v0, u1, v1 = uv
        data = np.array([ax, ay, u0, v0, bx, by, u1, v0, cx, cy, u1, v1,
                         ax, ay, u0, v0, cx, cy, u1, v1, dx, dy, u0, v1], "f4")
        self.quad_vbo.write(data.tobytes())
        prog = self.quad_prog
        prog["view"].value = view
        prog["screen"].value = int(screen)
        prog["kind"].value = kind
        prog["mul"].value = tuple(mul)
        prog["add"].value = tuple(add)
        prog["flash"].value = flash
        prog["alpha"].value = alpha
        texture.use(0)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.ONE, moderngl.ONE) if additive else (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        self.quad_vao.render(moderngl.TRIANGLES, vertices=6)


def unpremultiply(rgba: np.ndarray) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.uint16)
    out = rgba.copy()
    nz = a[..., 0] > 0
    out[..., :3][nz] = np.minimum(255, rgba[..., :3][nz].astype(np.uint16) * 255 // a[nz]).astype(np.uint8)
    return out


def _item_runs_impl(puppet: Puppet, it: Item):
    """Вершины трека группами одинакового состояния: ((страница, смешивание, режим, очистить маску), вершины)
    — в единицах куклы."""
    parts, xy = puppet.item_polys(it)
    if not len(parts):
        return []
    keep = puppet.shown(it, parts)
    if not keep.any():
        return []
    mask_frame = bool(puppet.f_flags[it.frame] & 0x100)
    is_mask = (puppet.p_b[parts] & 2 != 0) & mask_frame
    visible = np.nonzero(keep)[0]
    clip = bool(is_mask[visible[0]])                       # кадр начинается с маски — обрезать по ней
    parts, xy, is_mask = parts[keep], xy[keep], is_mask[keep]
    if MASK_RULE == "layer":
        # группа масок обрезает следующие детали той же тысячи номеров слоя (поле a детали: 9300, 9291 ->
        # 9360, 9351…); деталь другой тысячи (4431 после маски 7150) рисуется без маски
        mbs = getattr(puppet, "m", None)
        layer = mbs.parts["a"][parts].astype(np.int64) // 1000 if mbs is not None else np.zeros(len(parts), np.int64)
        kind = puppet.p_b[parts]
        role_groups = np.full(len(parts), DRAW)
        key = None
        for i in range(len(parts)):
            if is_mask[i]:
                role_groups[i] = MASK_WRITE
                # обрезают только маски b = 3 со своим номером слоя (подол мантии волшебника); b = 7, 11
                # и маски без номера слоя (a = 0, у лорда в теле) не обрезают ничего
                key = layer[i] if kind[i] == 3 and (mbs is None or mbs.parts["a"][parts[i]] > 0) else None
            elif key is not None and layer[i] == key:
                role_groups[i] = MASK_TEST
    elif MASK_RULE in ("group_out", "group_in"):
        after = np.cumsum(is_mask) > 0                     # уже была группа масок
        test = MASK_OUT if MASK_RULE == "group_out" else MASK_TEST
        role_groups = np.where(is_mask, MASK_WRITE, np.where(after, test, DRAW))
    elif MASK_RULE == "none":
        role_groups = np.where(is_mask, MASK_WRITE, DRAW)
    else:
        role_groups = None
    modes = puppet.p_mode[parts]
    blend = np.where(modes == 2, MULTIPLY, np.where(modes == 1, ADD, NORMAL))   # 3 — обычное (фоны BattleBG)
    role = role_groups if role_groups is not None else np.where(is_mask, MASK_WRITE, MASK_TEST if clip else DRAW)
    uv = puppet.uv[puppet.p_uv[parts]]
    tr = np.array(it.tr["rgba"], np.float32)
    if puppet.colors is not None:
        col = puppet.colors[puppet.p_col[parts]].astype(np.float32) * tr
    else:
        col = np.tile(tr, (len(parts), 6, 1))
    verts = np.concatenate([xy[:, FAN], uv[:, FAN], col[:, FAN]], axis=-1)     # [n, 12, 8]
    state = np.stack([puppet.p_page[parts], blend, role], 1)
    cut = np.nonzero((state[1:] != state[:-1]).any(1))[0] + 1
    runs, start, prev = [], 0, None
    for end in list(cut) + [len(parts)]:
        page, b, r = (int(v) for v in state[start])
        # маска стирается в начале кадра и в начале каждой новой группы масок
        clear = mask_frame and (start == 0 or (r == MASK_WRITE and prev != MASK_WRITE))
        runs.append(((page, b, r, clear), verts[start:end].reshape(-1, 8)))
        start, prev = end, r
    return runs


GLRenderer._item_runs = staticmethod(_item_runs_impl)
