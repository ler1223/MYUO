"""CRIWARE CPK archive reader: @UTF tables (incl. XOR-encrypted), TOC, CRILAYLA."""
import struct
import sys


def utf_decrypt(data: bytes) -> bytes:
    m, out = 0x655F, bytearray(data)
    for i in range(len(out)):
        out[i] ^= m & 0xFF
        m = (m * 0x4115) & 0xFFFFFFFF
    return bytes(out)


def read_packet(f, offset: int, magic: bytes) -> bytes:
    f.seek(offset)
    hdr = f.read(16)
    if hdr[:4] != magic:
        raise ValueError(f"expected {magic!r} at {offset:#x}, got {hdr[:4]!r}")
    size = struct.unpack_from("<Q", hdr, 8)[0]
    data = f.read(size)
    if data[:4] != b"@UTF":
        data = utf_decrypt(data)
    return data


def parse_utf(data: bytes):
    if data[:4] != b"@UTF":
        raise ValueError("not @UTF")
    _, rows_off, str_off, data_off, name_off, ncols, row_w, nrows = struct.unpack_from(">HHIIIHHI", data, 8)
    rows_off += 8; str_off += 8; data_off += 8

    def cstr(o):
        o += str_off
        return data[o:data.index(b"\0", o)].decode("utf-8", "replace")

    fmt = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i", 6: ">Q", 7: ">q", 8: ">f", 9: ">d"}

    def read_val(t, o):
        if t in fmt:
            v = struct.unpack_from(fmt[t], data, o)[0]
            return v, struct.calcsize(fmt[t])
        if t == 0xA:
            return cstr(struct.unpack_from(">I", data, o)[0]), 4
        if t == 0xB:
            do, ds = struct.unpack_from(">II", data, o)
            return data[data_off + do:data_off + do + ds], 8
        raise ValueError(f"utf type {t:#x}")

    cols, p = [], 0x20
    for _ in range(ncols):
        flag = data[p]; name = cstr(struct.unpack_from(">I", data, p + 1)[0]); p += 5
        storage, typ = flag & 0xF0, flag & 0x0F
        const = None
        if storage & 0x20:  # default/constant value
            const, n = read_val(typ, p); p += n
        cols.append((name, storage, typ, const))

    rows = []
    for r in range(nrows):
        o, row = rows_off + r * row_w, {}
        for name, storage, typ, const in cols:
            if storage & 0x40:
                v, n = read_val(typ, o); o += n
                row[name] = v
            elif storage & 0x20:
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return cstr(name_off) if name_off < len(data) else "", rows


def crilayla_decompress(src: bytes) -> bytes:
    if src[:8] != b"CRILAYLA":
        return src
    usize, hsize = struct.unpack_from("<II", src, 8)
    prefix = src[0x10 + hsize:0x10 + hsize + 0x100]
    out = bytearray(usize + 0x100)
    out[:0x100] = prefix
    wp = len(out) - 1
    end = 0x100
    # bit reader backwards from end of compressed data
    pos = 0x10 + hsize - 1
    bitpool = 0
    bits_left = 0

    def getbits(n):
        nonlocal pos, bitpool, bits_left
        v = 0
        while n:
            if bits_left == 0:
                bitpool = src[pos]; pos -= 1; bits_left = 8
            take = min(bits_left, n)
            v = (v << take) | ((bitpool >> (bits_left - take)) & ((1 << take) - 1))
            bits_left -= take; n -= take
        return v

    while wp >= end:
        if getbits(1):
            back = getbits(13) + 3
            length = 3
            lvls = (2, 3, 5, 8)
            done = False
            for bits in lvls:
                v = getbits(bits)
                length += v
                if v != (1 << bits) - 1:
                    done = True
                    break
            if not done:
                while True:
                    v = getbits(8)
                    length += v
                    if v != 0xFF:
                        break
            for _ in range(length):
                out[wp] = out[wp + back]; wp -= 1
                if wp < end:
                    break
        else:
            out[wp] = getbits(8); wp -= 1
    return bytes(out)


class CPK:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        _, rows = parse_utf(read_packet(self.f, 0, b"CPK "))
        self.header = rows[0]
        self.files = []
        toc = self.header.get("TocOffset")
        if toc:
            _, trows = parse_utf(read_packet(self.f, toc, b"TOC "))
            content = self.header.get("ContentOffset") or toc
            base = min(toc, content)
            for r in trows:
                d, n = r.get("DirName") or "", r.get("FileName") or ""
                self.files.append({
                    "path": f"{d}/{n}" if d else n,
                    "offset": base + r["FileOffset"],
                    "size": r["FileSize"],
                    "extract_size": r.get("ExtractSize") or r["FileSize"],
                    "id": r.get("ID"),
                })
        if not self.files and self.header.get("ItocOffset"):
            raise NotImplementedError("ITOC-only CPK")

    def read(self, entry) -> bytes:
        self.f.seek(entry["offset"])
        data = self.f.read(entry["size"])
        if entry["extract_size"] != entry["size"] or data[:8] == b"CRILAYLA":
            data = crilayla_decompress(data)
        return data


if __name__ == "__main__":
    c = CPK(sys.argv[1])
    for k, v in c.header.items():
        if not isinstance(v, bytes):
            print(f"  {k} = {v}")
    print(len(c.files), "files")
    comp = sum(1 for e in c.files if e["size"] != e["extract_size"])
    print(comp, "compressed")
    for e in c.files[: int(sys.argv[2]) if len(sys.argv) > 2 else 30]:
        print(f'{e["offset"]:#012x} {e["size"]:>10} {e["extract_size"]:>10} {e["path"]}')
