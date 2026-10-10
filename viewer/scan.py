#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描工作区里的像素帧动画资源，生成统一的索引数据。

识别规则（命中即作为一个"动画集"，并停止向下递归）：
  1. 目录含 atlas.json 且带 frames 数组        -> 以图集清单为准
  2. 目录含 frames/ 子目录且里面有 png         -> 按文件名自然排序
  3. 目录本身有 >=2 张同前缀的 xxx_0.png 序列  -> 按文件名自然排序

输出：JSON 索引（供 serve.py 的 /api/scan 使用），
或 --static 模式写出 data.js（供 file:// 直接双击 index.html 兜底使用）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

SKIP_DIRS = {".git", ".workbuddy", "__pycache__", "node_modules", "viewer", ".venv", "venv", ".idea"}
IMAGE_EXT = {".png", ".webp", ".gif"}
# walk_0 / attack-01 / run_12  ->  (动作名, 序号)
SEQ_RE = re.compile(r"^(.*?)[_-](\d+)$")


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


def scan(root: str):
    root = os.path.abspath(root)
    sets = []
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        st, matched = scan_dir(dirpath, root)
        if matched and st:
            sets.append(st)
            dirnames[:] = []  # 命中后不再向下递归
    sets.sort(key=lambda s: s["dir"])
    return {
        "root": root.replace("\\", "/"),
        "rootName": os.path.basename(root.rstrip("\\/")),
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "setCount": len(sets),
        "frameCount": sum(s["frameCount"] for s in sets),
        "sets": sets,
    }


def main():
    ap = argparse.ArgumentParser(description="扫描像素帧动画目录并生成索引")
    ap.add_argument("root", nargs="?", default=None, help="扫描根目录，默认 viewer 的上一级")
    ap.add_argument("--static", action="store_true", help="写出 data.js 供 file:// 直接打开")
    ap.add_argument("--json", action="store_true", help="把索引 JSON 打印到标准输出")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    root = args.root or os.path.dirname(here)
    data = scan(root)

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
            print(f"  {st['dir']}  {st['frameCount']} 帧  [{clips}]")
        print(f"[scan] 共 {data['setCount']} 个动画集 / {data['frameCount']} 帧 -> {data['root']}")


if __name__ == "__main__":
    main()
