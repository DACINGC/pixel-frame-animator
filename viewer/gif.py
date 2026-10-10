# -*- coding: utf-8 -*-
"""零依赖的像素动画 GIF 导出：自己解码 PNG + 自己写 GIF89a。

像素图天然是小调色板的索引色，所以这里直接做「色彩表 + 未压缩 LZW」：
每个像素发一个字面码（9 bit），字典增长到一定程度就发一次清除码复位，
避免码长变化带来的歧义。体积比最优压缩大一些，但对预览 GIF 完全够用。
"""

from __future__ import annotations

import os
import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- PNG 解码

def decode_png(path: str):
    """返回 (w, h, rgba_bytes)。支持 8bit 非隔行的 PNG（灰/RGB/索引/RGBA）。"""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != PNG_SIG:
        raise ValueError("不是 PNG 文件: " + path)

    pos, idat = 8, bytearray()
    width = height = depth = color_type = None
    palette = trns = None
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, depth, color_type, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlace != 0:
                raise ValueError("仅支持 8bit 非隔行 PNG: " + path)
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"tRNS":
            trns = body
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))

    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _y in range(height):
        filt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if filt == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 255
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif filt == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif filt == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out += line
        prev = line

    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        if color_type == 6:
            rgba[i * 4:i * 4 + 4] = out[i * 4:i * 4 + 4]
        elif color_type == 2:
            rgba[i * 4:i * 4 + 3] = out[i * 3:i * 3 + 3]
            rgba[i * 4 + 3] = 255
        elif color_type == 0:
            v = out[i]
            rgba[i * 4:i * 4 + 3] = bytes((v, v, v))
            rgba[i * 4 + 3] = 255
        elif color_type == 4:
            v, a = out[i * 2], out[i * 2 + 1]
            rgba[i * 4:i * 4 + 3] = bytes((v, v, v))
            rgba[i * 4 + 3] = a
        else:  # 3 索引色
            idx = out[i]
            rgba[i * 4:i * 4 + 3] = palette[idx * 3:idx * 3 + 3]
            rgba[i * 4 + 3] = trns[idx] if (trns and idx < len(trns)) else 255
    return width, height, bytes(rgba)


def scale_rgba(w: int, h: int, rgba: bytes, scale: int):
    """最近邻放大，保持硬边。"""
    if scale <= 1:
        return w, h, rgba
    out = bytearray(w * h * 4 * scale * scale)
    ow = w * scale
    for y in range(h):
        for x in range(w):
            src = (y * w + x) * 4
            px = rgba[src:src + 4]
            for sy in range(scale):
                base = ((y * scale + sy) * ow + x * scale) * 4
                for sx in range(scale):
                    out[base + sx * 4:base + sx * 4 + 4] = px
    return ow, h * scale, bytes(out)


def composite(w: int, h: int, rgba: bytes, bg: tuple):
    out = bytearray(w * h * 4)
    br, bg_, bb = bg[0], bg[1], bg[2]
    for i in range(w * h):
        r, g, b, a = rgba[i * 4:i * 4 + 4]
        if a == 255:
            out[i * 4:i * 4 + 4] = bytes((r, g, b, 255))
        elif a == 0:
            out[i * 4:i * 4 + 4] = bytes((br, bg_, bb, 255))
        else:
            k = a / 255.0
            out[i * 4:i * 4 + 4] = bytes((
                int(r * k + br * (1 - k)),
                int(g * k + bg_ * (1 - k)),
                int(b * k + bb * (1 - k)), 255))
    return bytes(out)


# ---------------------------------------------------------------- GIF 写出

class BitWriter:
    def __init__(self):
        self.buf = bytearray()
        self.acc = 0
        self.nbits = 0

    def write(self, code: int, size: int):
        self.acc |= code << self.nbits
        self.nbits += size
        while self.nbits >= 8:
            self.buf.append(self.acc & 255)
            self.acc >>= 8
            self.nbits -= 8

    def flush(self):
        if self.nbits:
            self.buf.append(self.acc & 255)
            self.acc = 0
            self.nbits = 0
        return bytes(self.buf)


def lzw_encode(indices: bytes, min_code_size: int) -> bytes:
    """标准 GIF LZW：字典随码长增长，4096 项时发清除码复位。"""
    clear = 1 << min_code_size
    end = clear + 1
    code_size = min_code_size + 1
    table = {}
    next_code = end + 1

    bw = BitWriter()
    bw.write(clear, code_size)
    if not indices:
        bw.write(end, code_size)
        return bw.flush()

    buf = bytes(indices[0:1])          # 首像素先挂起，不立即发码
    for px in indices[1:]:
        nbuf = buf + bytes((px,))
        if nbuf in table:
            buf = nbuf
            continue
        bw.write(buf[0] if len(buf) == 1 else table[buf], code_size)
        if next_code < 4096:
            table[nbuf] = next_code    # 只存长度 >=2 的序列，与解码端一致
            next_code += 1
            # 解码端字典比编码端慢一拍，这里必须"晚一个码"再升位宽（giflib 约定）
            if next_code > (1 << code_size) and code_size < 12:
                code_size += 1
        else:                          # 字典写满，发清除码复位
            bw.write(clear, code_size)
            table = {}
            next_code = end + 1
            code_size = min_code_size + 1
        buf = bytes((px,))

    bw.write(buf[0] if len(buf) == 1 else table.get(buf, buf[0]), code_size)
    bw.write(end, code_size)
    return bw.flush()


def build_palette(frames_rgba, transparent: bool):
    colors = {}
    for _w, _h, rgba in frames_rgba:
        for i in range(0, len(rgba), 4):
            px = rgba[i:i + 4]
            a = px[3]
            if transparent and a < 128:
                continue
            key = px[:3]
            if key not in colors:
                colors[key] = len(colors)
    if len(colors) > 255:
        colors = {}
        for _w, _h, rgba in frames_rgba:
            for i in range(0, len(rgba), 4):
                px = rgba[i:i + 4]
                if transparent and px[3] < 128:
                    continue
                key = bytes(((px[0] >> 3) << 3, (px[1] >> 3) << 3, (px[2] >> 3) << 3))
                if key not in colors:
                    colors[key] = len(colors)
    trans_index = len(colors) if transparent else None
    return colors, trans_index


def index_frames(frames_rgba, colors, trans_index):
    out = []
    for w, h, rgba in frames_rgba:
        buf = bytearray(w * h)
        for i in range(w * h):
            px = rgba[i * 4:i * 4 + 4]
            if trans_index is not None and px[3] < 128:
                buf[i] = trans_index
            else:
                buf[i] = colors[px[:3]]
        out.append(bytes(buf))
    return out


def sub_blocks(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out.append(len(chunk))
        out += chunk
    out.append(0)
    return bytes(out)


def write_gif(path: str, frames_rgba, delay_ms: int, transparent: bool, bg: tuple):
    """frames_rgba: [(w, h, rgba_bytes)]，所有帧会被补齐到最大尺寸。"""
    w = max(f[0] for f in frames_rgba)
    h = max(f[1] for f in frames_rgba)
    colors, trans_index = build_palette(frames_rgba, transparent)
    if trans_index is not None and trans_index > 255:
        raise ValueError("颜色数超过 255，无法写入 GIF 调色板")
    indexed = index_frames(frames_rgba, colors, trans_index)

    total = len(colors) + (1 if trans_index is not None else 0)
    min_code_size = max(2, (total - 1).bit_length())   # 至少能装下最大索引

    gct = bytearray(256 * 3)
    for rgb, idx in colors.items():
        gct[idx * 3:idx * 3 + 3] = rgb

    out = bytearray()
    out += b"GIF89a"
    out += struct.pack("<HH", w, h)
    out += bytes((0xF7, 0, 0))                      # 全局色表 256 色，背景索引 0
    out += gct
    out += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01" + struct.pack("<H", 0) + b"\x00"

    delay = max(2, int(round(delay_ms / 10.0)))
    for idx_data in indexed:
        gce = 0x08 | (0x01 if trans_index is not None else 0x00)   # disposal=2, 可选透明
        out += b"\x21\xF9\x04" + bytes((gce,)) + struct.pack("<H", delay)
        out += bytes((trans_index if trans_index is not None else 0,)) + b"\x00"
        out += b"\x2C" + struct.pack("<HHHH", 0, 0, w, h) + b"\x00"
        out += bytes((min_code_size,))
        out += sub_blocks(lzw_encode(idx_data, min_code_size))

    out += b"\x3B"
    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return len(colors)


# ---------------------------------------------------------------- 对外入口

BG_COLORS = {
    "dark": (24, 24, 30),
    "light": (246, 246, 250),
    "green": (0, 195, 65),
    "magenta": (255, 0, 212),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}


def export_gif(out_path: str, root: str, files, fps: float, scale: int = 4,
               bg: str = "transparent"):
    """按扫描索引里的相对路径把一批帧导出成 GIF。"""
    solid = BG_COLORS.get(bg)
    frames = []
    for rel in files:
        w, h, rgba = decode_png(os.path.join(root, rel.replace("/", os.sep)))
        if scale > 1:
            w, h, rgba = scale_rgba(w, h, rgba, scale)
        if solid is not None:
            rgba = composite(w, h, rgba, solid)
        frames.append((w, h, rgba))

    if not frames:
        raise ValueError("没有可导出的帧")
    delay_ms = 1000.0 / max(0.5, fps)
    return write_gif(out_path, frames, delay_ms, solid is None, solid or (0, 0, 0))
