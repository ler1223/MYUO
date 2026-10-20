"""Vanillaware FTEX texture container (Switch): parse + deswizzle + BCn decode via Pillow."""
import struct
import sys
import numpy as np
from PIL import Image

# .tex format byte -> (pillow decoder args, bytes per 4x4 block or per pixel, is_block)
FORMATS = {
    0x4D: ("bcn", 7, 16, True),   # BC7
    0x49: ("bcn", 4, 8, True),    # BC4 (fonts, single channel)
}


def deswizzle(data: bytes, w_el: int, h_el: int, bpe: int, bh: int) -> bytes:
    """Tegra X1 block-linear -> linear. w_el/h_el in elements, bpe bytes per element."""
    x = np.arange(w_el, dtype=np.int64)[None, :] * bpe
    y = np.arange(h_el, dtype=np.int64)[:, None]
    width_bytes = w_el * bpe
    gobs_w = (width_bytes + 63) // 64
    addr = ((y // (8 * bh)) * 512 * bh * gobs_w
            + (x // 64) * 512 * bh
            + ((y % (8 * bh)) // 8) * 512
            + ((x % 64) // 32) * 256 + ((y % 8) // 2) * 64
            + ((x % 32) // 16) * 32 + (y % 2) * 16)
    src = np.frombuffer(data, dtype=np.uint8)
    need = int(addr.max()) + bpe
    if len(src) < need:
        src = np.concatenate([src, np.zeros(need - len(src), np.uint8)])
    idx = addr[..., None] + np.arange(bpe)
    return src[idx].tobytes()


def block_height(h_el: int) -> int:
    bh = 16
    while bh > 1 and h_el <= (bh // 2) * 8:
        bh //= 2
    return bh


def parse(data: bytes):
    if data[:4] != b"FTEX":
        raise ValueError("not FTEX")
    hdr_size, count = struct.unpack_from("<II", data, 8)
    names = []
    for i in range(count):
        o = 0x20 + i * 0x60 if False else 0x20 + i * 0x40
        names.append(data[o:o + 0x20].split(b"\0")[0].decode("ascii", "replace"))
    texs, p = [], hdr_size
    while p < len(data) and data[p:p + 4] == b"FTX0":
        size, hsz = struct.unpack_from("<II", data, p + 4)
        t = p + hsz
        assert data[t:t + 4] == b".tex", hex(t)
        fmt = data[t + 4]
        w, h = struct.unpack_from("<II", data, t + 0xC)
        dsize = struct.unpack_from("<I", data, t + 0x20)[0]
        texs.append({"fmt": fmt, "w": w, "h": h, "off": t + 0x100, "size": dsize,
                     "hdr": data[t:t + 0x40]})
        p = t + 0x100 + dsize
        p = (p + 0xF) & ~0xF
    return names, texs


def decode(data: bytes, tex, swizzle=True) -> Image.Image:
    fmt = FORMATS.get(tex["fmt"])
    if not fmt:
        raise NotImplementedError(f"format {tex['fmt']:#x}")
    dec, arg, bpe, is_block = fmt
    w, h = tex["w"], tex["h"]
    raw = data[tex["off"]:tex["off"] + tex["size"]]
    w_el, h_el = ((w + 3) // 4, (h + 3) // 4) if is_block else (w, h)
    if swizzle:
        raw = deswizzle(raw, w_el, h_el, bpe, block_height(h_el))
    if dec == "bcn" and arg == 4:
        a = Image.frombytes("L", (w, h), raw, "bcn", 4)
        im = Image.new("RGBA", (w, h), (255, 255, 255, 0)); im.putalpha(a)
        return im
    if dec == "bcn":
        return Image.frombytes("RGBA", (w, h), raw, "bcn", arg)
    return Image.frombytes("RGBA", (w, h), raw, dec, arg)


if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    names, texs = parse(d)
    print(names)
    for i, t in enumerate(texs):
        print(i, hex(t["fmt"]), t["w"], t["h"], hex(t["off"]), t["size"], t["hdr"][:0x30].hex(" "))
        if len(sys.argv) > 2:
            decode(d, t, True).save(f"{sys.argv[2]}_{i}_sw.png")
            decode(d, t, False).save(f"{sys.argv[2]}_{i}_lin.png")
