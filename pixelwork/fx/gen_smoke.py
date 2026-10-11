# -*- coding: utf-8 -*-
"""
烟雾 / 扬尘 特效帧动画生成器（由 frame_anim_template.py 改造）。

用法：
  python gen_smoke.py <输出目录> <pack>
    pack = smoke  -> 6 帧循环烟团（CX=16, CY=16）
    pack = dust   -> 4 帧循环扬尘（CX=16, GROUND_Y=24）

约定（违反就不是像素画）：
  - SIZE=32，有限调色板 <=16 色，索引 0 = 透明，其余 alpha=255（禁止半透明）
  - fill=/outline= 一律传调色板索引
  - 锚点 CX/CY/GROUND_Y 全部写死成常量，帧间只改 r/dy/dx，绝不逐帧重算基准坐标
  - 主体一律索引 1 描边；<=4px 的飞散颗粒不描边
  - 四边不许被切（render_frame 里有越界检查）
"""
import hashlib, json, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32
CX = 16                                   # 水平锚点（两个包共用，写死）
CY = 16                                   # smoke 垂直锚点
GROUND_Y = 24                             # dust 地面锚点（整体偏下）

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / 'demo-output'
PACK = sys.argv[2] if len(sys.argv) > 2 else 'smoke'

PALETTE = [                                           # 索引 -> RGBA
    (0, 0, 0, 0),         # 0  透明
    (34, 30, 44, 255),    # 1  描边深色（两个包共用）
    (188, 188, 198, 255), # 2  灰·浅
    (142, 142, 154, 255), # 3  灰·中
    (100, 100, 112, 255), # 4  灰·深
    (68, 68, 80, 255),    # 5  灰·最深（暗部芯）
    (228, 228, 236, 255), # 6  灰·极浅（back 稀薄外圈）
    (150, 120, 88, 255),  # 7  土·暗
    (186, 152, 110, 255), # 8  土·中
    (216, 188, 146, 255), # 9  土·浅
    (242, 228, 200, 255), # 10 土·高光尘粒
    (250, 250, 255, 255), # 11 白（最亮尘粒）
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']        # 自下而上合成

# ---------------- 2. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)

def rect(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)

def ell(d, box, c, outline=None):
    d.ellipse(box, fill=c, outline=outline)

def seg(d, pts, c, w=1):
    d.line(pts, fill=c, width=w)

def puff_mask(lobes, cx, cy, r):
    """把若干椭圆瓣画进一张 0/1 掩码图，得到烟团/尘团的不规则外形。
    lobes = [(fx, fy, fr)]，单位是 r 的倍数：中心 (cx+fx*r, cy+fy*r)，半径 fr*r。
    锚点只由 cx/cy 决定，因此帧间只换 lobes 就是「翻滚」而不是「漂移」。"""
    m = Image.new('P', (SIZE, SIZE), 0)
    d = ImageDraw.Draw(m)
    for fx, fy, fr in lobes:
        px, py, pr = cx + fx * r, cy + fy * r, max(1.6, fr * r)
        d.ellipse((int(round(px - pr)), int(round(py - pr)),
                   int(round(px + pr)), int(round(py + pr))), fill=1)
    return m

def stamp(d, m, colorfn, outline=1):
    """把掩码落成像素：内部按 colorfn 上色，外圈补 1 像素描边。"""
    mp = m.load()
    for y in range(SIZE):
        for x in range(SIZE):
            if mp[x, y]:
                d.point((x, y), fill=colorfn(x, y))
    if outline is None:
        return
    for y in range(SIZE):
        for x in range(SIZE):
            if mp[x, y]:
                continue
            if ((x > 0 and mp[x - 1, y]) or (x < SIZE - 1 and mp[x + 1, y]) or
                    (y > 0 and mp[x, y - 1]) or (y < SIZE - 1 and mp[x, y + 1])):
                d.point((x, y), fill=outline)

# ---------------- 3. 包配置（调色板共用，配色/锚点分派）----------------
PACKS = {
    'smoke': {
        'anchor_y': CY,
        'back_c': 6,                       # back：极浅灰稀薄外圈
        'bands': {0: (2, 3, 4, 5),         # 上亮下暗四档灰
                  1: (2, 3, 3, 4),
                  2: (2, 2, 3, 3)},
        'back_k': 1.30,
    },
    'dust': {
        'anchor_y': GROUND_Y,
        'back_c': 10,                      # back：土·高光（必须比 body 最亮档更浅，否则外圈和主体糊成一片）
        'bands': {0: (9, 8, 8, 7),
                  1: (9, 9, 8, 8),
                  2: (9, 9, 9, 8)},
        'back_k': 1.40,
    },
}
if PACK not in PACKS:
    raise SystemExit(f'未知特效包：{PACK}，可选 {list(PACKS)}')
CFG = PACKS[PACK]

# ---------------- 4. 四层绘制（帧间只靠姿态参数变化）----------------
def draw_back(d, p):
    """最外圈稀薄烟/尘：比主体大一圈，不描边。"""
    ay = CFG['anchor_y'] + p['dy']
    m = puff_mask(p['lobes'], CX + p['dx'], ay, p['r'] * CFG['back_k'])
    stamp(d, m, lambda x, y: CFG['back_c'], outline=None)

def draw_body(d, p):
    """主体：不规则多瓣烟团，外圈索引 1 描边，内部按高度分三档明暗。"""
    ay = CFG['anchor_y'] + p['dy']
    m = puff_mask(p['lobes'], CX + p['dx'], ay, p['r'])
    bands = CFG['bands'][p['fade']]
    def tone(x, y):
        rel = (y - ay) / max(p['r'], 1.0)
        if rel < -0.35: return bands[0]
        if rel < 0.20:  return bands[1]
        if rel < 0.70:  return bands[2]
        return bands[3]
    stamp(d, m, tone, outline=1)

def draw_weapon(d, p):
    """飞散小颗粒：<=4px，一律不描边（描边会吃成黑块）。"""
    ay = CFG['anchor_y'] + p['dy']
    for fx, fy, sz, c in p['parts']:
        x = int(round(CX + p['dx'] + fx * p['r']))
        y = int(round(ay + fy * p['r']))
        rect(d, (x, y, x + sz - 1, y + sz - 1), c)

def draw_fx(d, p):
    """最亮高光尘粒：1px 点，不描边（smoke 不用这层，dust 点两颗）。"""
    ay = CFG['anchor_y'] + p['dy']
    for fx, fy, sz, c in p['spark']:
        x = int(round(CX + p['dx'] + fx * p['r']))
        y = int(round(ay + fy * p['r']))
        rect(d, (x, y, x + sz - 1, y + sz - 1), c)

# ---------------- 5. 动作表（先排时间轴再填参数）----------------
def pose(r=4.0, dy=0, dx=0, lobes=(), parts=(), spark=(), fade=0):
    """r 半径 / dy 上移(负)下移(正) / dx 后飘 / lobes 外形瓣 / parts 颗粒 / fade 消散档"""
    return {'r': r, 'dy': dy, 'dx': dx, 'lobes': lobes,
            'parts': parts, 'spark': spark, 'fade': fade}

# smoke 时间轴：小团 → 上升变大 → 翻滚 → 拉长 → 变淡 → 接近消失（末帧≈首帧，保证 loop）
# lobes 里的瓣必须互相重叠 >=1px，否则并集会被描边切出内部黑缝
SMOKE = [pose(r=4.0,  dy=+6, fade=0,                                  # 0 小团（贴地）
              lobes=[(-0.35, -0.25, 0.72), (0.35, -0.15, 0.66),
                     (0.05, 0.45, 0.64), (-0.40, 0.40, 0.56)],
              parts=[(1.35, -0.85, 1, 3), (1.95, -1.35, 1, 4)]),
         pose(r=6.0,  dy=+2, fade=0,                                  # 1 上升变大
              lobes=[(-0.40, -0.32, 0.64), (0.38, -0.26, 0.60), (0.30, 0.32, 0.62),
                     (-0.28, 0.38, 0.54), (0.00, 0.02, 0.72)],
              parts=[(-1.70, -0.95, 1, 3), (1.55, -1.15, 2, 4), (1.10, -1.70, 1, 3)]),
         pose(r=7.0,  dy=-2, fade=0,                                  # 2 翻滚：左右极不对称
              lobes=[(-0.55, -0.28, 0.56), (0.20, -0.45, 0.62), (0.58, 0.10, 0.50),
                     (-0.15, 0.45, 0.62), (-0.58, 0.28, 0.50)],
              parts=[(-1.85, -1.05, 1, 4), (1.65, -1.35, 2, 3),
                     (0.95, -1.55, 1, 4), (-1.15, -1.60, 1, 3)]),
         pose(r=6.5,  dy=-4, fade=0,                                  # 3 拉长：窄而高的柱状
              lobes=[(-0.06, -0.78, 0.44), (0.10, -0.36, 0.50), (0.20, 0.05, 0.46),
                     (-0.16, 0.48, 0.44), (0.00, 0.92, 0.40)],
              parts=[(1.55, -1.35, 1, 3), (-1.60, -1.25, 1, 4), (1.15, 1.05, 1, 3)]),
         pose(r=5.0,  dy=-7, fade=2,                                  # 4 变淡：只剩稀薄两瓣+散粒
              lobes=[(0.12, -0.46, 0.56), (-0.50, 0.14, 0.52), (0.34, 0.30, 0.52)],
              parts=[(-1.30, -1.10, 1, 4), (1.25, -0.95, 1, 3), (0.35, -1.25, 1, 3)]),
         pose(r=3.6,  dy=+5, fade=2,                                  # 5 接近消失：新小团回首帧
              lobes=[(-0.30, -0.28, 0.66), (0.42, -0.10, 0.60),
                     (0.02, 0.48, 0.58), (-0.45, 0.28, 0.52)],
              parts=[(1.60, -1.20, 1, 3)])]

# dust 时间轴：起尘(小而实) → 向两侧扩散 → 向后飘(不对称+拖尾) → 变淡回到接近首帧
DUST = [pose(r=3.6, dy=-1, dx=0.0, fade=0,                            # 0 起尘：贴地小而实
             lobes=[(-0.48, 0.15, 0.68), (0.48, 0.10, 0.66),
                    (0.00, -0.35, 0.64), (-0.10, 0.45, 0.58)],
             parts=[(1.70, -1.20, 1, 7), (-1.85, -0.85, 1, 8)],
             spark=[(0.90, -1.55, 1, 10)]),
        pose(r=5.0, dy=-1, dx=0.0, fade=0,                            # 1 扩散：横向拉开
             lobes=[(-1.00, 0.10, 0.50), (1.00, 0.05, 0.50), (0.00, -0.40, 0.58),
                    (-0.34, 0.50, 0.48), (0.42, 0.45, 0.46)],
             parts=[(-1.75, -0.95, 1, 7), (1.70, -1.10, 1, 8), (1.95, -0.55, 1, 7)],
             spark=[(-0.95, -1.30, 1, 10)]),
        pose(r=5.0, dy=-1, dx=-2.5, fade=0,                           # 2 后飘：整体左移+右侧拖尾粒
             lobes=[(-1.00, -0.28, 0.50), (-0.45, 0.15, 0.58), (0.28, 0.05, 0.52)],
             parts=[(-0.95, -1.15, 1, 8), (0.85, -0.85, 1, 7), (1.75, -0.45, 1, 8)],
             spark=[(0.45, -1.35, 1, 11)]),
        pose(r=3.6, dy=-1, dx=+1.0, fade=1,                           # 3 变淡：回到接近首帧的小片
             lobes=[(-0.48, 0.12, 0.62), (0.50, 0.18, 0.60), (0.04, -0.38, 0.60)],
             parts=[(1.60, -1.05, 1, 7)],
             spark=[(-0.85, -1.35, 1, 10)])]

ACTIONS = {'smoke': SMOKE, 'dust': DUST}
ACTIONS = {PACK: ACTIONS[PACK]}                       # 只导出命令行选定的那个包

# ---------------- 6. 渲染 + 导出 ----------------
def check_bounds(im, fid):
    """四边不许被切：任何非透明像素落在 x/y = 0 或 31 都视为越界。"""
    px = im.load()
    for x in range(SIZE):
        if px[x, 0][3] or px[x, SIZE - 1][3]:
            raise SystemExit(f'{fid}: 上下边缘出现像素（被切），x={x}')
    for y in range(SIZE):
        if px[0, y][3] or px[SIZE - 1, y][3]:
            raise SystemExit(f'{fid}: 左右边缘出现像素（被切），y={y}')

def render_frame(p, fid='?'):
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
    check_bounds(out, fid)
    return out

def export():
    if len(PALETTE) > 16:
        raise SystemExit('调色板超过 16 色')
    if PALETTE[0] != (0, 0, 0, 0):
        raise SystemExit('索引 0 必须是透明色')
    for i, c in enumerate(PALETTE):
        if i and c[3] != 255:
            raise SystemExit(f'索引 {i} 存在半透明，违反约定')
    if OUT.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{OUT}')
    (OUT / 'frames').mkdir(parents=True)
    frames, sheet_w = [], 0
    imgs = []
    for action, poses in ACTIONS.items():
        for i, p in enumerate(poses):
            im = render_frame(p, f'{action}_{i}')
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
        OUT / 'contact-sheet-8x.png')                       # 放大一律 NEAREST，禁止抗锯齿
    atlas = {'size': [sheet_w, SIZE], 'frame_size': SIZE, 'palette_size': len(PALETTE),
             'layer_order': LAYER_ORDER, 'pack': PACK, 'frames': frames}
    (OUT / 'atlas.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'palette.json').write_text(json.dumps(PALETTE, ensure_ascii=False), encoding='utf-8')
    hashes = [f['rgba_sha256'] for f in frames]
    if len(set(hashes)) != len(hashes):
        dup = [f['id'] for f in frames if hashes.count(f['rgba_sha256']) > 1]
        raise SystemExit(f'姿态重复，必须让每帧有真实差异：{dup}')
    if not any(Path(OUT / f['file']).stat().st_size for f in frames):
        raise SystemExit('所有帧都是空白，特效未绘制')
    lines = []
    for f in frames:
        sha = hashlib.sha256((OUT / f['file']).read_bytes()).hexdigest()
        lines.append(f'{sha}  {f["file"]}')
    with open(OUT / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'OK -> {OUT}  pack={PACK}  帧数={len(imgs)}  画布={SIZE}  '
          f'颜色数={len(PALETTE)}  帧间差异校验=PASS')

if __name__ == '__main__':
    export()
