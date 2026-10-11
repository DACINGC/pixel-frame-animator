# -*- coding: utf-8 -*-
"""把各特效定稿包拼成总览图，两种底色各一张（检查浅色/深色场景下的可读性）。

    python make_overview.py
"""
import glob
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS = [
    ('fx-impact-r2', '击中 impact + 斩击 slash'),
    ('fx-boom-r2', '爆炸 explode'),
    ('fx-smoke-r3', '烟雾 smoke（循环）'),
    ('fx-dust-r3', '跑动扬尘 dust（循环）'),
    ('fx-cast', '技能 charge + burst'),
]
ZOOM = 6
PAD = 4
LABEL_W = 150


def build(bg, out_name):
    rows = []
    max_cols = 0
    for pid, label in PACKS:
        files = sorted(glob.glob(os.path.join(HERE, pid, 'frames', '*.png')))
        rows.append((label, [Image.open(f).convert('RGBA') for f in files]))
        max_cols = max(max_cols, len(files))

    cell = 32 * ZOOM
    w = LABEL_W + max_cols * (cell + PAD) + PAD
    h = len(rows) * (cell + PAD) + PAD
    canvas = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(canvas)

    for r, (label, imgs) in enumerate(rows):
        y = PAD + r * (cell + PAD)
        d.text((6, y + 6), label, fill=(230, 230, 240) if sum(bg) < 400 else (30, 30, 40))
        for c, im in enumerate(imgs):
            x = LABEL_W + c * (cell + PAD)
            big = im.resize((cell, cell), Image.Resampling.NEAREST)
            canvas.paste(big, (x, y), big)
    out = os.path.join(HERE, out_name)
    canvas.save(out)
    print('OK ->', out, canvas.size)


if __name__ == '__main__':
    # 文件名带 _ 前缀：扫描器会忽略 _ 开头文件，避免 fx 目录被误判成 png 序列
    build((26, 26, 34), '_overview-dark.png')
    build((220, 220, 228), '_overview-light.png')
