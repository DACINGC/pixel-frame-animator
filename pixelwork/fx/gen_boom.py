# -*- coding: utf-8 -*-
"""
爆炸特效（explode）帧动画生成脚本
由 frame_anim_template.py 复制改造（模板原文件未做任何改动）。

约定：
  - SIZE = 32，中心锚点 CX / CY 写死为常量，膨胀收缩一律用半径参数控制，
    绝不逐帧重算中心坐标，保证播放时不飘。
  - 调色板索引模式 'P'，fill / outline 一律传索引，绝不传 RGB；索引 0 = 透明。
  - 主体（火球、烟团）带索引 1 深色描边；≤4px 的火星/碎块/高光一律不描边。
  - 四层：back=冲击波/稀薄烟，body=火球主体/烟团，weapon=飞散火星与碎块，
    fx=最亮白心与亮黄内焰。
"""
import hashlib, json, math, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32
CX = 16                                   # 中心锚点（写死，永不逐帧重算）
CY = 16
MAX_R = 14                                # 最大半径：16-14=2 .. 16+14=30，留 1px 余量
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / 'demo-output'

PALETTE = [                                            # 索引 -> RGBA
    (0, 0, 0, 0),          # 0  透明
    (34, 30, 44, 255),     # 1  描边深色
    (122, 28, 24, 255),    # 2  暗红（外焰 / 余烬）
    (186, 54, 28, 255),    # 3  红
    (232, 108, 32, 255),   # 4  橙
    (250, 168, 52, 255),   # 5  橙黄
    (252, 224, 128, 255),  # 6  亮黄
    (255, 255, 255, 255),  # 7  白（白心）
    (214, 156, 102, 255),  # 8  冲击波淡环（比主体暗，只是外圈扩散层）
    (74, 70, 80, 255),     # 9  深灰烟
    (120, 116, 126, 255),  # 10 中灰烟
    (170, 166, 174, 255),  # 11 浅灰烟
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']          # 自下而上合成

DIR8 = [(1, 0), (-1, 0), (0, -1), (0, 1),
        (1, -1), (-1, -1), (1, 1), (-1, 1)]

# ---------------- 2. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)

def rect(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)

def ell(d, box, c, outline=None):
    d.ellipse(box, fill=c, outline=outline)

def seg(d, pts, c, w=1):
    d.line(pts, fill=c, width=w)

def disc(d, cx, cy, r, c, outline=None):
    """围绕任意锚点的实心圆；r<=0 退化为单点。"""
    if r <= 0:
        d.point((cx, cy), fill=c)
        return
    box = (cx - r, cy - r, cx + r, cy + r)
    if outline is None:
        d.ellipse(box, fill=c)
    else:
        d.ellipse(box, fill=c, outline=outline)

def radial(dx, dy, r):
    """方向向量 (dx,dy) 在半径 r 上的像素坐标（围绕 CX/CY）。"""
    n = math.hypot(dx, dy)
    return CX + int(round(dx / n * r)), CY + int(round(dy / n * r))

def tongue(d, dx, dy, r0, r1, c):
    """火苗舌：从半径 r0 伸到 r1 的硬边线段，细长件不描边。"""
    seg(d, [radial(dx, dy, r0), radial(dx, dy, r1)], c, 1)

def spark(d, dx, dy, c, size=1):
    """火星 / 碎块：≤4px，一律不描边（描边会被吃成黑块）。"""
    x, y = CX + dx, CY + dy
    if size <= 1:
        d.point((x, y), fill=c)
    else:
        rect(d, (x, y, x + size - 1, y + size - 1), c)

# ---------------- 3. 四层绘制 ----------------
def draw_back(d, p):
    """back：外圈冲击波 / 稀薄烟（最淡的一层）"""
    if p['glow']:                                     # 稀薄点环
        for dx, dy in DIR8:
            x, y = radial(dx, dy, p['glow'])
            d.point((x, y), fill=8)
    if p['ring']:                                     # 完整冲击环
        rr = p['ring']
        d.ellipse((CX - rr, CY - rr, CX + rr, CY + rr), fill=0, outline=8)
    if p['frag']:                                     # 冲击环碎片
        rr = p['frag']
        box = (CX - rr, CY - rr, CX + rr, CY + rr)
        for a0 in p['frag_segs']:
            d.arc(box, a0, a0 + p['frag_len'], fill=8, width=1)
    if p['backsmoke']:                                # 上升的稀薄烟
        sy, items = p['backsmoke']
        for dx, dy, r, c in items:
            disc(d, CX + dx, CY + sy + dy, r, c)
    if p['smoke_ring']:                               # 稀薄烟圈
        sy, rr, segs = p['smoke_ring']
        box = (CX - rr, CY + sy - rr, CX + rr, CY + sy + rr)
        for a0, a1 in segs:
            d.arc(box, a0, a1, fill=11, width=1)

def draw_body(d, p):
    """body：火球主体 / 烟团（唯一带描边的主体层）"""
    for dx, dy, r0, r1, c in p['tongues']:            # 火苗舌（先画，主体盖住根部）
        tongue(d, dx, dy, r0, r1, c)
    if p['ball']:                                     # 火球：外壳描边，内部逐层提亮
        R, shells = p['ball']
        for r, c in shells:
            disc(d, CX, CY, r, c, outline=1 if r == R else None)
    for dx, dy, r, c in p['blobs']:                   # 分裂后的火块
        disc(d, CX + dx, CY + dy, r, c, outline=1)
    if p['smoke']:                                    # 烟团
        sy, items = p['smoke']
        for dx, dy, r, c, ol in items:
            disc(d, CX + dx, CY + sy + dy, r, c, outline=1 if ol else None)
    if p['ember']:                                    # 未燃尽的暗红余烬核
        dx, dy, r, c = p['ember']
        disc(d, CX + dx, CY + dy, r, c)

def draw_weapon(d, p):
    """weapon：飞散火星与碎块（≤4px，不描边）"""
    for dx, dy, c in p['chunks']:
        spark(d, dx, dy, c, 2)
    for dx, dy, c in p['sparks']:
        spark(d, dx, dy, c, 1)

def draw_fx(d, p):
    """fx：最亮白心与亮黄内焰（面积要小）"""
    if p['inner']:
        dx, dy, r, c = p['inner']
        disc(d, CX + dx, CY + dy, r, c)
    for dx, dy, c, size in p['fx_bits']:              # 火块里的亮黄残焰
        spark(d, dx, dy, c, size)
    if p['core']:                                     # 白心：core=1→2x2, 2→3x3, 3→4x4
        k = p['core'] - 1
        rect(d, (CX - 1 - (k > 0), CY - 1 - (k > 0),
                 CX + k, CY + k), 7)

# ---------------- 4. 动作表（先排时间轴再写参数）----------------
# explode 6 帧：小闪光 → 膨胀 → 最大（白心+冲击环）→ 火焰分裂 → 烟+火星 → 烟圈消散
def pose(ball=None, blobs=(), tongues=(), inner=None, core=0, fx_bits=(),
         glow=0, ring=0, frag=0, frag_segs=(), frag_len=26,
         sparks=(), chunks=(), smoke=None, backsmoke=None, smoke_ring=None,
         ember=None):
    return {'ball': ball, 'blobs': blobs, 'tongues': tongues, 'inner': inner,
            'core': core, 'fx_bits': fx_bits, 'glow': glow, 'ring': ring,
            'frag': frag, 'frag_segs': frag_segs, 'frag_len': frag_len,
            'sparks': sparks, 'chunks': chunks, 'smoke': smoke,
            'backsmoke': backsmoke, 'smoke_ring': smoke_ring, 'ember': ember}

ACTIONS = {
    'explode': [
        # 0 小闪光：一点白心 + 四向小火苗，主体只有 r=3
        pose(ball=(3, [(3, 4)]),
             tongues=[(0, -1, 3, 5, 6), (-1, 0, 3, 5, 6),
                      (1, 0, 3, 5, 6), (0, 1, 3, 4, 5)],
             core=1),

        # 1 膨胀：火球 r=6，橙红主色，外圈出现稀薄点环，飞出 3 颗火星
        pose(glow=8,
             ball=(6, [(6, 3), (4, 4), (2, 5)]),
             tongues=[(0, -1, 6, 8, 5), (-1, 0, 6, 8, 5), (1, 0, 6, 8, 5),
                      (0, 1, 6, 8, 5), (1, -1, 5, 7, 5), (-1, 1, 5, 7, 5)],
             inner=(0, 0, 2, 6), core=1,
             sparks=[(0, -10, 6), (10, -2, 5), (-8, 6, 5)]),

        # 2 最大：r=9 火球 + 冲击环 r=12 + 最大白心 + 8 向火苗 + 6 颗火星
        pose(ring=12,
             ball=(9, [(9, 2), (7, 3), (5, 4)]),
             tongues=[(0, -1, 9, 11, 5), (-1, 0, 9, 11, 5), (1, 0, 9, 11, 5),
                      (0, 1, 9, 11, 5), (1, -1, 8, 10, 5), (-1, -1, 8, 10, 5),
                      (1, 1, 8, 10, 5), (-1, 1, 8, 10, 5)],
             inner=(0, 0, 3, 6), core=2,
             sparks=[(0, -12, 6), (12, -4, 6), (10, 8, 5),
                     (-12, 3, 5), (-7, -10, 6), (4, 12, 5)]),

        # 3 火焰分裂：主体裂成 5 块（不再是整圆），冲击环碎成 6 段，飞散碎块+火星
        pose(frag=13, frag_segs=(195, 250, 305, 20, 75, 130),
             blobs=[(-6, -4, 3, 3), (5, -6, 2, 3), (-7, 5, 2, 2),
                    (6, 4, 3, 3), (0, 0, 2, 2)],
             fx_bits=[(-6, -4, 6, 2), (6, 4, 5, 2), (5, -6, 6, 1)],
             chunks=[(-11, -6, 3), (11, -7, 3), (-10, 7, 2), (12, 6, 2), (0, -11, 5)],
             sparks=[(0, -12, 6), (12, -2, 6), (9, 9, 5),
                     (-9, -10, 6), (-4, 12, 5), (7, -12, 5)]),

        # 4 烟+火星：火退成暗红余烬核，灰烟上升（sy=-4），只剩 3 颗零星火星
        pose(backsmoke=(-4, [(-4, -6, 2, 11), (5, -5, 2, 11), (0, -8, 3, 11)]),
             smoke=(-4, [(0, -2, 5, 9, True), (0, -1, 3, 10, False)]),
             ember=(0, 3, 2, 2),
             sparks=[(-10, -1, 5), (10, -6, 5), (-6, 9, 2)]),

        # 5 烟圈消散：只剩稀薄烟圈 + 一小团残烟 + 2 颗将熄火星（不为空）
        pose(smoke_ring=(-6, 9, [(200, 250), (280, 330), (350, 360), (0, 30), (60, 100)]),
             smoke=(-6, [(0, 2, 3, 10, True), (0, 3, 2, 11, False)]),
             sparks=[(-8, 4, 2), (9, -3, 5)]),
    ],
}

# ---------------- 5. 渲染 + 导出 ----------------
def render_frame(p):
    layers = {}
    im = new_layer(); draw_back(ImageDraw.Draw(im), p);   layers['back'] = im
    im = new_layer(); draw_body(ImageDraw.Draw(im), p);   layers['body'] = im
    im = new_layer(); draw_weapon(ImageDraw.Draw(im), p); layers['weapon'] = im
    im = new_layer(); draw_fx(ImageDraw.Draw(im), p);     layers['fx'] = im
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for name in LAYER_ORDER:
        sp = layers[name].load()
        for yy in range(SIZE):
            for xx in range(SIZE):
                if sp[xx, yy]:
                    px[xx, yy] = PALETTE[sp[xx, yy]]
    return out

def export():
    if OUT.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{OUT}')
    (OUT / 'frames').mkdir(parents=True)
    frames, sheet_w, imgs = [], 0, []
    for action, poses in ACTIONS.items():
        for i, p in enumerate(poses):
            im = render_frame(p)
            fid = f'{action}_{i}'
            im.save(OUT / 'frames' / f'{fid}.png')
            imgs.append((fid, im))
            frames.append({'id': fid, 'action': action, 'order': len(imgs) - 1,
                           'file': f'frames/{fid}.png',
                           'rect': [(len(imgs) - 1) * SIZE, 0, SIZE, SIZE],
                           'rgba_sha256': hashlib.sha256(im.tobytes()).hexdigest()})
            sheet_w += SIZE
    sheet = Image.new('RGBA', (sheet_w, SIZE), (0, 0, 0, 0))
    for i, (_, im) in enumerate(imgs):
        sheet.paste(im, (i * SIZE, 0))
    sheet.save(OUT / 'sprite-sheet.png')
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.Resampling.NEAREST).save(
        OUT / 'contact-sheet-8x.png')                    # 放大一律 NEAREST
    atlas = {'size': [sheet_w, SIZE], 'frame_size': SIZE, 'palette_size': len(PALETTE),
             'layer_order': LAYER_ORDER, 'frames': frames}
    (OUT / 'atlas.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'palette.json').write_text(json.dumps(PALETTE, ensure_ascii=False), encoding='utf-8')
    hashes = [f['rgba_sha256'] for f in frames]
    if len(set(hashes)) != len(hashes):
        dup = [f['id'] for f in frames if hashes.count(f['rgba_sha256']) > 1]
        raise SystemExit(f'姿态重复，必须让每帧有真实差异：{dup}')
    if not any(Path(OUT / f['file']).stat().st_size for f in frames):
        raise SystemExit('所有帧都是空白，角色未绘制')
    lines = []
    for f in frames:
        sha = hashlib.sha256((OUT / f['file']).read_bytes()).hexdigest()
        lines.append(f'{sha}  {f["file"]}')
    with open(OUT / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'OK -> {OUT}  帧数={len(imgs)}  画布={SIZE}  颜色数={len(PALETTE)}  帧间差异校验=PASS')
    print('下一步：真实打开 contact-sheet-8x.png 目检轮廓/姿态差异/部位一致/不截断')

if __name__ == '__main__':
    export()
