# -*- coding: utf-8 -*-
"""
击中 / 打击特效帧动画包 —— impact(冲击星芒) + slash(斩击弧光) 共 8 帧。

从 frame_anim_template.py 复制改造，遵循 pixelwork/fx/CONTRACT.md：
  - SIZE=32，锚点 CX=CY=16 写死，一切用半径参数控制
  - 调色板 <=16 色，索引 0 透明，其余 alpha=255，fill/outline 一律传索引
  - 主体带索引 1 描边；<=4px 的火星/白心不描边
  - 最大半径 <=14，四边留 1px 余量（脚本会强制校验边框为空）
"""
import hashlib, json, math, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32
CX, CY = 16, 16          # 中心锚点，写死，绝不逐帧重算
MAXR = 14                # 最大半径上限（CX-14=2 .. CX+14=30）

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / 'demo-output'

# 调色板：索引 -> RGBA（0 透明，其余 alpha=255，禁止半透明）
PALETTE = [
    (0, 0, 0, 0),          # 0  透明
    (34, 30, 44, 255),     # 1  描边深色
    (255, 255, 255, 255),  # 2  白（高光 / 白心）
    (255, 238, 200, 255),  # 3  暖白
    (255, 196, 84, 255),   # 4  金（星芒主体）
    (226, 140, 50, 255),   # 5  金暗（碎屑 / 暗部）
    (146, 80, 34, 255),    # 6  焦金（残影）
    (255, 224, 152, 255),  # 7  淡金（外发光 / 冲击波淡环）
    (108, 170, 200, 255),  # 8  淡青（外发光）
    (110, 214, 248, 255),  # 9  青亮
    (56, 160, 208, 255),   # 10 青中（弧光主体）
    (28, 104, 152, 255),   # 11 青暗（弧光外缘）
    (168, 178, 204, 255),  # 12 灰（消散残影）
    (92, 100, 128, 255),   # 13 暗灰（消散碎屑）
]

OUTLINE, WHITE, WARM_W = 1, 2, 3
GOLD, GOLD_D, EMBER, PALE_GOLD = 4, 5, 6, 7
PALE_CY, CY_HI, CY_MID, CY_LO = 8, 9, 10, 11
GREY, GREY_D = 12, 13

LAYER_ORDER = ['back', 'body', 'weapon', 'fx']     # 自下而上

# ---------------- 2. 绘制原语（全部围绕 CX/CY）----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)

def put(d, x, y, c):
    if 0 <= x < SIZE and 0 <= y < SIZE:
        d.point((x, y), fill=c)
    else:
        raise SystemExit(f'像素越界 ({x},{y}) —— 缩小半径')

def pol(rad, ang):
    """极坐标 -> 像素（ang 用数学角，0=右，逆时针为正）"""
    a = math.radians(ang)
    return int(round(CX + rad * math.cos(a))), int(round(CY - rad * math.sin(a)))

def ell_pt(rx, ry, ang, off=0.0):
    """椭圆弧上的点；off 为径向厚度偏移（正=外）"""
    a = math.radians(ang)
    return int(round(CX + (rx + off) * math.cos(a))), int(round(CY - (ry + off) * math.sin(a)))

def star(d, L, L2, w, w2, c, eight=True, outline=OUTLINE):
    """以 CX/CY 为中心的星芒：主半径 L（正交），次半径 L2（对角），w/w2 为腰宽"""
    k = 8 if eight else 4
    step = 360 // k
    pts = []
    for i in range(k):
        rr, ww = (L, w) if i % 2 == 0 else (L2, w2)
        pts.append(pol(rr, -90 + i * step))
        pts.append(pol(ww, -90 + (i + 0.5) * step))
    d.polygon(pts, fill=c, outline=outline)

def spike(d, ang, L, c, base=1.6):
    """细长尖刺（星芒尖端），细 -> 不描边，否则会被吃成黑块"""
    a = math.radians(ang)
    ux, uy = math.cos(a), -math.sin(a)
    nx, ny = -uy, ux
    d.polygon([(CX + ux * L, CY + uy * L),
               (CX + nx * base, CY + ny * base),
               (CX - nx * base, CY - ny * base)], fill=c)

def ring(d, r, c, w=1):
    d.ellipse((CX - r, CY - r, CX + r - 1, CY + r - 1), outline=c, width=w)

def ring_arc(d, r, c, a0, a1, w=1):
    d.arc((CX - r, CY - r, CX + r - 1, CY + r - 1), a0, a1, fill=c, width=w)

def crescent(d, rx, ry, a0, a1, half, band, rim=False):
    """弯月弧带：两端细中段粗（half 为中段半厚），band 由外到内排列"""
    n = max(1, int(round(abs(a1 - a0) / 0.5)))
    pts = []
    for i in range(n + 1):
        u = i / n
        ang = a0 + (a1 - a0) * u
        h = 0.5 + (half - 0.5) * math.sin(math.pi * u)   # 中段粗、两端收细
        pts.append((ang, int(round(h))))
    if rim:                                              # 先铺描边，再压主体色
        for ang, hi in pts:
            for off in (hi + 1, -(hi + 1)):
                x, y = ell_pt(rx, ry, ang, off)
                put(d, x, y, OUTLINE)
    for ang, hi in pts:
        for o in range(-hi, hi + 1):
            c = band[min(hi - o, len(band) - 1)]
            x, y = ell_pt(rx, ry, ang, o)
            put(d, x, y, c)

def spark(d, ang, rad, size, c):
    """飞散碎屑 / 火星（<=4px，一律不描边）"""
    x, y = pol(rad, ang)
    if size <= 1:
        put(d, x, y, c)
    else:
        d.rectangle((x, y, x + size - 1, y + size - 1), fill=c)

# ---------------- 3. 姿态参数（统一走 pose 一个入口）----------------
def pose(**kw):
    p = dict(
        kind='impact',
        # impact：星芒
        L=6, L2=4, w=2, w2=2, eight=True, body_c=GOLD,
        inner_L=0, inner_c=WARM_W,
        core=0, core_w=2,                 # fx 白心星芒长度（0=无）
        rings=(), arcs=(), tips=(), tip_c=WARM_W,
        sparks=(),                        # (角度, 半径, 尺寸, 颜色)
        # slash：弯月弧光
        rx=9, ry=7, segs=((130, 75),), half=2.0, band=(CY_LO, CY_MID), rim=True,
        glow=0.0,                         # back 外发光半厚
        core_segs=(), core_rx=7, core_ry=5, core_half=0.8,
    )
    p.update(kw)
    return p

# ---------------- 4. 四层绘制 ----------------
def draw_back(d, p):
    """back = 外发光 / 冲击波淡环"""
    if p['kind'] == 'impact':
        for r, c in p['rings']:
            ring(d, r, c, 1)
        for r, c, a0, a1 in p['arcs']:
            ring_arc(d, r, c, a0, a1, 1)
    else:
        if p['glow'] > 0:
            for a0, a1 in p['segs']:
                crescent(d, p['rx'], p['ry'], a0, a1, p['glow'], (PALE_CY,), rim=False)

def draw_body(d, p):
    """body = 星芒 / 弧光主体（带索引 1 描边）"""
    if p['kind'] == 'impact':
        star(d, p['L'], p['L2'], p['w'], p['w2'], p['body_c'], eight=p['eight'])
        if p['inner_L']:
            star(d, p['inner_L'], max(1, int(p['inner_L'] * 0.6)),
                 2, 2, p['inner_c'], eight=p['eight'], outline=None)
    else:
        for a0, a1 in p['segs']:
            crescent(d, p['rx'], p['ry'], a0, a1, p['half'], p['band'], rim=p['rim'])

def draw_weapon(d, p):
    """weapon = 飞散碎屑 / 星芒尖端"""
    if p['kind'] == 'impact':
        for ang, L in p['tips']:
            spike(d, ang, L, p['tip_c'])
    for ang, rad, size, c in p['sparks']:
        spark(d, ang, rad, size, c)

def draw_fx(d, p):
    """fx = 最亮高光（白心），面积小"""
    if p['kind'] == 'impact':
        if p['core']:
            star(d, p['core'], max(1, int(p['core'] * 0.5)), p['core_w'], 1,
                 WHITE, eight=False, outline=None)
            d.rectangle((CX - 1, CY - 1, CX + 1, CY + 1), fill=WHITE)
    else:
        for a0, a1 in p['core_segs']:
            crescent(d, p['core_rx'], p['core_ry'], a0, a1, p['core_half'], (WHITE,), rim=False)

# ---------------- 5. 动作表：impact 4 帧 + slash 4 帧 ----------------
ACTIONS = {
    # 冲击命中：白闪 -> 星芒张开 -> 最大（带飞散碎屑）-> 收缩衰减
    'impact': [
        pose(kind='impact',                                     # 0 白闪
             L=5, L2=3, w=2, w2=1, eight=True, body_c=WARM_W,
             core=3, core_w=1,
             rings=((6, PALE_GOLD),),
             sparks=((45, 7, 1, GOLD_D), (135, 7, 1, GOLD_D),
                     (225, 7, 1, GOLD_D), (315, 7, 1, GOLD_D))),
        pose(kind='impact',                                     # 1 星芒张开
             L=9, L2=5, w=3, w2=2, eight=True, body_c=GOLD,
             inner_L=5, inner_c=WARM_W, core=4, core_w=2,
             rings=((9, PALE_GOLD),),
             arcs=((12, PALE_GOLD, -20, 20), (12, PALE_GOLD, 70, 110),
                   (12, PALE_GOLD, 160, 200), (12, PALE_GOLD, 250, 290)),
             sparks=((45, 11, 2, GOLD_D), (135, 11, 2, GOLD_D),
                     (225, 11, 2, GOLD_D), (315, 11, 2, GOLD_D),
                     (0, 12, 1, WARM_W), (90, 12, 1, WARM_W),
                     (180, 12, 1, WARM_W), (270, 12, 1, WARM_W))),
        pose(kind='impact',                                     # 2 最大 + 飞散碎屑
             L=13, L2=9, w=4, w2=3, eight=True, body_c=GOLD,
             inner_L=8, inner_c=WARM_W, core=5, core_w=2,
             rings=((14, PALE_GOLD), (11, PALE_GOLD)),
             tips=((45, 14), (135, 14), (225, 14), (315, 14)), tip_c=WARM_W,
             sparks=((20, 13, 2, GOLD_D), (65, 12, 1, GOLD), (110, 14, 2, GOLD_D),
                     (155, 12, 1, GOLD), (200, 13, 2, GOLD_D), (245, 12, 1, GOLD),
                     (290, 14, 2, GOLD_D), (335, 12, 1, GOLD_D))),
        pose(kind='impact',                                     # 3 收缩衰减（残影）
             L=4, L2=2, w=2, w2=1, eight=False, body_c=GOLD_D,
             core=0,
             arcs=((10, GREY, 30, 100), (12, GREY, 160, 215), (9, GREY, 250, 320)),
             sparks=((35, 12, 1, EMBER), (100, 13, 1, GREY_D), (170, 11, 2, EMBER),
                     (215, 13, 1, GREY_D), (265, 12, 1, EMBER), (320, 11, 2, GREY_D))),
    ],
    # 斩击弧光：弧线出现 -> 扫过并加宽 -> 最亮（内白外青）-> 消散
    'slash': [
        pose(kind='slash',                                      # 0 弧线出现
             rx=8, ry=6, segs=((135, 60),), half=1.1, band=(CY_LO, CY_MID),
             glow=1.7,
             sparks=((60, 9, 1, CY_HI),)),
        pose(kind='slash',                                      # 1 扫过并加宽
             rx=9, ry=7, segs=((128, 25),), half=2.2, band=(CY_LO, CY_MID, CY_HI),
             glow=3.2,
             core_segs=((90, 40),), core_rx=7, core_ry=5, core_half=0.8,
             sparks=((20, 10, 1, CY_HI), (35, 11, 1, CY_HI), (55, 11, 1, CY_HI))),
        pose(kind='slash',                                      # 2 最亮：内白外青
             rx=10, ry=8, segs=((125, -45),), half=3.0, band=(CY_LO, CY_MID, CY_HI),
             glow=3.8,
             core_segs=((100, -20),), core_rx=8, core_ry=6, core_half=1.3,
             sparks=((0, 12, 1, CY_HI), (-20, 13, 2, CY_HI), (-35, 12, 1, WHITE),
                     (-10, 14, 1, CY_HI), (-50, 11, 1, CY_HI))),
        pose(kind='slash',                                      # 3 消散（断裂残影）
             rx=10, ry=8, segs=((105, 60), (20, -35)), half=1.2, band=(GREY_D, CY_LO),
             glow=1.8,
             sparks=((-15, 13, 1, GREY), (-40, 12, 1, GREY_D), (-60, 10, 1, GREY))),
    ],
}

# ---------------- 6. 渲染 + 导出 ----------------
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

def check_edges(im, fid):
    """不截断校验：四条边必须为空（留 1px 余量）"""
    px = im.load()
    for i in range(SIZE):
        for x, y in ((i, 0), (i, SIZE - 1), (0, i), (SIZE - 1, i)):
            if px[x, y][3] != 0:
                raise SystemExit(f'{fid} 触到画布边缘 ({x},{y}) —— 缩小半径')

def export():
    if OUT.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{OUT}')
    (OUT / 'frames').mkdir(parents=True)
    frames, sheet_w, imgs = [], 0, []
    for action, poses in ACTIONS.items():
        for i, p in enumerate(poses):
            im = render_frame(p)
            fid = f'{action}_{i}'
            check_edges(im, fid)
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
        OUT / 'contact-sheet-8x.png')                       # 放大一律 NEAREST
    atlas = {'size': [sheet_w, SIZE], 'frame_size': SIZE, 'palette_size': len(PALETTE),
             'layer_order': LAYER_ORDER, 'frames': frames}
    (OUT / 'atlas.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'palette.json').write_text(json.dumps(PALETTE, ensure_ascii=False), encoding='utf-8')
    hashes = [f['rgba_sha256'] for f in frames]
    if len(set(hashes)) != len(hashes):
        dup = [f['id'] for f in frames if hashes.count(f['rgba_sha256']) > 1]
        raise SystemExit(f'姿态重复，必须让每帧有真实差异：{dup}')
    for f in frames:
        if not (OUT / f['file']).stat().st_size:
            raise SystemExit(f'{f["id"]} 是空帧')
    # manifest 校验 PNG 字节，使 sha256sum -c manifest.sha256 可直接复核
    lines = []
    for f in frames:
        sha = hashlib.sha256((OUT / f['file']).read_bytes()).hexdigest()
        lines.append(f'{sha}  {f["file"]}')
    with open(OUT / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'OK -> {OUT}  帧数={len(imgs)}  画布={SIZE}  颜色数={len(PALETTE)}  边缘校验=PASS  帧间差异校验=PASS')
    print('下一步：真实打开 contact-sheet-8x.png 目检')

if __name__ == '__main__':
    export()
