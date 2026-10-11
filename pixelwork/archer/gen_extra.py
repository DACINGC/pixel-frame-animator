# -*- coding: utf-8 -*-
"""云纹游侠 —— 追加动作包：死亡 / 大招

设计原则（沿用 GUIDE.md）：
  * 不修改 gen_project.py —— 造型代码全部来自那里，本文件只做「新能力 + 新姿态参数」。
  * 姿态 = 参数，不为每帧重写绘制代码。
  * 旋转回落 mandated: 用前向映射 + 补洞，纯 NEAREST，禁止插值/模糊。

用法：
  python gen_extra.py <输出目录> <death|ultimate|all>
"""
import sys, json, hashlib, math
from pathlib import Path
from PIL import Image, ImageDraw

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

import gen_project as G                      # 角色造型的唯一定义源

SIZE = G.SIZE
PALETTE = G.PALETTE
new = G.new
r, ell, line = G.r, G.ell, G.line
GRIP = G.GRIP                                # 弓把基准 (9,32)
BOW_BBOX = G.BOW_BBOX

C_TR, C_OUT, C_BLUE, C_LBLUE, C_DBLUE = 0, 1, 2, 3, 4
C_WHITE, C_SKIN, C_SKIND, C_ORANGE, C_ORLIT = 5, 6, 7, 8, 9
C_RED, C_SOCKS, C_GOLD, C_GREEN, C_CYAN, C_RESID = 10, 11, 12, 13, 14, 15

# ------------------------------------------------------------------ 图层小工具
def _L(fn):
    """起一张空索引图层，把 fn 的绘制结果画进去"""
    im = new()
    fn(ImageDraw.Draw(im))
    return im

def _noop(*a, **k):
    pass

def merge(imgs):
    """多张索引图层合成为一张（上层非透明覆盖下层）"""
    out = new()
    px = out.load()
    for im in imgs:
        sp = im.load()
        for y in range(SIZE):
            for x in range(SIZE):
                c = sp[x, y]
                if c:
                    px[x, y] = c
    return out

# -------------------------------------------------------------- 几何变换（硬边）
def rotate_points(src, deg, pivot=(0, 0)):
    """前向映射旋转：每个源像素写出一个目标像素，绝不做插值。正角度 = 画面顺时针。"""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    px0, py0 = pivot
    sp = src.load()
    pts = {}
    for y in range(SIZE):
        for x in range(SIZE):
            c = sp[x, y]
            if not c:
                continue
            dx, dy = x - px0, y - py0
            pts[(round(px0 + dx * ca - dy * sa), round(py0 + dx * sa + dy * ca))] = c
    return pts

def fill_holes(pts, rounds=1):
    """前向映射在斜角会留下 1px 星点空隙，补掉：三面有邻点点就填"""
    for _ in range(rounds):
        add = {}
        for (x, y), c in list(pts.items()):
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in pts or not (0 <= nx < SIZE and 0 <= ny < SIZE):
                    continue
                nb = sum(((nx + a, ny + b) in pts) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if nb >= 3:
                    add.setdefault((nx, ny), c)
        pts.update(add)
    return pts

def _bbox(pts):
    xs, ys = zip(*pts.keys())
    return min(xs), min(ys), max(xs), max(ys)

def dict_to_img(pts):
    im = new()
    px = im.load()
    for (x, y), c in pts.items():
        if 0 <= x < SIZE and 0 <= y < SIZE:
            px[x, y] = c
    return im

def rot_fit(src, deg, pivot=(0, 0), bottom=None, left=None, roundh=1):
    """旋转后自动落到指定底边/左边，并保证不贴边溢出"""
    pts = rotate_points(src, deg, pivot)
    fill_holes(pts, roundh)
    if not pts:
        return new()
    x0, y0, x1, y1 = _bbox(pts)
    mx = my = 0
    if bottom is not None:
        my = bottom - y1
    if left is not None:
        mx = left - x0
    # 夹进画布，四边至少留 2px
    mx = min(max(mx, 2 - x0), SIZE - 3 - x1)
    my = min(max(my, 2 - y0), SIZE - 3 - y1)
    return dict_to_img({(x + mx, y + my): c for (x, y), c in pts.items()})

def rot_about(src, deg, pivot, move=(0, 0), roundh=1):
    pts = rotate_points(src, deg, pivot)
    fill_holes(pts, roundh)
    if move != (0, 0):
        pts = {(x + move[0], y + move[1]): c for (x, y), c in pts.items()}
    return dict_to_img(pts)

def punch(im, blocks):
    """在图层自身挖洞（fill=0 即擦除），用于消散"""
    d = ImageDraw.Draw(im)
    for (x0, y0, x1, y1) in blocks:
        d.rectangle((x0, y0, x1, y1), fill=0)
    return im

def dissolve_blocks(level, seed=7):
    """确定性伪随机挖洞位置 —— 同一 seed 每次结果一致"""
    out = []
    x = seed
    n = int(26 * level)
    for i in range(n):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        bx = (x >> 7) % (SIZE - 6) + 3
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        by = (x >> 7) % (SIZE - 6) + 3
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        s = 1 + (x >> 9) % 3
        out.append((bx, by, bx + s, by + s))
    return out

# ---------------------------------------------------------------- 新增造型能力
def draw_head_ex(d, dy=0, mode='normal'):
    """头部：mode = normal 睁眼 / blink 闭眼 / dead X眼 / glow 发光瞳"""
    y = dy
    G.draw_head(d, dy, blink=(mode == 'blink'))
    if mode == 'dead':                                   # 盖 X 眼 + 张口
        for cx in (27, 33):
            line(d, [(cx - 1, 19 + y), (cx + 2, 22 + y)], 1, 1)
            line(d, [(cx + 2, 19 + y), (cx - 1, 22 + y)], 1, 1)
        r(d, (29, 24 + y, 32, 26 + y), 1)
    elif mode == 'glow':                                 # 二段变身瞳：白瞳青边（与原瞳同尺寸）
        for cx in (27, 33):
            r(d, (cx, 20 + y, cx + 1, 21 + y), C_WHITE)
            line(d, [(cx - 1, 20 + y), (cx - 1, 21 + y)], C_CYAN, 1)
            line(d, [(cx + 2, 20 + y), (cx + 2, 21 + y)], C_CYAN, 1)

def draw_legs_kneel(d, dy=0, lean=0):
    """新增腿部枚举 5 = 单膝跪地：后腿着膝，前腿踩地，重心下沉"""
    y, x = dy, lean
    def knee(lx, ly):
        r(d, (lx, ly, lx + 4, ly + 3), C_BLUE, C_OUT)
    line(d, [(29 + x, 41 + y), (23 + x, 50 + y)], C_SOCKS, 3)   # 后腿大腿
    line(d, [(23 + x, 50 + y), (22 + x, 55 + y)], C_SOCKS, 3)   # 小腿
    knee(19 + x, 55 + y)                                        # 膝盖着地
    line(d, [(35 + x, 41 + y), (39 + x, 50 + y)], C_SOCKS, 3)   # 前腿大腿
    line(d, [(39 + x, 50 + y), (40 + x, 54 + y)], C_SOCKS, 3)
    knee(38 + x, 54 + y)

def draw_legs_ex(d, dy=0, lean=0, pose=0):
    if pose == 5:
        draw_legs_kneel(d, dy, lean)
    else:
        G.draw_legs(d, dy, lean, pose)

def draw_wings(d, dy=0, s=1.0):
    """大招光翼：从背后的肩部向右上展开，s 控制展开程度（0.45 初展 ~ 1.0 全展）"""
    bx, by = 36, 30 + dy
    def P(dx1, dy1):
        return (bx + round(dx1 * s), by + round(dy1 * s))
    d.polygon([P(0, 2), P(21, -19), P(17, -7), P(9, -2)], fill=C_WHITE, outline=C_OUT)
    d.polygon([P(2, 0), P(17, -14), P(12, -4)], fill=C_LBLUE)
    d.polygon([P(18, -17), P(23, -21), P(16, -11)], fill=C_CYAN)
    line(d, [P(1, 1), P(19, -16)], C_OUT, 1)
    line(d, [P(3, 1), P(15, -8)], C_OUT, 1)
    line(d, [P(6, 0), P(20, -11)], C_OUT, 1)

# --------------------------------------------------------------------- 特效层
def fx_impact(d, dy=0, cx=29, cy=30):
    """受击爆点：红色四芒星 + 金十字 + 白芯"""
    cy += dy
    line(d, [(cx - 6, cy), (cx + 6, cy)], C_RED, 1)
    line(d, [(cx, cy - 6), (cx, cy + 6)], C_RED, 1)
    line(d, [(cx - 4, cy - 4), (cx + 4, cy + 4)], C_GOLD, 1)
    line(d, [(cx - 4, cy + 4), (cx + 4, cy - 4)], C_GOLD, 1)
    r(d, (cx - 1, cy - 1, cx + 1, cy + 1), C_WHITE)
    for px_, py_ in ((cx + 8, cy - 5), (cx - 9, cy + 4), (cx + 6, cy + 7), (cx - 7, cy - 7)):
        r(d, (px_, py_, px_ + 1, py_ + 1), C_RED)

def fx_dust_at(d, x, y, dy=0):
    """尘团：任意落点<｜hy_place▁holder▁no▁813｜>气"""
    y += dy
    ell(d, (x, y, x + 6, y + 4), C_WHITE, C_OUT)
    ell(d, (x + 5, y + 1, x + 11, y + 5), C_RESID)
    ell(d, (x - 5, y + 2, x, y + 6), C_RESID)
    line(d, [(x + 2, y - 2), (x + 2, y - 2)], C_WHITE, 1)

def fx_soul(d, dy=0, n=9):
    """消散：向上升腾的灵魂光点"""
    spec = [(33, 42), (26, 35), (40, 33), (22, 27), (35, 23), (29, 17),
            (43, 18), (32, 11), (25, 9)]
    for i, (x, y) in enumerate(spec[:n]):
        c = C_WHITE if i % 2 == 0 else C_CYAN
        r(d, (x, y + dy, x + 1, y + 1 + dy), c)
        if i % 3 == 0:
            line(d, [(x - 2, y + dy), (x + 3, y + dy)], C_GOLD, 1)

def fx_aura(d, box, dy=0):
    """聚能气环：越大=能量越散，越小=压缩到身周"""
    x0, y0, x1, y1 = box
    y0 += dy
    y1 += dy
    ell(d, (x0, y0, x1, y1), None, outline=C_CYAN)
    ell(d, (x0 + 2, y0 + 2, x1 - 2, y1 - 2), None, outline=C_LBLUE)

def fx_rise(d, dy=0, n=6):
    """上升能量柱 / 气流短线"""
    spec = [(10, 50), (14, 46), (45, 50), (49, 45), (20, 54), (40, 55)]
    for i, (x, y) in enumerate(spec[:n]):
        line(d, [(x, y + dy), (x, y - 5 + dy)], C_CYAN, 1)
        r(d, (x - 1, y - 8 + dy, x + 1, y - 7 + dy), C_WHITE)

def fx_burst(d, dy=0, sweep=True):
    """爆发冲击波：外围大环 + 横向气掠"""
    ell(d, (2, 12 + dy, 61, 60 + dy), None, outline=C_CYAN)
    ell(d, (6, 16 + dy, 57, 56 + dy), None, outline=C_WHITE)
    if sweep:
        line(d, [(2, 44 + dy), (61, 44 + dy)], C_RESID, 1)
        line(d, [(2, 47 + dy), (52, 47 + dy)], C_LBLUE, 1)

def fx_beam(d, y=31, tail=True, strong=True):
    """大招光矛：横向贯穿的巨型光束"""
    w, h = (3, 5) if strong else (1, 3)
    line(d, [(14, y), (61, y)], C_WHITE, w)
    line(d, [(14, y - 3), (61, y - 3)], C_CYAN, 1)
    line(d, [(14, y + 3), (61, y + 3)], C_CYAN, 1)
    if strong:
        line(d, [(14, y - h), (61, y - h)], C_LBLUE, 1)
        line(d, [(14, y + h), (61, y + h)], C_LBLUE, 1)
    # 左端矛头
    d.polygon([(2, y), (16, y - 7), (16, y + 7)], fill=C_WHITE, outline=C_OUT)
    d.polygon([(7, y), (16, y - 4), (16, y + 4)], fill=C_CYAN)
    if tail:
        for yy in (y - 9, y + 9):
            line(d, [(18, yy), (58, yy)], C_RESID, 1)

def fx_streak(d, dy=0, n=5):
    """射击余波：横向残影线"""
    spec = [(20, 24), (26, 38), (34, 20), (40, 44), (48, 28)]
    for i, (x, y) in enumerate(spec[:n]):
        c = C_RESID if i % 2 else C_CYAN
        line(d, [(x, y + dy), (x + 14, y + dy)], c, 1)

def fx_spark(d, dy=0, n=5):
    """小火花 / 收势余光"""
    spec = [(12, 24), (20, 18), (46, 22), (52, 32), (30, 12)]
    for i, (x, y) in enumerate(spec[:n]):
        c = C_WHITE if i % 2 == 0 else C_CYAN
        r(d, (x, y + dy, x + 1, y + 1 + dy), c)

def fx_arrowrain(d, dy=0, n=5):
    """光箭雨：空中成排的小型青光箭"""
    spec = [(6, 8), (16, 4), (30, 6), (44, 3), (54, 9)]
    for i, (x, y) in enumerate(spec[:n]):
        line(d, [(x, y + dy), (x + 7, y + 7 + dy)], C_GOLD, 1)
        d.polygon([(x + 7, y + 7 + dy), (x + 2, y + 5 + dy), (x + 5, y + 2 + dy)],
                  fill=C_CYAN, outline=C_OUT)

# ------------------------------------------------------------ 帧构造器（参数化）
def mk_frame(fid, dy=0, lean=0, legs=0, hair=0, hand=None, draw_px=None,
             arrow=None, bow_deg=0, bow_move=(0, 0), head='normal',
             wings=0, fx_fn=None, fx_back_fn=None):
    """标准站姿帧：沿用原角色的关键锚点，只做相对偏移。
    fx_back_fn: 画在角色身后的环境特效（气环/冲击波），避免遮脸"""
    grip = (GRIP[0] + lean, GRIP[1])

    def back(d):
        G.draw_hair_back(d, hair, dy)
        if wings:
            draw_wings(d, dy, wings)

    def body(d):
        G.draw_body(d, dy, lean)
        draw_head_ex(d, dy, head)
        G.draw_arm_bow(d, dy, lean, grip)
        G.draw_arm_string(d, dy, lean, hand)
        draw_legs_ex(d, dy, lean, legs)

    bow = _L(lambda d: G.draw_bow(d, dy, draw_px, arrow, hand))
    if bow_deg or bow_move != (0, 0):
        bow = rot_about(bow, bow_deg, (GRIP[0], GRIP[1] + dy), bow_move)

    layers = []
    if fx_back_fn:
        layers.append(('backfx', _L(fx_back_fn)))
    layers += [
        ('hair', _L(back)),
        ('body', _L(body)),
        ('bow', bow),
        ('fx', _L(fx_fn or _noop)),
    ]
    return {'id': fid, 'layers': layers}

def mk_frame_fall(fid, deg, bottom=None, left=None, dy=0, lean=0, legs=0,
                  hair=2, hand=None, draw_px=None, bow_in_hand=True, bow_deg=0,
                  fx_fn=None, dissolve=0.0, seed=7):
    """倒地帧：先按站姿完整画出角色（X 眼），再整体旋转落地。
    bow_deg: 弓相对身体的额外转角（让弓斜倚在身侧而不是横在头顶）"""
    grip = (GRIP[0] + lean, GRIP[1])
    hair_im = _L(lambda d: G.draw_hair_back(d, hair, dy))
    body_im = _L(lambda d: (G.draw_body(d, dy, lean),
                            draw_head_ex(d, dy, 'dead'),
                            G.draw_arm_bow(d, dy, lean, grip),
                            G.draw_arm_string(d, dy, lean, hand),
                            draw_legs_ex(d, dy, lean, legs)))
    parts = [hair_im, body_im]
    if bow_in_hand:
        def _bow(d):
            G.draw_bow(d, dy, draw_px, None, hand)
        bow_im = _L(_bow) if not bow_deg else rot_about(_L(_bow), bow_deg, (GRIP[0], GRIP[1] + dy))
        parts.append(bow_im)
    src = merge(parts)
    img = rot_fit(src, deg, pivot=(32, 31), bottom=bottom, left=left)
    if dissolve:
        punch(img, dissolve_blocks(dissolve, seed))
    return {'id': fid, 'layers': [
        ('body', img),
        ('fx', _L(fx_fn or _noop)),
    ]}

# ------------------------------------------------------------------- 动作参数表
def build_death():
    """死亡 6 帧：受击 → 踉跄 → 跪地 → 倾倒 → 躺地 → 消散"""
    f = []
    # 0 受击后仰：重心拔高、弓随身体后仰、胸口爆点
    f.append(mk_frame('death_0', dy=-1, lean=-3, legs=2, hair=3,
                      draw_px=18, hand=(20, 32), bow_deg=-14,
                      head='dead',
                      fx_fn=lambda d: (fx_impact(d, 0), fx_dust_at(d, 46, 52, dy=0))))
    # 1 踉跄：大跨步后退，弓被带得向后下坠
    f.append(mk_frame('death_1', dy=2, lean=-2, legs=4, hair=2, bow_deg=-22,
                      head='dead',
                      fx_fn=lambda d: (fx_dust_at(d, 44, 53, dy=0),
                                       fx_spark(d, 0, 3))))
    # 2 单膝跪：重心压到最低，后撑手扶地，弓几乎贴地
    f.append(mk_frame('death_2', dy=7, lean=2, legs=5, hair=3, hand=(41, 49),
                      bow_deg=52, bow_move=(-1, 2), head='dead',
                      fx_fn=lambda d: fx_dust_at(d, 24, 54, dy=0)))
    # 3 倾倒中：整体旋转 42 度砸向地面
    f.append(mk_frame_fall('death_3', deg=42, bottom=58, left=None,
                           legs=2, hair=3, hand=(38, 46),
                           fx_fn=lambda d: fx_dust_at(d, 22, 52, dy=0)))
    # 4 躺地：完全倒下，仰面 X 眼，弓斜倚身侧，尘土扬起
    f.append(mk_frame_fall('death_4', deg=90, bottom=57, bow_deg=-55,
                           legs=2, hair=3, hand=(36, 40),
                           fx_fn=lambda d: (fx_dust_at(d, 8, 52, dy=0),
                                            fx_dust_at(d, 44, 53, dy=0))))
    # 5 消散：躯体被挖去一部分，灵魂光点上升
    f.append(mk_frame_fall('death_5', deg=90, bottom=57, bow_deg=-55, legs=2, hair=3,
                           hand=(36, 40), dissolve=0.85, seed=19,
                           fx_fn=lambda d: fx_soul(d, 0, 9)))
    return f

def build_ultimate():
    """大招 8 帧：蓄势 → 满弦 → 聚能 → 腾空 → 放矛 → 余波 → 回落 → 收势"""
    f = []
    # 0 起手：搭箭上弦，脚下微光
    f.append(mk_frame('ult_0', dy=0, legs=2, hair=-1, draw_px=20, hand=(20, 32),
                      arrow='nock', head='normal',
                      fx_back_fn=lambda d: fx_aura(d, (8, 10, 56, 58), 0),
                      fx_fn=lambda d: fx_spark(d, 0, 3)))
    # 1 满弦上举：拉到极限，气环收紧
    f.append(mk_frame('ult_1', dy=-1, lean=1, legs=1, hair=-2, draw_px=26,
                      hand=(26, 32), arrow='nock', bow_deg=-16, head='glow',
                      fx_back_fn=lambda d: fx_aura(d, (12, 14, 52, 54), 0),
                      fx_fn=lambda d: fx_rise(d, 0, 4)))
    # 2 蹲身聚能：把能量压进弓身，光翼初展
    f.append(mk_frame('ult_2', dy=4, lean=1, legs=3, hair=-3, draw_px=26,
                      hand=(26, 34), arrow='nock', bow_deg=-22, head='glow',
                      wings=0.5,
                      fx_back_fn=lambda d: fx_aura(d, (16, 18, 48, 52), 0),
                      fx_fn=lambda d: fx_rise(d, 0, 6)))
    # 3 腾空展翼：跃起 + 光翼全展 + 冲击波（爆点帧）
    f.append(mk_frame('ult_3', dy=-7, lean=1, legs=3, hair=-3, draw_px=26,
                      hand=(25, 26), arrow='nock', bow_deg=-30, head='glow',
                      wings=1.0,
                      fx_back_fn=lambda d: fx_burst(d, 0),
                      fx_fn=lambda d: fx_rise(d, 0, 6)))
    # 4 光矛成形：脱手瞬间，巨型光束贯穿画面（弓把高度，不遮脸）
    f.append(mk_frame('ult_4', dy=-1, lean=2, legs=1, hair=-2, arrow='fly',
                      hand=(24, 31), bow_deg=-24, head='glow', wings=0.9,
                      fx_fn=lambda d: fx_beam(d, y=33, tail=True, strong=True)))
    # 5 余波：光束衰减 + 光箭雨 + 残影
    f.append(mk_frame('ult_5', dy=0, lean=2, legs=2, hair=1, arrow='fly',
                      hand=(25, 32), bow_deg=-16, head='normal', wings=0.6,
                      fx_fn=lambda d: (fx_beam(d, y=34, tail=True, strong=False),
                                       fx_streak(d, 0, 5), fx_arrowrain(d, 0, 4))))
    # 6 回落：收翼下沉
    f.append(mk_frame('ult_6', dy=1, lean=1, legs=3, hair=3, draw_px=None,
                      hand=None, bow_deg=-6, head='normal', wings=0.35,
                      fx_fn=lambda d: (fx_spark(d, 0, 5), fx_streak(d, 0, 3))))
    # 7 收势：落回地面，闭目，残光散尽
    f.append(mk_frame('ult_7', dy=0, legs=0, hair=1, hand=None, head='blink',
                      fx_fn=lambda d: fx_spark(d, 0, 3)))
    return f

# ------------------------------------------------------------------- 渲染 + 导出
def render(layers):
    """多图层合成为 RGBA 成品帧"""
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for _, im in layers:
        sp = im.load()
        for y in range(SIZE):
            for x in range(SIZE):
                c = sp[x, y]
                if c:
                    px[x, y] = PALETTE[c]
    return out

def export(out_dir, frames, title):
    OUT = Path(out_dir)
    if OUT.exists():
        raise SystemExit('输出目录已存在，换一个新名字：%s' % OUT)
    (OUT / 'frames').mkdir(parents=True)
    imgs, meta = [], []
    for i, fr in enumerate(frames):
        im = render(fr['layers'])
        fid = fr['id']
        p = OUT / 'frames' / ('%s.png' % fid)
        im.save(p)
        imgs.append((fid, im))
        meta.append({'id': fid, 'action': fid.rsplit('_', 1)[0], 'order': i,
                     'file': 'frames/%s.png' % fid,
                     'rect': [i * SIZE, 0, SIZE, SIZE],
                     'rgba_sha256': hashlib.sha256(im.tobytes()).hexdigest()})
    n = len(imgs)
    sheet = Image.new('RGBA', (n * SIZE, SIZE), (0, 0, 0, 0))
    for i, (_, im) in enumerate(imgs):
        sheet.paste(im, (i * SIZE, 0))
    sheet.save(OUT / 'sprite-sheet.png')
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.Resampling.NEAREST).save(
        OUT / 'contact-sheet-8x.png')
    (OUT / 'atlas.json').write_text(json.dumps(
        {'title': title, 'size': [n * SIZE, SIZE], 'frame_size': SIZE,
         'palette_size': len(PALETTE), 'frames': meta},
        ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'palette.json').write_text(json.dumps(PALETTE, ensure_ascii=False), encoding='utf-8')
    hs = [m['rgba_sha256'] for m in meta]
    if len(set(hs)) != len(hs):
        dup = [m['id'] for m in meta if hs.count(m['rgba_sha256']) > 1]
        raise SystemExit('姿态重复，每帧必须有真实差异：%s' % dup)
    # manifest 校验 PNG 文件本身的字节 + 强制 LF 行尾，
    # 这样 sha256sum -c manifest.sha256 可直接复核（Windows 下 write_text 会转成 CRLF 导致校验失败）
    lines = []
    for m in meta:
        sha = hashlib.sha256((OUT / m['file']).read_bytes()).hexdigest()
        lines.append('%s  %s' % (sha, m['file']))
    with open(OUT / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    _write_project_json(OUT, frames, title)
    print('OK -> %s  帧数=%d  画布=%d  颜色数=%d  帧间差异校验=PASS' % (OUT, n, SIZE, len(PALETTE)))
    for m in meta:
        print('   ', m['id'], m['rgba_sha256'][:12])
    return hs

def _write_project_json(OUT, frames, title):
    """保留可编辑工程（与原 delivery 包同 schema），方便后续精确改某一帧"""
    order = ['backfx', 'hair', 'body', 'bow', 'fx']
    pframes = []
    for fr in frames:
        lays = dict(fr['layers'])
        pframes.append({
            'id': fr['id'], 'pose': fr['id'],
            'layers': {k: [list(lays[k].getdata())[i * SIZE:(i + 1) * SIZE] for i in range(SIZE)]
                       for k in order if k in lays}})
    proj = {'schema': 'pixel-project/1', 'project_id': OUT.name, 'title': title,
            'description': title, 'size': SIZE, 'revision': 3,
            'palette': [list(c) for c in PALETTE],
            'layer_order': [k for k in order], 'frames': pframes}
    (OUT / 'project.json').write_text(json.dumps(proj, ensure_ascii=False) + '\n', encoding='utf-8')

if __name__ == '__main__':
    which = sys.argv[2] if len(sys.argv) > 2 else 'all'
    if which in ('death', 'all'):
        export(sys.argv[1] + '/v3-death' if which == 'all' else sys.argv[1],
               build_death(), '原创像素弓箭手·云纹游侠 —— 死亡动画 6 帧')
    if which in ('ultimate', 'all'):
        export(sys.argv[1] + '/v3-ultimate' if which == 'all' else sys.argv[1],
               build_ultimate(), '原创像素弓箭手·云纹游侠 —— 大招动画 8 帧')
