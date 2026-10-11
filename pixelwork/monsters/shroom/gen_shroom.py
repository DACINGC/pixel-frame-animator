# -*- coding: utf-8 -*-
"""
毒蘑菇怪 Shroom —— 32x32 像素帧动画生成器
（由 pixel-frame-animator/scripts/frame_anim_template.py 改造，原文件未改动）

用法：
  PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
  "$PY" gen_shroom.py <outdir> locomotion     # move_0..3 + hit_0..1
  "$PY" gen_shroom.py <outdir> combat         # attack_0..3 + death_0..3
"""
import hashlib, json, math, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / 'shroom-out'
PACK = sys.argv[2] if len(sys.argv) > 2 else 'locomotion'

PALETTE = [                                          # idx -> RGBA，全部 alpha=255
    (0, 0, 0, 0),          # 0  透明
    (34, 30, 44, 255),     # 1  描边深色（强制）
    (200, 69, 60, 255),    # 2  伞盖红 #C8453C
    (232, 103, 92, 255),   # 3  伞盖亮部 #E8675C
    (142, 46, 42, 255),    # 4  伞盖暗部 #8E2E2A
    (242, 237, 228, 255),  # 5  白（斑点 / 闪白）
    (240, 228, 200, 255),  # 6  菌柄奶油白 #F0E4C8
    (196, 179, 148, 255),  # 7  菌柄暗 #C4B394
    (214, 58, 58, 255),    # 8  受击红（闪白时的描边 / 受击暗红）
    (92, 62, 52, 255),     # 9  菌褶暗棕
    (170, 74, 190, 255),   # 10 孢子紫
    (226, 140, 236, 255),  # 11 孢子紫亮
    (150, 206, 86, 255),   # 12 孢子黄绿
    (214, 238, 150, 255),  # 13 孢子黄绿亮
    (150, 150, 164, 255),  # 14 尘土灰
    (86, 86, 104, 255),    # 15 尘土暗 / 落地影
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']        # 自下而上

# ---------------- 2. 锚点常量（写死，姿态只做相对偏移）----------------
CAP_CX  = 16        # 伞盖水平中心（中立）
TOP_Y   = 8         # 中立姿态伞顶行
FOOT_Y  = 27        # 脚底行（站在画布底部）
CAP_H   = 8         # 伞盖行数（含顶行与底行）
CAP_HW  = 9         # 伞盖底边半宽 -> 全宽 19
STEM_H  = 8         # 菌柄行数（17..24）
STEM_HW = 4         # 菌柄半宽 -> 全宽 8（列 cx-4..cx+3）
FOOT_H  = 3         # 脚行数（25..27）

# ---------------- 3. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)

def clamp_row(y):
    return max(0, min(SIZE - 1, y))

def clamp_col(x):
    return max(0, min(SIZE - 1, x))

def hline(d, y, x0, x1, c):
    if x1 < x0 or c == 0:
        return
    y = clamp_row(y)
    x0, x1 = clamp_col(x0), clamp_col(x1)
    d.line([(x0, y), (x1, y)], fill=c)

def dot(d, x, y, c):
    if 0 <= x < SIZE and 0 <= y < SIZE:
        d.point((x, y), fill=c)

def box(d, x0, y0, x1, y1, c, outline=None):
    if x1 < x0 or y1 < y0:
        return
    d.rectangle([clamp_col(x0), clamp_row(y0), clamp_col(x1), clamp_row(y1)],
                fill=c, outline=outline)

def disc(d, x0, y0, x1, y1, c, outline=None):
    """椭圆色块，outline 可选（<=4px 的小部件不要传 outline）"""
    if x1 < x0 or y1 < y0:
        return
    d.ellipse([clamp_col(x0), clamp_row(y0), clamp_col(x1), clamp_row(y1)],
              fill=c, outline=outline)

# ---------------- 4. 几何（全部由锚点常量推导）----------------
def geom(p):
    lift = p['lift']
    cx = CAP_CX + p['lean']
    foot_bot  = FOOT_Y - lift
    feet_top  = foot_bot - (FOOT_H - 1)
    stem_bot  = feet_top - 1
    stem_rows = max(4, STEM_H + p['stem_dh'])
    stem_top  = stem_bot - (stem_rows - 1)
    gill_y    = stem_top - 1
    cap_bot   = gill_y - 1 + p['capdy']
    cap_rows  = max(3, CAP_H + p['cap_dh'])
    cap_top   = cap_bot - (cap_rows - 1)
    hw        = max(3, CAP_HW + p['cap_dw'])
    return dict(cx=cx, cap_top=cap_top, cap_bot=cap_bot, cap_rows=cap_rows, hw=hw,
                stem_top=stem_top, stem_bot=stem_bot, stem_rows=stem_rows,
                gill_y=gill_y, feet_top=feet_top, foot_bot=foot_bot)

def check_bounds(p, g, fid):
    y = min(g['cap_top'] - 1, g['stem_top'], g['feet_top'])
    top_ok = y >= 0
    x0 = g['cx'] - g['hw'] - 1
    x1 = g['cx'] + g['hw'] + 1
    xok = x0 >= 0 and x1 <= SIZE - 1
    if not (top_ok and xok):
        raise SystemExit(f'{fid} 超出画布: y={y} x=[{x0},{x1}] (画布 0..{SIZE-1})')

# ---------------- 5. 配色映射（flash / tint 只换索引，不改坐标）----------------
def colors(p):
    if p['flash']:
        return dict(out=8, main=5, light=5, dark=5, stem=5, stemdark=5,
                    gill=5, foot=5, footdark=5, face=1)
    if p['tint']:                       # 受击暗红：整体降一档
        return dict(out=1, main=8, light=2, dark=4, stem=7, stemdark=7,
                    gill=9, foot=7, footdark=9, face=1)
    return dict(out=1, main=2, light=3, dark=4, stem=6, stemdark=7,
                gill=9, foot=6, footdark=7, face=1)

# ---------------- 6. back 层：菌褶 + 落地影 ----------------
def draw_back(d, p, g, c):
    cx, gill, hw = g['cx'], g['gill_y'], g['hw']
    if p['remains']:
        hline(d, FOOT_Y, cx - hw + 3, cx + hw - 3, 15)      # 地面残影
        return
    gw = hw - 1
    hline(d, gill, cx - gw - 1, cx + gw + 1, c['out'])
    hline(d, gill, cx - gw, cx + gw, c['gill'])
    for x in range(cx - gw + 1, cx + gw, 2):               # 菌褶竖纹
        dot(d, x, gill, c['out'])
    if p['fx'] == 'dust':                                   # 落地尘：身后一小团
        disc(d, cx + 5, g['foot_bot'] - 1, cx + 9, g['foot_bot'] + 1, 14)
        dot(d, cx + 10, g['foot_bot'] - 1, 14)

# ---------------- 7. body 层 ----------------
def cap_halfwidth(y, cap_top, cap_bot, hw):
    rows = cap_bot - cap_top + 1
    vy = (cap_bot - y) / float(max(1, rows - 1))            # 0=底行 1=顶行
    vy = max(0.0, min(1.0, vy))
    return int(round(hw * math.sqrt(max(0.0, 1.0 - vy * vy)))), vy

SPOTS = [(-0.55, 0.62, 3), (0.42, 0.40, 3), (-0.10, 0.22, 2), (0.72, 0.74, 2)]
#  (u=行半宽比例, v=高度比例(0底1顶), 尺寸)

def blob(d, x, y, s, c):
    """白色圆斑点：<=4px，绝不描边，只做削角"""
    if s >= 3:
        hline(d, y,     x + 1, x + s - 2, c)
        hline(d, y + 1, x,     x + s - 1, c)
        hline(d, y + 2, x + 1, x + s - 2, c)
    else:
        box(d, x, y, x + s - 1, y + s - 1, c)

def draw_cap(d, p, g, c):
    cx, cap_top, cap_bot, hw = g['cx'], g['cap_top'], g['cap_bot'], g['hw']
    rows = cap_bot - cap_top + 1
    # --- 描边 pass：向外扩 1px ---
    dot(d, cx, cap_top - 1, c['out'])
    for i in range(rows):
        y = cap_top + i
        w, _ = cap_halfwidth(y, cap_top, cap_bot, hw)
        hline(d, y, cx - w - 1, cx + w + 1, c['out'])
    # --- 填色 pass ---
    for i in range(rows):
        y = cap_top + i
        w, vy = cap_halfwidth(y, cap_top, cap_bot, hw)
        x0, x1 = cx - w, cx + w
        base = c['dark'] if i >= rows - 1 else c['main']
        hline(d, y, x0, x1, base)
        if w >= 3:
            lw = max(1, int(w * 0.45))
            if vy > 0.30:                                   # 左上亮部
                hline(d, y, x0 + 1, x0 + lw, c['light'])
            sw = max(1, int(w * 0.40))                      # 右侧暗部
            if vy < 0.95:
                hline(d, y, x1 - sw, x1 - 1, c['dark'])
    # --- 白斑点 ---
    if not p['flash']:
        for u, v, s in SPOTS:
            i = int(round(v * (rows - 1)))
            y = cap_top + i
            if y > cap_bot - 1:
                continue
            w, _ = cap_halfwidth(y, cap_top, cap_bot, hw)
            px = cx + int(round(u * max(1, w - s)))
            if abs(px - cx) + s // 2 > w - 1:               # 顶到描边就跳过
                continue
            blob(d, px - s // 2, clamp_row(y - s // 2), s, 5)

def draw_stem(d, p, g, c):
    cx, top, bot = g['cx'], g['stem_top'], g['stem_bot']
    rows = bot - top + 1
    if rows < 2:
        return
    for i in range(rows):
        y = top + i
        if i == 0:
            a, b = cx - STEM_HW + 1, cx + STEM_HW - 2       # 顶行收窄
        else:
            a, b = cx - STEM_HW, cx + STEM_HW - 1
        hline(d, y, a - 1, b + 1, c['out'])
    for i in range(rows):
        y = top + i
        if i == 0:
            a, b = cx - STEM_HW + 1, cx + STEM_HW - 2
        elif i == rows - 1:
            a, b = cx - STEM_HW + 1, cx + STEM_HW - 2       # 底行略收
        else:
            a, b = cx - STEM_HW, cx + STEM_HW - 1
        hline(d, y, a, b, c['stem'])
        if b - a >= 3:                                       # 右侧暗面
            hline(d, y, b - 1, b, c['stemdark'])
    if rows >= 4:
        hline(d, top + 1, cx - STEM_HW + 1, cx - STEM_HW + 2, c['main'] if False else c['stem'])

def draw_face(d, p, g, c):
    if not p['face'] or g['stem_rows'] < 5:
        return
    cx, top, bot = g['cx'], g['stem_top'], g['stem_bot']
    ey = top + 2                                             # 眼睛偏左：[cx-4..cx-3] 与 [cx..cx+1]
    if p['flash']:                                           # 受击：眼睛变横线
        for ex in (cx - 4, cx + 0):
            hline(d, ey + 1, ex, ex + 2, c['face'])
        return
    for ex in (cx - 4, cx + 0):
        box(d, ex, ey, ex + 1, ey + 1, c['face'])            # 2x2 豆豆眼，不描边
        hline(d, ey + 2, ex, ex + 1, c['stemdark'])          # 单侧暗线做眼窝
    m = p['mouth']
    if m == 0:                                               # 闭嘴
        hline(d, ey + 4, cx - 3, cx - 1, c['face'])
    elif m == 1:                                             # 常态小嘴
        hline(d, ey + 4, cx - 3, cx - 1, c['face'])
        dot(d, cx - 2, ey + 5, c['stemdark'])
    else:                                                    # 张嘴（准备喷孢子）
        my = min(ey + 4, bot - 1)
        box(d, cx - 4, my, cx, my + 1, 1)
        if my + 2 <= bot:
            hline(d, my + 2, cx - 3, cx - 1, 1)
        dot(d, cx - 2, my + 1, c['main'])                    # 舌头
        if my + 1 <= bot:
            dot(d, cx - 1, my + 1, c['dark'])

def draw_feet(d, p, g, c):
    cx, top, bot = g['cx'], g['feet_top'], g['foot_bot']
    legs = p['legs']
    if legs == 0:      lp, rp = (-6, 1)
    elif legs == 1:    lp, rp = (-5, 0)
    elif legs == 2:    lp, rp = (-7, 2)
    else:              lp, rp = (-4, 0)                      # legs==3 腾空收腿
    rows = bot - top + 1
    for ox in (lp, rp):
        x0, x1 = cx + ox, cx + ox + 2
        if legs == 3 and rows >= 2:                          # 收腿：短而尖
            box(d, x0, top, x1, bot - 1, c['foot'])
            hline(d, bot, x0, x1, c['footdark'])
            continue
        box(d, x0 - 1, top - 1, x1 + 1, bot + 1, c['out'])
        box(d, x0, top, x1, bot, c['foot'])
        hline(d, bot, x0, x1, c['footdark'])
        if bot - top >= 2:
            dot(d, x1, bot - 1, c['footdark'])

def draw_body(d, p, g, c):
    if p['remains']:                                         # 死亡末帧：只剩伞盖残片
        draw_cap(d, p, g, c)
        return
    draw_stem(d, p, g, c)
    draw_face(d, p, g, c)
    draw_feet(d, p, g, c)
    draw_cap(d, p, g, c)                                     # 伞盖画最后 -> 塌陷时压住柄与脸

# ---------------- 8. weapon 层：向左喷出的孢子云 ----------------
def draw_weapon(d, p, g, c):
    lv = p['spore']
    if lv == 0:
        return
    cx = g['cx']
    my = g['stem_top'] + 4                                   # 出孢子的嘴部高度
    ox = cx - 8                                              # 云心
    oy = my - 1
    if lv == 1:                                              # 残余：一小团 + 两粒
        disc(d, ox - 2, oy - 2, ox + 1, oy + 1, 10, outline=1)
        dot(d, ox - 1, oy - 1, 11)
        dot(d, ox - 4, oy - 4, 12)
        dot(d, ox + 2, oy - 3, 13)
    elif lv == 2:
        disc(d, ox - 3, oy - 3, ox + 2, oy + 2, 10, outline=1)
        dot(d, ox - 1, oy - 1, 11)
        disc(d, ox - 1, oy - 6, ox + 3, oy - 3, 12, outline=1)
        dot(d, ox + 1, oy - 5, 13)
        dot(d, ox - 6, oy + 1, 13)
        hline(d, oy, cx - 5, cx - 3, 11)
    else:                                                    # lv==3 命中帧：大团孢子云
        disc(d, ox - 5, oy - 4, ox + 2, oy + 3, 10, outline=1)
        disc(d, ox - 3, oy - 3, ox + 0, oy + 1, 11)
        disc(d, ox - 1, oy - 8, ox + 4, oy - 3, 12, outline=1)
        dot(d, ox + 1, oy - 6, 13)
        disc(d, ox - 9, oy + 1, ox - 5, oy + 5, 12, outline=1)
        dot(d, ox - 7, oy + 3, 13)
        dot(d, ox + 4, oy + 1, 11)
        dot(d, ox - 2, oy + 5, 11)
        dot(d, ox + 3, oy - 10, 13)
        hline(d, oy + 1, cx - 4, cx - 2, 11)                 # 从嘴里拖出的尾迹
        dot(d, cx - 1, oy + 1, 5)

# ---------------- 9. fx 层：特效 ----------------
def draw_fx(d, p, g, c):
    kind = p['fx']
    cx, foot = g['cx'], g['foot_bot']
    cap_top = g['cap_top']
    if kind == 'charge':                                     # 吸气：向嘴汇聚的小点
        my = g['stem_top'] + 4
        for dx, dy in ((-3, -5), (-6, -1), (-2, 4), (3, -4), (5, 1)):
            dot(d, cx + dx, my + dy, 12)
        dot(d, cx - 4, my - 2, 13)
        dot(d, cx - 5, my + 1, 13)
    elif kind == 'impact':                                   # 命中冲击
        disc(d, cx - 14, cap_top + 6, cx - 6, g['stem_top'] + 8, 11, outline=1)
        d.arc([cx - 12, cap_top + 8, cx - 4, g['stem_top'] + 6], 250, 430, fill=5, width=1)
        for dx, dy in ((-13, -2), (-12, 6), (-3, -6), (-3, 8)):
            dot(d, cx + dx, cap_top + 12 + dy, 13)
        dot(d, cx - 9, cap_top + 12, 5)
    elif kind == 'drift':                                    # 收势：残余孢子飘散
        my = g['stem_top'] + 3
        for dx, dy in ((-4, -2), (-7, -5), (-10, -7), (-6, -8), (-12, -3)):
            dot(d, cx + dx, my + dy, 12)
        dot(d, cx - 9, my - 6, 13)
        dot(d, cx - 5, my - 4, 11)
    elif kind == 'spark':                                    # 受击星花
        sy = cap_top + 6
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            dot(d, cx - 8 + dx, sy + dy, 5)
        dot(d, cx - 8, sy, 8)
    elif kind == 'fade':                                     # 死亡末帧：向上飘散
        for i, (dx, dy) in enumerate(((-4, -2), (-6, -5), (-2, -7), (-8, -8), (-4, -11))):
            col = 10 if i % 2 == 0 else 12
            dot(d, cx + dx, g['cap_top'] - 1 + dy, col)
        dot(d, cx - 6, g['cap_top'] - 4, 13)
        dot(d, cx - 2, g['cap_top'] - 9, 11)
        hline(d, foot + 1, cx - 6, cx + 2, 15)               # 地上残影

# ---------------- 10. 姿态入口（唯一）----------------
def pose(lift=0, lean=0, cap_dh=0, cap_dw=0, stem_dh=0, legs=0, mouth=1,
         flash=0, tint=0, spore=0, fx=None, capdy=0, remains=0, face=1):
    return dict(lift=lift, lean=lean, cap_dh=cap_dh, cap_dw=cap_dw, stem_dh=stem_dh,
                legs=legs, mouth=mouth, flash=flash, tint=tint, spore=spore,
                fx=fx, capdy=capdy, remains=remains, face=face)

ACTIONS = {
    # 一蹦一蹦前进：深蹲蓄力 -> 弹起离地拉长 -> 落地压扁 -> 回弹（接近起始帧）
    'move': [pose(cap_dh=-2, cap_dw=3, stem_dh=-2, legs=1),
             pose(lift=3, lean=-1, cap_dw=-1, stem_dh=1, legs=3),
             pose(lean=1, cap_dh=-2, cap_dw=3, stem_dh=-2, legs=2, fx='dust'),
             pose(cap_dh=-1, cap_dw=1, stem_dh=-1, legs=1)],
    # 喷孢子：吸气鼓起 -> 张嘴前倾 -> 命中（孢子云 + 冲击） -> 收势残余
    'attack': [pose(lean=1, cap_dh=2, cap_dw=1, stem_dh=-1, legs=1, mouth=0, fx='charge'),
               pose(lean=-2, legs=0, mouth=2),
               pose(lean=-2, cap_dh=-1, cap_dw=2, stem_dh=-1, legs=2, mouth=2,
                    spore=3, fx='impact'),
               pose(lean=-1, legs=0, mouth=1, spore=1, fx='drift')],
    # 受击：闪白压扁 -> 回弹带受击暗红
    'hit': [pose(lean=1, cap_dh=-2, cap_dw=3, stem_dh=-2, legs=2, mouth=2,
                 flash=1, fx='spark'),
            pose(lift=1, lean=-1, legs=3, tint=1)],
    # 死亡：抖 -> 伞盖塌陷 -> 倾倒 -> 一摊残片 + 飘散孢子
    'death': [pose(lean=-1, cap_dh=-1, cap_dw=2, stem_dh=-1, legs=2, mouth=2,
                   flash=1, fx='spark'),
              pose(lean=1, cap_dh=-4, cap_dw=3, stem_dh=-4, legs=2, mouth=2,
                   tint=1, capdy=2),
              pose(lean=2, cap_dh=-3, cap_dw=2, stem_dh=-4, legs=2,
                   tint=1, capdy=6, face=0),
              pose(lean=2, cap_dh=-5, cap_dw=-2, stem_dh=-4,
                   tint=1, capdy=7, remains=1, face=0, fx='fade')],
}
PACKS = {'locomotion': ['move', 'hit'], 'combat': ['attack', 'death']}

# ---------------- 11. 渲染 + 导出 ----------------
def render_frame(p):
    g = geom(p)
    c = colors(p)
    layers = {}
    for name in LAYER_ORDER:
        im = new_layer()
        {'back': draw_back, 'body': draw_body,
         'weapon': draw_weapon, 'fx': draw_fx}[name](ImageDraw.Draw(im), p, g, c)
        layers[name] = im
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
    if PACK not in PACKS:
        raise SystemExit(f'未知包 {PACK}，可选：{list(PACKS)}')
    if OUT.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{OUT}')
    (OUT / 'frames').mkdir(parents=True)
    imgs, frames = [], []
    total = 0
    for action in PACKS[PACK]:
        for i, p in enumerate(ACTIONS[action]):
            g = geom(p)
            fid = f'{action}_{i}'
            check_bounds(p, g, fid)
            im = render_frame(p)
            im.save(OUT / 'frames' / f'{fid}.png')
            imgs.append((fid, im))
            frames.append({'id': fid, 'action': action, 'order': total,
                           'file': f'frames/{fid}.png',
                           'rect': [total * SIZE, 0, SIZE, SIZE],
                           'rgba_sha256': hashlib.sha256(im.tobytes()).hexdigest()})
            total += 1
    sheet_w = total * SIZE
    sheet = Image.new('RGBA', (sheet_w, SIZE), (0, 0, 0, 0))
    for i, (_, im) in enumerate(imgs):
        sheet.paste(im, (i * SIZE, 0))
    sheet.save(OUT / 'sprite-sheet.png')
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.Resampling.NEAREST).save(
        OUT / 'contact-sheet-8x.png')
    atlas = {'size': [sheet_w, SIZE], 'frame_size': SIZE, 'palette_size': len(PALETTE),
             'layer_order': LAYER_ORDER, 'anchors': {'CAP_CX': CAP_CX, 'TOP_Y': TOP_Y,
                                                     'FOOT_Y': FOOT_Y, 'CAP_H': CAP_H,
                                                     'CAP_HW': CAP_HW, 'STEM_H': STEM_H,
                                                     'STEM_HW': STEM_HW},
             'frames': frames}
    (OUT / 'atlas.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2),
                                    encoding='utf-8')
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
    print(f'OK -> {OUT}  包={PACK}  帧数={total}  画布={SIZE}  颜色数={len(PALETTE)}')
    print('帧清单：' + ' '.join(f['id'] for f in frames))
    print('下一步：真实打开 contact-sheet-8x.png 目检轮廓/姿态差异/部位一致/不截断')

if __name__ == '__main__':
    export()
