# -*- coding: utf-8 -*-
"""
技能 / 施法特效帧动画包（fx-cast）—— 从 frame_anim_template.py 复制改造。

动作编排：
  charge 4 帧（循环型）：光点聚集 → 光球变大 → 光环向内收拢 → 蓄满闪光
  burst  4 帧（单发型）：光柱升起 → 最亮（放射线）→ 衰减 → 余辉（少量残影）

硬性约定：
  SIZE=32，中心锚点 CX/CY 写死为常量，形状只用半径参数控制
  调色板 <=16 色，索引 0 透明，其余 alpha=255
  fill=/outline= 一律传调色板索引
  主体（光球/光柱）描边索引 1；<=4px 的光点与放射线不描边
"""
import hashlib, json, math, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32
CX = 16          # 中心锚点：写死，绝不逐帧重算
CY = 16
MAXR = 14        # 最大半径，保证 CX±14 = 2..30，四边各留 1px 余量

OUT = Path(sys.argv[1]) if len(sys.argv[1:]) else Path.cwd() / 'demo-output'

PALETTE = [                                            # 索引 -> RGBA
    (0, 0, 0, 0),          # 0  透明
    (26, 20, 46, 255),     # 1  描边深色（深紫，非纯黑）
    (46, 34, 92, 255),     # 2  暗部 深紫（外发光淡环）
    (72, 52, 140, 255),    # 3  靛蓝（法阵暗描线）
    (40, 86, 160, 255),    # 4  青蓝暗部
    (58, 132, 214, 255),   # 5  青蓝主色
    (110, 190, 240, 255),  # 6  亮青
    (198, 244, 255, 255),  # 7  极亮青（放射线 / 亮点）
    (255, 255, 255, 255),  # 8  白（最亮白心）
    (150, 110, 220, 255),  # 9  法阵描线紫
    (196, 150, 255, 255),  # 10 法阵描线亮紫
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']         # 自下而上合成

# ---------------- 2. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)

def rect(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)

def ell(d, box, c=None, outline=None):
    d.ellipse(box, fill=c, outline=outline)

def seg(d, pts, c, w=1):
    d.line(pts, fill=c, width=w)                       # 细线不描边（会被吃成黑块）

def clamp(v, lo=2, hi=SIZE - 3):
    """限幅到 2..29：光点/刻线最多向外再占 1px，仍留 1px 安全边距"""
    return max(lo, min(hi, int(round(v))))

def orbit(n, radius, phase_deg):
    """绕 CX/CY 均分取 n 个点，phase_deg 控制整体旋转（帧间结构差异靠它）"""
    pts = []
    for i in range(n):
        a = math.radians(phase_deg + 360.0 * i / n)
        pts.append((clamp(CX + radius * math.cos(a)),
                    clamp(CY + radius * math.sin(a))))
    return pts

def ring_box(r):
    r = min(r, MAXR)
    return (CX - r, CY - r, CX + r, CY + r)

def dot(d, x, y, c, size=2):
    """光点：<=4px，一律不描边"""
    if size <= 1:
        rect(d, (x, y, x, y), c)
    else:
        rect(d, (x, y, x + size - 1, y + size - 1), c)

# ---------------- 3. 四个图层的绘制 ----------------
def draw_back(d, p):
    """back：外发光淡环 / 底部法阵余光（最淡的一层）"""
    k = p['kind']
    if p['ring']:                                      # 法阵环 / 冲击环
        c = 3
        if k == 'charge':
            c = 6 if p['hot'] else 3
        else:
            c = 7 if p['hot'] else 3
        ell(d, ring_box(p['ring']), outline=c)
    if p['ring2']:                                     # 更外一圈稀薄辉光
        ell(d, ring_box(p['ring2']), outline=2)
    if p['runes'] and p['ring']:                       # 四方法阵刻线
        rr = min(p['ring'] + 1, MAXR - 1)
        rc = 10 if p['hot'] else 9
        for i in range(4):
            a = math.radians(90 * i + p['phase'])
            x = clamp(CX + rr * math.cos(a))
            y = clamp(CY + rr * math.sin(a))
            if i % 2 == 0:
                rect(d, (x - 1, y, x + 1, y), rc)
            else:
                rect(d, (x, y - 1, x, y + 1), rc)
    if k == 'burst' and p['mc']:                       # 底部法阵余光（透视椭圆）
        rx = min(p['mc'], MAXR - 2)
        ry = CY + 8
        ell(d, (CX - rx, ry, CX + rx, ry + rx // 2 + 1),
            outline=3 if p['fade'] >= 2 else 9)
        ell(d, (CX - rx // 2, ry + 2, CX + rx // 2, ry + 4),
            outline=2 if p['fade'] >= 2 else 10)

def draw_body(d, p):
    """body：光球（charge）或光柱（burst）主体，一律描边索引 1"""
    if p['kind'] == 'charge':
        r = min(p['r'], MAXR)
        ell(d, ring_box(r), 6 if p['hot'] else 5, outline=1)
        if r >= 4:                                     # 底部暗面，给光球一点体积
            ell(d, (CX - r + 2, CY + 1, CX + r - 2, CY + r - 1), 4)
    else:
        if p['hw']:                                    # 向上光柱
            rect(d, (CX - p['hw'], p['top'], CX + p['hw'], p['bot']),
                 6 if p['hot'] else 5, outline=1)
            rect(d, (CX - p['hw'] + 1, p['bot'] - 2, CX + p['hw'] - 1, p['bot'] - 1), 4)
        if p['rem']:                                   # 余辉残影（衰减后的小团）
            rr = p['rem']
            ell(d, ring_box(rr), 4, outline=1)

def draw_weapon(d, p):
    """weapon：环绕光点 / 放射线 / 收拢拖尾（细，不描边）"""
    if p['dr'] and p['n']:
        c = 7 if p['hot'] else 6
        if p['kind'] == 'burst' and p['fade'] >= 2:
            c = 4
        for (x, y) in orbit(p['n'], p['dr'], p['phase']):
            dot(d, x, y, c, p['dsz'])
    if p['conv'] and p['dr']:                          # 向内收拢的拖尾
        for i in range(p['conv']):
            a = math.radians(p['phase'] + 360.0 * i / p['conv'])
            x1 = clamp(CX + (p['dr'] + 4) * math.cos(a))
            y1 = clamp(CY + (p['dr'] + 4) * math.sin(a))
            x2 = clamp(CX + (p['dr'] + 1) * math.cos(a))
            y2 = clamp(CY + (p['dr'] + 1) * math.sin(a))
            seg(d, [(x1, y1), (x2, y2)], 6)
    if p['rays'] and p['rlen']:                        # 放射状亮线
        c = 7 if p['hot'] else 6
        for i in range(p['rays']):
            a = math.radians(p['rphase'] + 360.0 * i / p['rays'])
            x1 = clamp(CX + 3 * math.cos(a))
            y1 = clamp(CY + 3 * math.sin(a))
            x2 = clamp(CX + p['rlen'] * math.cos(a))
            y2 = clamp(CY + p['rlen'] * math.sin(a))
            seg(d, [(x1, y1), (x2, y2)], c)
    if p['spark']:                                     # 闪光帧的外射火星
        base = p['ring'] + 1
        for i in range(p['spark']):
            a = math.radians(45 + 90 * i)
            x1 = clamp(CX + base * math.cos(a))
            y1 = clamp(CY + base * math.sin(a))
            x2 = clamp(CX + (base + 3) * math.cos(a))
            y2 = clamp(CY + (base + 3) * math.sin(a))
            seg(d, [(x1, y1), (x2, y2)], 7)

def draw_fx(d, p):
    """fx：最亮白心（面积小）"""
    if p['fxr']:
        rr = p['fxr']
        rect(d, (CX - rr, CY - rr, CX + rr, CY + rr), p['fxc'])
    if p['tip'] and p['hw']:                           # 光柱顶端的白色尖
        rect(d, (CX - 1, p['top'] - 1, CX + 1, p['top'] + 1), 8)

# ---------------- 4. 姿态表（统一走 pose 一个入口）----------------
def pose(kind='charge', r=4, ring=0, ring2=0, dr=0, dsz=2, n=6, phase=0,
         hot=0, fade=0, conv=0, spark=0, runes=0,
         hw=0, top=8, bot=20, rem=0, mc=0, rays=0, rlen=0, rphase=0,
         fxr=0, fxc=8, tip=0):
    return {'kind': kind, 'r': r, 'ring': ring, 'ring2': ring2,
            'dr': dr, 'dsz': dsz, 'n': n, 'phase': phase,
            'hot': hot, 'fade': fade, 'conv': conv, 'spark': spark,
            'runes': runes, 'hw': hw, 'top': top, 'bot': bot,
            'rem': rem, 'mc': mc, 'rays': rays, 'rlen': rlen,
            'rphase': rphase, 'fxr': fxr, 'fxc': fxc, 'tip': tip}

ACTIONS = {
    # 蓄力（循环）：光点远 → 光球变大 → 环收拢 + 拖尾 → 蓄满闪光（外圈回到接近首帧尺度）
    'charge': [
        pose(r=3,  ring=13, dr=12, dsz=2, n=6, phase=0,  runes=1,
             fxr=0),
        pose(r=4,  ring=10, dr=10, dsz=2, n=6, phase=30, runes=1,
             fxr=1),
        pose(r=5,  ring=7,  dr=7,  dsz=2, n=6, phase=60, runes=1, conv=6,
             fxr=1),
        pose(r=4,  ring=9,  ring2=13, dr=11, dsz=2, n=6, phase=90,
             hot=1, spark=4, runes=1, fxr=2),
    ],
    # 爆发（单发）：光柱升起 → 最亮 + 8 放射线 → 衰减（4 线，换角度）→ 余辉残影
    'burst': [
        pose(kind='burst', hw=2, top=6,  bot=22, mc=9,
             dr=9, dsz=1, n=4, phase=45, rays=0, tip=1),
        pose(kind='burst', hw=3, top=3,  bot=21, mc=10, ring=13,
             hot=1, rays=8, rlen=12, rphase=0,
             dr=11, dsz=2, n=6, phase=15, runes=1, fxr=2, tip=1),
        pose(kind='burst', hw=2, top=7,  bot=20, mc=8, fade=1,
             rays=4, rlen=8, rphase=22,
             dr=8, dsz=1, n=5, phase=200, fxr=1, fxc=7),
        pose(kind='burst', hw=0, rem=3, mc=7, fade=2,
             rays=3, rlen=6, rphase=45,
             dr=6, dsz=1, n=3, phase=300, fxr=0, fxc=7),
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

def check_bounds(im):
    """四边不截断：最外一圈（x/y = 0 或 31）不允许有像素，保证留 1px 余量"""
    px = im.load()
    bad = []
    for i in range(SIZE):
        for (x, y) in ((0, i), (SIZE - 1, i), (i, 0), (i, SIZE - 1)):
            if px[x, y][3]:
                bad.append((x, y))
    return bad

def export():
    if OUT.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{OUT}')
    (OUT / 'frames').mkdir(parents=True)
    frames, sheet_w, imgs = [], 0, []
    for action, poses in ACTIONS.items():
        for i, p in enumerate(poses):
            im = render_frame(p)
            bad = check_bounds(im)
            if bad:
                raise SystemExit(f'{action}_{i} 超出安全边距（可能被切）：{bad}')
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
        OUT / 'contact-sheet-8x.png')                  # 放大一律 NEAREST
    atlas = {'size': [sheet_w, SIZE], 'frame_size': SIZE, 'palette_size': len(PALETTE),
             'layer_order': LAYER_ORDER, 'frames': frames}
    (OUT / 'atlas.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'palette.json').write_text(json.dumps(PALETTE, ensure_ascii=False), encoding='utf-8')
    hashes = [f['rgba_sha256'] for f in frames]
    if len(set(hashes)) != len(hashes):
        dup = [f['id'] for f in frames if hashes.count(f['rgba_sha256']) > 1]
        raise SystemExit(f'姿态重复，必须让每帧有真实差异：{dup}')
    lines = []
    for f in frames:
        sha = hashlib.sha256((OUT / f['file']).read_bytes()).hexdigest()
        lines.append(f'{sha}  {f["file"]}')
    with open(OUT / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'OK -> {OUT}  帧数={len(imgs)}  画布={SIZE}  颜色数={len(PALETTE)}  帧间差异校验=PASS')

if __name__ == '__main__':
    export()
