# -*- coding: utf-8 -*-
"""
通用像素帧动画模板 —— 自包含，只依赖 Pillow，不依赖任何专家插件。

用法（给任何 Agent 的说明书）：
  1. 改 PALETTE：定义你的角色配色（索引 0 必须透明）。
  2. 改 CHARACTER 绘制函数：draw_back / draw_body / draw_weapon / draw_fx
     用矩形/椭圆/多边形/线段在 64x64 网格上画，fill 用「调色板索引」而不是 RGB。
  3. 填 ACTIONS：每个动作一个姿态参数列表，一帧一组参数。
  4. 运行：python frame_anim_template.py   → 输出完整交付包。

约定（违反就不是像素画）：
  - 有限调色板（<=16 色），索引 0 = 透明
  - 只画硬边，放大一律 NEAREST，禁止抗锯齿/模糊
  - 关键锚点（头/腰/脚）固定，姿态只做相对偏移，否则帧间会抖
  - 每帧姿态必须有真实差异
"""
import hashlib, json, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 64
# 输出目录：命令行第一个参数可指定，默认脚本同目录下 demo-output
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'demo-output'

PALETTE = [                                           # 索引 -> RGBA
    (0, 0, 0, 0),        # 0 透明
    (34, 30, 44, 255),   # 1 描边/深色
    (70, 78, 104, 255),  # 2 主色（斗篷）
    (122, 134, 168, 255),# 3 主色亮部
    (44, 52, 74, 255),   # 4 主色暗部
    (240, 240, 248, 255),# 5 白
    (255, 214, 180, 255),# 6 皮肤
    (226, 170, 130, 255),# 7 皮肤暗
    (198, 70, 70, 255),  # 8 红（围巾）
    (232, 186, 92, 255), # 9 金
    (150, 200, 255, 255),# 10 剑刃青
    (96, 210, 130, 255), # 11 绿瞳
    (120, 226, 255, 255),# 12 特效青
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

# ---------------- 3. 角色造型（示例：斗篷剑士）----------------
# 姿态参数约定：
#   dy   整体上下位移（正=下沉）
#   lean 身体前倾像素（正=向右倾）
#   legs 0并立 1左前 2右前 3收腿 4大跨
#   swing 披风/头发摆动像素
#   arm  手的坐标(x,y)，None=垂放
#   fx   特效名，None=无

def draw_back(d, p):                                  # 背后：披风
    y, sw = p['dy'], p['swing']
    d.polygon([(26, 26 + y), (40, 26 + y),
               (44 + sw, 40 + y), (38 + sw, 46 + y),
               (28 + sw, 46 + y), (22 + sw, 40 + y)], fill=2, outline=1)
    seg(d, [(30, 28 + y), (28 + sw, 44 + y)], 4, 1)
    seg(d, [(36, 28 + y), (38 + sw, 44 + y)], 4, 1)

def draw_body(d, p):
    y, x, legs = p['dy'], p['lean'], p['legs']
    # 躯干
    d.polygon([(27 + x, 26 + y), (39 + x, 26 + y),
               (41 + x, 36 + y), (25 + x, 36 + y)], fill=2, outline=1)
    rect(d, (30 + x, 27 + y, 36 + x, 32 + y), 3)
    seg(d, [(26 + x, 33 + y), (40 + x, 33 + y)], 9, 1)          # 金腰带
    # 围巾
    rect(d, (28 + x, 24 + y, 38 + x, 26 + y), 8, 1)
    # 头
    ell(d, (27 + x, 14 + y, 39 + x, 26 + y), 6, outline=1)
    d.polygon([(27 + x, 15 + y), (39 + x, 15 + y),
               (39 + x, 19 + y), (33 + x, 17 + y), (27 + x, 19 + y)], fill=1)
    rect(d, (30 + x, 19 + y, 31 + x, 20 + y), 11)                # 左眼
    rect(d, (35 + x, 19 + y, 36 + x, 20 + y), 11)                # 右眼
    # 腿
    def shoe(lx, ly):
        rect(d, (lx, ly, lx + 4, ly + 3), 4, outline=1)
    if legs == 0:
        rect(d, (29 + x, 36 + y, 31 + x, 50 + y), 4, outline=1); shoe(27 + x, 50 + y)
        rect(d, (35 + x, 36 + y, 37 + x, 50 + y), 4, outline=1); shoe(35 + x, 50 + y)
    elif legs == 1:
        seg(d, [(30 + x, 37 + y), (26 + x, 48 + y)], 4, 3); shoe(23 + x, 48 + y)
        seg(d, [(36 + x, 37 + y), (38 + x, 48 + y)], 4, 3); shoe(37 + x, 48 + y)
    elif legs == 2:
        seg(d, [(30 + x, 37 + y), (28 + x, 48 + y)], 4, 3); shoe(25 + x, 48 + y)
        seg(d, [(36 + x, 37 + y), (41 + x, 48 + y)], 4, 3); shoe(40 + x, 48 + y)
    elif legs == 3:
        rect(d, (29 + x, 36 + y, 31 + x, 44 + y), 4, outline=1); shoe(27 + x, 44 + y)
        rect(d, (35 + x, 36 + y, 37 + x, 43 + y), 4, outline=1); shoe(36 + x, 43 + y)
    elif legs == 4:
        seg(d, [(29 + x, 37 + y), (21 + x, 46 + y)], 4, 3); shoe(18 + x, 46 + y)
        seg(d, [(37 + x, 37 + y), (44 + x, 44 + y)], 4, 3); shoe(43 + x, 44 + y)
    # 手臂（arm=None 时垂放，否则伸向该点）
    if p['arm'] is None:
        seg(d, [(38 + x, 28 + y), (40 + x, 34 + y)], 6, 3)
        rect(d, (39 + x, 34 + y, 41 + x, 36 + y), 6, outline=1)
    else:
        seg(d, [(38 + x, 28 + y), (p['arm'][0], p['arm'][1] + y)], 6, 3)
        rect(d, (p['arm'][0] - 1, p['arm'][1] + y - 1, p['arm'][0] + 1, p['arm'][1] + y + 1), 6, outline=1)

def draw_weapon(d, p):                                 # 单手剑
    y, x, arm = p['dy'], p['lean'], p['arm']
    ax = arm[0] if arm else 40 + x
    ay = (arm[1] if arm else 34) + y
    seg(d, [(ax - 1, ay), (ax - 1, ay - 16)], 10, 2)   # 剑刃
    d.polygon([(ax - 1, ay - 16), (ax - 3, ay - 12), (ax + 1, ay - 12)], fill=5, outline=1)
    seg(d, [(ax - 3, ay - 2), (ax + 2, ay - 2)], 9, 2) # 护手
    seg(d, [(ax - 1, ay - 1), (ax - 1, ay + 3)], 4, 2) # 剑柄

def draw_fx(d, p):
    kind, y = p['fx'], p['dy']
    if kind == 'slash':
        d.arc((38, 20 + y, 60, 44 + y), 300, 60, fill=12, width=2)
        d.arc((40, 22 + y, 58, 42 + y), 310, 50, fill=5, width=1)
    elif kind == 'dust':
        ell(d, (44, 50 + y, 50, 54 + y), 5, outline=1)
        ell(d, (50, 52 + y, 55, 55 + y), 3)

# ---------------- 4. 动作表（一帧一组姿态参数）----------------
def pose(dy=0, lean=0, legs=0, swing=0, arm=None, fx=None):
    return {'dy': dy, 'lean': lean, 'legs': legs, 'swing': swing, 'arm': arm, 'fx': fx}

ACTIONS = {
    # 行走：迈左 → 抬起过渡 → 迈右 → 中立过渡（四帧必须两两不同，否则就是浪费图集的重复帧）
    'walk':  [pose(1, 0, 1, 1), pose(-1, 0, 0, 0), pose(1, 0, 2, -1), pose(0, 0, 0, 0)],
    'run':   [pose(0, 2, 4, -2), pose(-1, 2, 2, -3), pose(0, 2, 4, 1), pose(-1, 2, 1, 2)],
    'jump':  [pose(3, 0, 3, 2), pose(-3, 0, 0, -2), pose(-7, 0, 3, -2), pose(-2, 0, 0, 1, fx='dust')],
    'attack':[pose(0, 0, 0, 0, arm=(46, 30)),
              pose(0, 1, 2, 1, arm=(48, 26)),
              pose(0, 2, 2, 2, arm=(46, 24), fx='slash'),
              pose(1, 1, 0, 0, arm=(44, 32))],
}

# ---------------- 5. 渲染 + 导出 ----------------
def render_frame(p):
    layers = {}
    im = new_layer(); draw_back(ImageDraw.Draw(im), p);   layers['back'] = im
    im = new_layer(); draw_body(ImageDraw.Draw(im), p);   layers['body'] = im
    im = new_layer(); draw_weapon(ImageDraw.Draw(im), p); layers['weapon'] = im
    im = new_layer(); draw_fx(ImageDraw.Draw(im), p);     layers['fx'] = im
    # 按 LAYER_ORDER 逐像素合成为 RGBA（索引 0 = 透明，上层覆盖下层）
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
    frames, sheet_w = [], 0
    imgs = []
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
        OUT / 'contact-sheet-8x.png')                       # 放大一律 NEAREST，禁止抗锯齿
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
    manifest = '\n'.join(f'{f["rgba_sha256"]}  {f["file"]}' for f in frames)
    (OUT / 'manifest.sha256').write_text(manifest, encoding='utf-8')
    print(f'OK -> {OUT}  帧数={len(imgs)}  画布={SIZE}  颜色数={len(PALETTE)}  帧间差异校验=PASS')
    print('下一步：真实打开 contact-sheet-8x.png 目检轮廓/姿态差异/部位一致/不截断')

if __name__ == '__main__':
    export()
