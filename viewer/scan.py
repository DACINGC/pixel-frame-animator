#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描工作区里的像素帧动画资源，生成统一的索引数据。

识别规则（命中即作为一个"动画集"，并停止向下递归）：
  1. 目录含 atlas.json 且带 frames 数组        -> 以图集清单为准
  2. 目录含 frames/ 子目录且里面有 png         -> 按文件名自然排序
  3. 目录本身有 >=2 张同前缀的 xxx_0.png 序列  -> 按文件名自然排序

输出：JSON 索引（供 serve.py 的 /api/scan 使用），
或 --static 模式写出 data.js（供 file:// 直接双击 index.html 兜底使用）。

去重标注（只做标记，绝不改动磁盘文件）：
  fingerprint  逐帧视觉指纹（忽略全透明像素的差异）
  isDup/dupOf  与另一个动画集内容相同，dupOf 指向保留的那一个
  isLatest/supersededBy  同一动画的 -rN 迭代版本，按修改时间判定谁是最新的
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import zlib
from datetime import datetime

SKIP_DIRS = {".git", ".workbuddy", "__pycache__", "node_modules", "viewer", ".venv", "venv", ".idea"}
# 默认跳过的归档目录（--include-archive 可打开）
ARCHIVE_DIRS = {"_archive", "_archive_old", "_trash"}
IMAGE_EXT = {".png", ".webp", ".gif"}
# walk_0 / attack-01 / run_12  ->  (动作名, 序号)
SEQ_RE = re.compile(r"^(.*?)[_-](\d+)$")
# bat-attack-death-r2 / slime-move-hit-r4  ->  (基础名, 版本号)
REV_SUFFIX_RE = re.compile(r"^(.*?)[-_](?:r|rev|v)(\d+)$", re.IGNORECASE)


def natural_key(text: str):
    """自然排序：walk_2 排在 walk_10 前面。"""
    parts = re.split(r"(\d+)", text)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def png_size(path: str):
    """只读 PNG 头取宽高，不依赖 Pillow。"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    except OSError:
        pass
    return None


def read_json(path: str):
    try:
        if os.path.getsize(path) > 20 * 1024 * 1024:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def rel_posix(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace("\\", "/")


def clip_of(frame_id: str) -> str:
    m = SEQ_RE.match(frame_id)
    if m:
        name = m.group(1).strip("_-")
        return name or "default"
    return "default"


def pick_sheet(dirpath: str):
    """找出 sprite-sheet / contact-sheet 之类的整图。"""
    sheet = contact = None
    for name in sorted(os.listdir(dirpath)):
        low = name.lower()
        if not low.endswith(".png"):
            continue
        if "sprite-sheet" in low or low.startswith("spritesheet") or low.startswith("sheet"):
            sheet = name
        elif "contact" in low:
            contact = name
    return sheet, contact


def load_meta(dirpath: str):
    """从 project.json / 包内 md 里取标题、描述、调色板。"""
    meta = {"title": None, "description": None, "projectId": None, "revision": None,
            "palette": None, "frameSize": None}
    pj = read_json(os.path.join(dirpath, "project.json"))
    if isinstance(pj, dict):
        meta["title"] = pj.get("title")
        meta["description"] = pj.get("description")
        meta["projectId"] = pj.get("project_id")
        meta["revision"] = pj.get("revision")
        meta["palette"] = pj.get("palette")
        if isinstance(pj.get("size"), int):
            meta["frameSize"] = pj["size"]
    if not meta["palette"]:
        pal = read_json(os.path.join(dirpath, "palette.json"))
        if isinstance(pal, list) and pal and isinstance(pal[0], list):
            meta["palette"] = pal
    return meta


def frames_from_atlas(dirpath: str, root: str, atlas: dict):
    frames = []
    for i, item in enumerate(atlas.get("frames") or []):
        rel_file = str(item.get("file") or "").replace("\\", "/")
        abs_file = os.path.join(dirpath, rel_file)
        if not os.path.isfile(abs_file):
            continue
        fid = str(item.get("id") or os.path.splitext(os.path.basename(rel_file))[0])
        rect = item.get("rect")
        if isinstance(rect, list) and len(rect) == 4:
            fw, fh = int(rect[2]), int(rect[3])
        else:
            size = png_size(abs_file) or (0, 0)
            fw, fh = size
            rect = None
        frames.append({
            "id": fid,
            "file": rel_posix(root, abs_file),
            "clip": str(item.get("action") or clip_of(fid)),
            "index": i,
            "order": int(item.get("order", i)),
            "rect": rect,
            "w": fw,
            "h": fh,
            "sha": item.get("rgba_sha256"),
        })
    return frames


def frames_from_files(files, root):
    """files: 绝对路径列表，按文件名自然排序。"""
    frames = []
    for i, abs_file in enumerate(sorted(files, key=lambda p: natural_key(os.path.basename(p)))):
        fid = os.path.splitext(os.path.basename(abs_file))[0]
        size = png_size(abs_file) or (0, 0)
        frames.append({
            "id": fid,
            "file": rel_posix(root, abs_file),
            "clip": clip_of(fid),
            "index": i,
            "order": i,
            "rect": None,
            "w": size[0],
            "h": size[1],
            "sha": None,
        })
    return frames


def build_set(dirpath: str, root: str, frames):
    if not frames:
        return None
    rel_dir = rel_posix(root, dirpath)
    meta = load_meta(dirpath)
    sheet_name, contact_name = pick_sheet(dirpath)

    clips = []
    seen = {}
    for fr in frames:
        if fr["clip"] not in seen:
            seen[fr["clip"]] = {"name": fr["clip"], "frames": []}
            clips.append(seen[fr["clip"]])
        seen[fr["clip"]]["frames"].append(fr["index"])

    fw = max((fr["w"] for fr in frames), default=0)
    fh = max((fr["h"] for fr in frames), default=0)
    if isinstance(meta["frameSize"], int):
        fw = fh = meta["frameSize"]

    sheet = None
    if sheet_name:
        abs_sheet = os.path.join(dirpath, sheet_name)
        sheet = {"file": rel_posix(root, abs_sheet), "size": png_size(abs_sheet)}

    try:
        mtime = int(os.path.getmtime(dirpath))
    except OSError:
        mtime = 0

    return {
        "id": rel_dir,
        "name": os.path.basename(dirpath.rstrip("\\/")),
        "dir": rel_dir,
        "abs": dirpath.replace("\\", "/"),
        "group": os.path.dirname(rel_dir).replace("\\", "/"),
        "title": meta["title"],
        "description": meta["description"],
        "projectId": meta["projectId"],
        "revision": meta["revision"],
        "palette": meta["palette"],
        "frameCount": len(frames),
        "frameSize": [fw, fh] if fw and fh else None,
        "sheet": sheet,
        "contact": rel_posix(root, os.path.join(dirpath, contact_name)) if contact_name else None,
        "updatedAt": mtime,
        "clips": clips,
        "frames": frames,
    }


def scan_dir(dirpath: str, root: str):
    """判断某目录是否是一个动画集，是则返回 set 数据。"""
    name = os.path.basename(dirpath.rstrip("\\/"))
    hidden = name.startswith("_")

    atlas_path = os.path.join(dirpath, "atlas.json")
    if os.path.isfile(atlas_path):
        atlas = read_json(atlas_path)
        if isinstance(atlas, dict) and atlas.get("frames"):
            st = build_set(dirpath, root, frames_from_atlas(dirpath, root, atlas))
            if st:
                st["source"] = "atlas.json"
                if not st["projectId"]:
                    st["projectId"] = atlas.get("project_id")
                if isinstance(atlas.get("size"), list) and st["sheet"]:
                    st["sheet"]["size"] = atlas["size"]
                return st, True

    if hidden:
        return None, False  # 归档目录只在有 atlas.json 时才收录，避免临时放大图混入

    frames_dir = os.path.join(dirpath, "frames")
    if os.path.isdir(frames_dir):
        files = [os.path.join(frames_dir, f) for f in os.listdir(frames_dir)
                 if os.path.splitext(f)[1].lower() in IMAGE_EXT and not f.startswith((".", "_"))]
        st = build_set(dirpath, root, frames_from_files(files, root))
        if st:
            st["source"] = "frames/"
            return st, True

    if os.path.isdir(dirpath):
        files = [os.path.join(dirpath, f) for f in os.listdir(dirpath)
                 if os.path.splitext(f)[1].lower() in IMAGE_EXT and not f.startswith((".", "_"))]
        if len(files) >= 2:
            st = build_set(dirpath, root, frames_from_files(files, root))
            if st:
                st["source"] = "png序列"
                return st, True
    return None, False


def decode_rgba(data: bytes):
    """零依赖解码 8bit RGBA PNG，返回逐像素字节串；非该格式返回 None。

    只依赖标准库 zlib——Pillow 不是每台机器都装了。
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, w, h, idat = 8, 0, 0, []
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            if length < 13:
                return None
            w = int.from_bytes(body[0:4], "big")
            h = int.from_bytes(body[4:8], "big")
            if body[8] != 8 or body[9] != 6:  # 只处理 8bit / truecolor+alpha
                return None
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if not (w and h and idat):
        return None

    raw = zlib.decompress(b"".join(idat))
    bpp, stride = 4, w * 4
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _y in range(h):
        if p + 1 + stride > len(raw):
            return None
        filt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if filt == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif filt == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif filt == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pr = a + b - c
                pa, pb, pc = abs(pr - a), abs(pr - b), abs(pr - c)
                line[i] = (line[i] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        out += line
        prev = line
    return bytes(out)


def visual_fingerprint(root: str, frames) -> str:
    """逐帧视觉指纹：只对不透明像素取哈希，忽略全透明区域的差异。

    这样「只差几个透明像素」的两个包也能被判为重复。
    """
    h = hashlib.sha256()
    for fr in frames:
        path = os.path.join(root, str(fr.get("file") or "").replace("/", os.sep))
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            h.update(str(fr.get("file") or "").encode("utf-8"))
            continue
        px = decode_rgba(data)
        if px is None:  # 非 RGBA PNG（webp/gif/其他）退回整文件哈希
            h.update(hashlib.sha256(data).digest())
            continue
        h.update(len(px).to_bytes(8, "big"))
        for i in range(0, len(px), 4):
            if px[i + 3]:  # alpha > 0 才算有效像素
                h.update(i.to_bytes(4, "big"))
                h.update(px[i:i + 4])
    return h.hexdigest()


def is_archived(st: dict) -> bool:
    rel = str(st.get("dir") or "")
    return rel.startswith("_") or "/_" in rel


def rev_number(st: dict) -> int:
    m = REV_SUFFIX_RE.match(str(st.get("name") or ""))
    return int(m.group(2)) if m else 0


def annotate(root: str, sets):
    """给每个动画集打上去重标记（只标记，不动文件）。"""
    for st in sets:
        st["fingerprint"] = visual_fingerprint(root, st["frames"])

    # 1) 内容相同的重复组：保留「非归档 + 最新修改 + 路径最短」的那个
    by_fp = {}
    for st in sets:
        by_fp.setdefault(st["fingerprint"], []).append(st)
    for members in by_fp.values():
        ids = [m["id"] for m in members]
        rep = min(members, key=lambda m: (is_archived(m), -int(m.get("updatedAt") or 0),
                                          len(m["dir"]), m["dir"]))
        for m in members:
            m["dupGroup"] = ids
            m["isDup"] = m["id"] != rep["id"]
            m["dupOf"] = None if m["id"] == rep["id"] else rep["id"]

    # 2) 同动画的迭代版本（-rN）：按修改时间取最新
    by_variant = {}
    for st in sets:
        parent = os.path.dirname(str(st.get("dir") or ""))
        m = REV_SUFFIX_RE.match(str(st.get("name") or ""))
        key = (parent, m.group(1) if m else str(st.get("name")))
        by_variant.setdefault(key, []).append(st)
    for members in by_variant.values():
        ordered = sorted(members, key=lambda m: (int(m.get("updatedAt") or 0), rev_number(m), m["dir"]))
        latest = ordered[-1]
        ids = [m["id"] for m in ordered]
        for m in members:
            m["variantGroup"] = ids if len(ids) > 1 else None
            m["isLatest"] = m["id"] == latest["id"]
            m["supersededBy"] = None if m["id"] == latest["id"] else latest["id"]
    return sets


def scan(root: str, include_archive: bool = False):
    root = os.path.abspath(root)
    sets = []
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and not d.startswith(".")
                             and (include_archive or d not in ARCHIVE_DIRS))
        st, matched = scan_dir(dirpath, root)
        if matched and st:
            sets.append(st)
            dirnames[:] = []  # 命中后不再向下递归
    sets.sort(key=lambda s: s["dir"])
    annotate(root, sets)
    dup_count = sum(1 for s in sets if s.get("isDup"))
    old_count = sum(1 for s in sets if s.get("supersededBy"))
    # 一个包可能既是重复又是旧版，不能简单相减
    visible_count = sum(1 for s in sets if not s.get("isDup") and not s.get("supersededBy"))
    return {
        "root": root.replace("\\", "/"),
        "rootName": os.path.basename(root.rstrip("\\/")),
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "setCount": len(sets),
        "frameCount": sum(s["frameCount"] for s in sets),
        "dupCount": dup_count,
        "oldCount": old_count,
        "visibleCount": visible_count,
        "archived": not include_archive,
        "sets": sets,
    }


def main():
    ap = argparse.ArgumentParser(description="扫描像素帧动画目录并生成索引")
    ap.add_argument("root", nargs="?", default=None, help="扫描根目录，默认 viewer 的上一级")
    ap.add_argument("--static", action="store_true", help="写出 data.js 供 file:// 直接打开")
    ap.add_argument("--json", action="store_true", help="把索引 JSON 打印到标准输出")
    ap.add_argument("--include-archive", action="store_true", help="连 _archive 等归档目录一起扫描")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    root = args.root or os.path.dirname(here)
    data = scan(root, include_archive=args.include_archive)

    if args.static:
        out = os.path.join(here, "data.js")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("/* 自动生成，运行 `python serve.py` 或 `python scan.py --static` 重新生成 */\n")
            fh.write("window.PFA_STATIC_DATA = ")
            json.dump(data, fh, ensure_ascii=False)
            fh.write(";\n")
        print(f"[scan] 已写出 {out}（{data['setCount']} 个动画集 / {data['frameCount']} 帧）")
    elif args.json:
        json.dump(data, sys.stdout, ensure_ascii=False)
    else:
        for st in data["sets"]:
            clips = "/".join(c["name"] for c in st["clips"])
            tag = "重复" if st.get("isDup") else ("旧版" if st.get("supersededBy") else "显示")
            print(f"  [{tag}] {st['dir']}  {st['frameCount']} 帧  [{clips}]")
        print(f"[scan] 共 {data['setCount']} 个动画集 / {data['frameCount']} 帧 -> {data['root']}")
        print(f"[scan] 默认显示 {data['visibleCount']} 个"
              f"（隐藏重复 {data['dupCount']} 个 / 旧版本 {data['oldCount']} 个）")


if __name__ == "__main__":
    main()
