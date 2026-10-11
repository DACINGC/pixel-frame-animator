# -*- coding: utf-8 -*-
"""主 Agent 收尾校验：palette 一致性 / 索引域 / 连招关节 / SHA 复核 / 总览图"""
import json, hashlib, subprocess, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
PKGS = ['sw-walk-run', 'sw-idles', 'sw-jump-climb', 'sw-dodge-slide', 'sw-hurt',
        'sw-death', 'sw-ultimate', 'sw-atk12', 'sw-atk34', 'sw-atk5']
ok = True

# 1) palette 逐字节一致
pal0 = (HERE / PKGS[0] / 'palette.json').read_bytes()
for p in PKGS:
    b = (HERE / p / 'palette.json').read_bytes()
    if b != pal0:
        print(f'[FAIL] palette 不一致: {p}')
        ok = False
print(f'[ok] 10 包 palette.json 逐字节一致')

# 2) 帧数与调色板域（PNG 存的是 RGB，比对 RGB 元组是否都在调色板内）
sys.path.insert(0, str(HERE))
import sw_lib as S
allowed = {c[:3] for c in S.PALETTE}
total = 0
for p in PKGS:
    atlas = json.loads((HERE / p / 'atlas.json').read_text(encoding='utf-8'))
    n = len(atlas['frames'])
    total += n
    for f in atlas['frames']:
        im = Image.open(HERE / p / f['file']).convert('RGBA')
        used = {px[:3] for px in im.getdata() if px[3] > 0}
        extra = used - allowed
        if extra:
            print(f'[FAIL] {p}/{f["id"]} 出现调色板外颜色 {sorted(extra)[:5]}')
            ok = False
print(f'[ok] 全场调色板域合法，共 {total} 帧')

# 3) 连招关节（复用 G 的 check_combo）
r = subprocess.run([sys.executable, str(HERE / '_qa' / 'check_combo.py')],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    ok = False

# 4) sha256sum -c（每包）
for p in PKGS:
    r = subprocess.run(['sha256sum', '-c', 'manifest.sha256'], cwd=HERE / p,
                       capture_output=True, text=True)
    bad = [l for l in r.stdout.splitlines() if 'FAILED' in l]
    if r.returncode != 0 or bad:
        print(f'[FAIL] {p} manifest 校验失败: {bad[:3]}')
        ok = False
print('[ok] 10 包 manifest.sha256 复核通过')

# 5) 总览图（10 行，_ 前缀防 scan 误收）
rows = []
for p in PKGS:
    atlas = json.loads((HERE / p / 'atlas.json').read_text(encoding='utf-8'))
    row = Image.new('RGBA', (64 * len(atlas['frames']), 64), (0, 0, 0, 0))
    for i, f in enumerate(atlas['frames']):
        row.paste(Image.open(HERE / p / f['file']).convert('RGBA'), (i * 64, 0))
    rows.append((p, row))
W = max(r.width for _, r in rows)
sheet = Image.new('RGBA', (W, 64 * len(rows)), (24, 22, 30, 255))
for i, (p, row) in enumerate(rows):
    sheet.paste(row, (0, i * 64))
out = HERE / '_qa' / '_overview.png'
sheet.resize((W * 4, sheet.height * 4), Image.Resampling.NEAREST).save(out)
print(f'[ok] 总览图 {out}')

# 6) 每包 manifest 文件自身哈希（登记用）
print('\n=== manifest.sha256 文件自身哈希（登记进 README） ===')
for p in PKGS:
    h = hashlib.sha256((HERE / p / 'manifest.sha256').read_bytes()).hexdigest()
    print(f'{p:16s} {h}')

print('\n[RESULT] ' + ('ALL OK' if ok else 'HAS FAILURES'))
sys.exit(0 if ok else 1)
