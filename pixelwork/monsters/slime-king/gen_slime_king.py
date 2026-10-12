# -*- coding: utf-8 -*-
"""
史莱姆王（King Slime）BOSS 怪物帧动画生成器 —— 32x32 像素画，纯 Pillow 程序化点阵绘制。

造型：比普通史莱姆大两号的深绿果冻体（底宽约 26px、体高约 16px，坐在 FOOT_Y=27 接地线上），
      头顶锯齿金冠+红宝石、右肩深紫披风（back 层摆动）、加粗左伪足；面朝左。
      6 动作 22 帧拆 3 个包（BOSS 对小怪「4 动作 2 包」配额的显式扩展，见 DESIGN.md §7）。

用法（第二个参数选包，缺省三个包都生成）：
  PY="C:/Users/PC-7020/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
  "$PY" gen_slime_king.py <父目录> locomotion    -> <父目录>/slime-king-move-hit
  "$PY" gen_slime_king.py <父目录> combat        -> <父目录>/slime-king-attack-death
  "$PY" gen_slime_king.py <父目录> special       -> <父目录>/slime-king-roar-summon
  "$PY" gen_slime_king.py <父目录> locomotion -r2 -> 迭代版落到 slime-king-move-hit-r2（绝不覆盖旧包）

约定遵循 pixelwork/monsters/CONTRACT.md + slime-king/DESIGN.md：
  SIZE=32 固定；16 色有限调色板（索引 0 透明、索引 1 描边）；fill 一律传索引；
  锚点常量写死（CX/TOP_Y/BASE_Y/FOOT_Y/HALF_W），姿态只做相对偏移；
  每帧有真实差异；统一面朝左；每包 <=8 帧；输出目录必须不存在。
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

# ---------------- 1. 配置 ----------------
SIZE = 32
NAME = 'slime-king'
BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
PACKS = {'locomotion': ['move', 'hit'], 'combat': ['attack', 'death'],
         'special': ['roar', 'summon']}
PACK_SUFFIX = {'locomotion': 'move-hit', 'combat': 'attack-death',
               'special': 'roar-summon'}
PACK = sys.argv[2] if len(sys.argv) > 2 else None
REV = sys.argv[3] if len(sys.argv) > 3 else ''      # 迭代后缀，如 -r2

PALETTE = [                             # 索引 -> RGBA（16 色，<=16）
    (0, 0, 0, 0),           # 0  透明
    (34, 30, 44, 255),      # 1  描边深色
    (45, 132, 70, 255),     # 2  主体绿主色 #2D8446
    (98, 198, 112, 255),    # 3  主体绿亮部 #62C670
    (28, 92, 50, 255),      # 4  主体绿暗部 #1C5C32
    (240, 245, 238, 255),   # 5  白（白泽光/眼高光/宝石高光/闪白/特效核心）
    (18, 74, 42, 255),      # 6  深绿内核 #124A2A
    (150, 52, 58, 255),     # 7  受击暗红（tint 描边染色）
    (226, 74, 74, 255),     # 8  受击红 ∩ 红宝石
    (168, 235, 150, 255),   # 9  淡绿（水渍/水滴/小史莱姆）
    (255, 224, 102, 255),   # 10 金黄（金冠亮部 ∩ 特效黄 ∩ 宝石闪光）
    (222, 168, 52, 255),    # 11 金冠主色
    (22, 28, 30, 255),      # 12 眼睛深色/口腔
    (94, 58, 138, 255),     # 13 披风主色（深紫）
    (56, 34, 86, 255),      # 14 披风暗部
    (92, 60, 64, 255),      # 15 受击暗部红
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']      # 自下而上合成

# ---- 锚点常量（写死，姿态只做相对偏移，绝不逐帧重算绝对坐标）----
CX = 15          # 身体水平中心（比小怪左移 1px，给右侧披风让位）
TOP_Y = 12       # 中立姿态头顶 y（皇冠再高 4px，冠顶 y=8）
BASE_Y = 27      # 中立姿态平底（接地面）y
FOOT_Y = 27      # 接地线（与小怪一致，overview 拼图按此对齐）
HALF_W = 13      # 中立姿态半宽（底宽 2*HALF_W = 26px）
DOME_H = BASE_Y - TOP_Y + 1         # 16 行（中立体高）
EYE = 4          # 眼边长（目检显大可一行改回 3）


# ---------------- 2. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)


def setpx(im, x, y, c):
    """索引 0 视为透明，不落笔。传的是调色板索引，绝不是 RGB。"""
    if 0 <= x < SIZE and 0 <= y < SIZE and c:
        im.putpixel((x, y), c)


def hline(im, x0, x1, y, c):
    for x in range(x0, x1 + 1):
        setpx(im, x, y, c)


# ---------------- 3. 形体（几何 + 蒙版）----------------
def body_shape(p):
    """返回 (行数 h, 半宽 hw)。squash>0 压扁变宽，<0 拉长变窄。"""
    sq = p['squash']
    h = DOME_H - sq
    hw = HALF_W + int(round(sq * 0.6))
    return max(5, min(h, 20)), max(5, min(hw, 14))


def body_mask(p):
    """半圆顶 + 平底；wobble 让上半部左右甩动（果冻抖动），底部不动。"""
    h, hw = body_shape(p)
    cx = CX + p['lean']
    base = BASE_Y + p['dy']
    wob = p['wobble']
    m = {}
    for row in range(h):
        y = base - row
        if not (0 <= y < SIZE):
            continue
        t = row / (h - 1) if h > 1 else 0.0
        wi = int(round(hw * (1.0 - t * t) ** 0.5))
        if row >= h - 2:
            wi = max(wi, 2)
        wi = max(wi, 1)
        shift = int(round(wob * (row / max(1, h - 1))))
        for x in range(cx - wi + shift, cx + wi + shift):   # 宽 = 2*wi
            if 0 <= x < SIZE:
                m[(x, y)] = True
    return m


def outline_of(mask):
    """4 邻域边界像素 = 描边环。"""
    ring = set()
    for (x, y) in mask:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in mask:
                ring.add((x, y))
                break
    return ring


def pseudo_cols(p):
    """伪足按列生成（根藏在体内、尖端向左），返回 {x: (yc, hh, frac)}。

    BOSS 伪足比小怪粗：hh 系数 3.0 -> 3.5；根部只埋进身体 inset 像素。
    """
    cx = CX + p['lean']
    reach = p['reach']
    if reach <= 0:
        return {}
    _, hw = body_shape(p)
    y0 = BASE_Y + p['dy'] - 3                 # 伪足中轴（低于眼睛，避免遮脸）
    inset = max(2, hw // 3)
    x_root = cx - hw + inset                  # 根部藏进身体
    x_tip = cx - hw - reach                   # 尖端伸出体左缘 reach 像素
    span = max(1, x_root - x_tip)
    cols = {}
    for x in range(x_tip, x_root + 1):
        frac = (x_root - x) / span            # 0=根 1=尖
        hh = max(1, int(round(3.5 * (1 - frac) ** 0.5)))
        yc = y0 + int(round(frac * 1.2))      # 尖端略下垂
        cols[x] = (yc, hh, frac)
    return cols


def pseudo_mask(p):
    m = {}
    for x, (yc, hh, _) in pseudo_cols(p).items():
        if not (0 <= x < SIZE):
            continue
        for k in range(-hh, hh + 1):
            if 0 <= yc + k < SIZE:
                m[(x, yc + k)] = True
    return m


def pseudo_tip(p):
    cols = pseudo_cols(p)
    if not cols:
        return None
    x = min(cols)
    return x, cols[x][0]


def crown_rect(p):
    """皇冠 8x4 左上角 (x0, y0)：x0 随 lean 平移；y0 锚定头顶固定 4px 偏移，
    绝不按比例缩放——压扁帧里皇冠只是随头顶下降，不会陷进眼睛。"""
    h, _ = body_shape(p)
    cx = CX + p['lean']
    base = BASE_Y + p['dy']
    top = base - h + 1
    return cx - 4, top - 4


# ---------------- 4. 四层绘制 ----------------
def draw_cloak(im, p, c):
    """披风（back 层）：右肩下垂 4px 宽；肩部钉住、下摆 shift=round(swing*frac)。
    swing>0 向右后扬（腾空/前冲），swing<0 向左前甩或贴背收拢（宽帧/后仰帧）。"""
    if p['puddle']:
        return
    h, hw = body_shape(p)
    cx = CX + p['lean']
    base = BASE_Y + p['dy']
    top = base - h + 1
    y0, y1 = top + 2, base - 2
    if y1 <= y0:
        return
    for y in range(y0, y1 + 1):
        frac = (y - y0) / (y1 - y0)
        shift = int(round(p['swing'] * frac))
        x1 = cx + hw + shift                  # 右缘（出界由界断言兜底）
        x0 = x1 - 3
        for x in range(x0, x1 + 1):
            setpx(im, x, y, c(14) if (x == x1 or y == y1) else c(13))


def draw_back(im, p, c):
    """back：底部接地阴影（腾空时收窄，凸显弹跳）+ 深紫披风。"""
    cx = CX + p['lean']
    lift = max(0, -p['dy'])
    sw = HALF_W + int(round(p['squash'] * 0.5)) - int(round(lift * 1.0))
    sw = max(3, min(13, sw))
    y = BASE_Y + 1
    hline(im, cx - sw, cx + sw, y, 1)
    hline(im, cx - sw + 3, cx + sw - 3, y + 1, 1)
    draw_cloak(im, p, c)


def draw_crown(im, p, c):
    """皇冠（body 层）：8x4 三齿（齿宽 2px）+ 冠带正中红宝石 3x2 + 左上白高光。

    小齿禁用 outline_of 自动描边（2px 齿宽会被整齿吃成黑块），改手工双色：
    齿顶行/冠带顶行用 10 亮金，其余 11 主金；冠与 Dome 相接处由 Dome 自身描边环分隔。
    """
    x0, y0 = crown_rect(p)
    for tx in (0, 3, 6):                      # 三齿起始列
        for col in range(2):
            setpx(im, x0 + tx + col, y0, c(10))      # 齿顶行
            setpx(im, x0 + tx + col, y0 + 1, c(11))  # 齿体行
    for col in range(8):                      # 冠带两行
        setpx(im, x0 + col, y0 + 2, c(10))
        setpx(im, x0 + col, y0 + 3, c(11))
    for gx in range(3):                       # 红宝石嵌冠带正中
        for gy in range(2):
            setpx(im, x0 + 2 + gx, y0 + 2 + gy, c(8))
    setpx(im, x0 + 2, y0 + 2, c(5))           # 宝石左上高光


def draw_mouth(im, p, c, eye_y, m, ring):
    """嘴（body 层）：眼下方 5px 宽。open=5x2 口腔深色，wide=5x3；两角 1px 白牙。"""
    cx = CX + p['lean']
    my = eye_y + 5
    rows = 3 if p['mouth'] == 'wide' else 2

    def put(mx, myy, col):
        if (mx, myy) in m and (mx, myy) not in ring:
            setpx(im, mx, myy, c(col))

    for gy in range(rows):
        for gx in range(-2, 3):
            put(cx + gx, my + gy, 12)
    put(cx - 2, my, 5)                        # 左白牙
    put(cx + 2, my, 5)                        # 右白牙


def draw_puddle(im, p, c):
    """death 末帧：只剩一滩浅色水渍 + 少量残留深色小点。"""
    cx = CX + p['lean']
    y0 = BASE_Y
    hline(im, cx - 12, cx + 11, y0, c(9))
    hline(im, cx - 8, cx + 8, y0 - 1, c(9))
    hline(im, cx - 4, cx + 4, y0 - 2, c(3))
    hline(im, cx - 2, cx + 2, y0 - 3, c(3))
    setpx(im, cx - 5, y0 - 1, c(5))
    setpx(im, cx + 4, y0 - 1, c(5))
    setpx(im, cx + 1, y0 - 2, c(5))
    for x in (cx - 9, cx + 7, cx + 10, cx - 11):
        setpx(im, x, y0, c(1))                # 残留深色碎屑


def draw_wreckage(im, p, c):
    """death 末帧：皇冠残骸立在水渍右侧尽头（22..29, 24..27）——王者仅剩的尊严，
    画在水渍之上，与飘散粒子错开。"""
    x0, y0 = 22, 24
    for tx in (0, 3, 6):
        for col in range(2):
            setpx(im, x0 + tx + col, y0, c(10))
            setpx(im, x0 + tx + col, y0 + 1, c(11))
    for col in range(8):
        setpx(im, x0 + col, y0 + 2, c(10))
        setpx(im, x0 + col, y0 + 3, c(11))
    for gx in range(3):
        for gy in range(2):
            setpx(im, x0 + 2 + gx, y0 + 2 + gy, c(8))
    setpx(im, x0 + 2, y0 + 2, c(5))


def draw_body(im, p, c):
    """body：果冻主体 + 白泽光 + 梯度 + 皇冠宝石 + 内核 + 嘴 + 眼睛。"""
    if p['puddle']:
        draw_puddle(im, p, c)
        draw_wreckage(im, p, c)
        return
    m = body_mask(p)
    if not m:
        return
    ring = outline_of(m)
    h, hw = body_shape(p)
    cx = CX + p['lean']
    base = BASE_Y + p['dy']
    top = base - h + 1

    # 左上白泽光：锚定头顶（不按比例），保证压扁帧里也只是小块反光
    gloss = set()
    for gy in (top + 1, top + 2):
        for gx in (cx - 5, cx - 4, cx - 3):
            if (gx, gy) in m and (gx, gy) not in ring:
                gloss.add((gx, gy))

    for (x, y) in m:                          # 先整块铺描边色
        setpx(im, x, y, c(1))
    for (x, y) in m:                          # 再上内部梯度（边界自动留描边）
        if (x, y) in ring:
            continue
        row = base - y
        vf = row / max(1, h - 1)              # 0 底 .. 1 顶
        u = (x - (cx - 0.5)) / hw             # -1 左 .. 1 右
        col = 2
        if vf > 0.58:                         # 顶部弧形高光带
            col = 3
        if vf < 0.16:                         # 底部接地暗部
            col = 4
        elif vf < 0.32 and u > 0.05:
            col = 4
        if 0.28 < vf < 0.58 and u > 0.50:     # 右下侧厚度
            col = 4
        if (x, y) in gloss:
            col = 5
        setpx(im, x, y, c(col))

    draw_crown(im, p, c)                      # 皇冠+宝石（锚定头顶，画在 Dome 之上）

    eye_y = top + max(3, int(round(h * 0.36))) + p['eyeoff']
    ex_l, ex_r = cx - 7, cx - 2               # EYE=4：整体偏左 => 面朝左

    def eye(mx, my, col):
        if (mx, my) in m and (mx, my) not in ring:
            setpx(im, mx, my, c(col))

    # 体内深绿内核（偏右下、挂在眼睛下方）。张嘴时不画，让位给嘴型。
    # 核本体落在暗部里，必须整圈包边才立得住：左上亮边 (3) + 右下暗边 (1)。
    if p['mouth'] == 'none' and h >= 9 and eye_y + 5 <= base - 2:
        cy = eye_y + 5
        core = set()
        for y in range(cy - 3, cy + 4):
            for x in range(cx - 1, cx + 6):
                nx = (x - (cx + 2)) / 2.2
                ny = (y - cy) / 2.2
                if nx * nx + ny * ny <= 1.0:
                    core.add((x, y))
        for (x, y) in core:
            for (dx, dy) in ((0, -1), (-1, 0), (0, 1), (1, 0)):
                q = (x + dx, y + dy)
                if q not in core:
                    eye(q[0], q[1], 3 if (dx <= 0 and dy <= 0) else 1)
        for (x, y) in core:
            eye(x, y, 6)

    if p['mouth'] != 'none':
        draw_mouth(im, p, c, eye_y, m, ring)

    # 眼睛（<=4px 小部件，绝不 outline，用深色 + 白色高光点）
    mode = p['eyes']
    if mode == 'open':
        for ex in (ex_l, ex_r):
            for k in range(EYE):
                for j in range(EYE):
                    eye(ex + j, eye_y + k, 12)
            eye(ex, eye_y, 5)                 # 眼高光
    elif mode == 'line':                      # 闪白帧：眼睛变横线
        for ex in (ex_l, ex_r):
            for j in range(EYE):
                eye(ex + j, eye_y + 1, 12)
    elif mode == 'closed':
        for ex in (ex_l, ex_r):
            for j in range(EYE):
                eye(ex + j, eye_y, 12)
    elif mode == 'x':                         # 受击/死亡：X 眼（双对角线）
        for ex in (ex_l, ex_r):
            for j in range(EYE):
                eye(ex + j, eye_y + j, 12)
                eye(ex + EYE - 1 - j, eye_y + j, 12)


def draw_mini(im, p, c):
    """小史莱姆（weapon 层，summon 专属）：5x4 圆角淡绿本体 + 深色描边 + 单眼。
    mouth=嘴左下（身前）；land=左下角地面（压扁成 5x3，贴体缘=「身前件」语义）。"""
    cx = CX + p['lean']
    if p['spawn'] == 'mouth':
        h, _ = body_shape(p)
        base = BASE_Y + p['dy']
        top = base - h + 1
        eye_y = top + max(3, int(round(h * 0.36)))
        x0, y0, hh = cx - 10, eye_y + 7, 4
    else:                                     # land
        x0, y0, hh = max(1, cx - 15), FOOT_Y - 2, 3
    m = set()
    for row in range(hh):
        inset = 1 if (row == 0 or row == hh - 1) else 0
        for col in range(5):
            if inset and col in (0, 4):
                continue                      # 圆角：上下行各收 1px
            m.add((x0 + col, y0 + row))
    ring = outline_of(m)
    for (x, y) in m:                          # 先整块铺描边色
        setpx(im, x, y, c(1))
    for (x, y) in m:                          # 再上本体色（边界自动留描边）
        if (x, y) in ring:
            continue
        setpx(im, x, y, c(9))
    setpx(im, x0 + 2, y0 + 1, c(12))          # 单眼
    setpx(im, x0 + 1, y0 + 1, c(5))           # 眼高光


def draw_weapon(im, p, c):
    """weapon：身前件 —— 加粗左伪足 + summon 的小史莱姆。
    伪足与身体融合处不留描边，只在体外沿保留。"""
    if not p['puddle'] and p['reach'] > 0:
        m = pseudo_mask(p)
        if m:
            ring = outline_of(m)
            body = body_mask(p)
            for (x, y) in m:                  # 先整块铺描边色
                setpx(im, x, y, c(1))
            for x, (yc, hh, _) in pseudo_cols(p).items():
                for k in range(-hh, hh + 1):
                    y = yc + k
                    if (x, y) not in m:
                        continue
                    if (x, y) in ring and (x, y) not in body:
                        continue              # 体外沿保留描边
                    col = 3 if k < 0 else (4 if k > 0 else 2)
                    setpx(im, x, y, c(col))
            tip = pseudo_tip(p)
            if tip:
                setpx(im, tip[0], tip[1] - 1, c(3))   # 尖端果冻反光
    if p['spawn'] != 'none':
        draw_mini(im, p, c)


def draw_gem_flare(im, p, c):
    """宝石闪光（fx 层）：冠周 3 粒火花（金黄/白），位置随冠顶浮动。"""
    x0, y0 = crown_rect(p)
    setpx(im, x0 - 1, y0 + 2, c(10))
    setpx(im, x0 + 8, y0 + 1, c(5))
    setpx(im, x0 + 1, y0 - 1, c(10))


def draw_fx(im, p, c):
    """fx：命中冲击星 / 弹跳水花 / 落地溅开 / 咆哮音环 / 余波 / 消散粒子 / 宝石闪光。
    全部整块不透明色，禁渐变、禁半透明。"""
    kind = p['fx']
    cx = CX + p['lean']
    if kind == 'impact':
        tip = pseudo_tip(p)
        if not tip:
            return
        tx, ty = tip
        # 紧凑 ±1 火花（tip 已贴近左界，±2 版会出界 x=0）
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            setpx(im, tx + dx, ty + dy, c(10))
        setpx(im, tx, ty, c(5))               # 芯
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            setpx(im, tx + dx, ty + dy, c(10))
        for gx, col in ((-1, 9), (0, 5), (1, 9)):
            setpx(im, tx + gx, ty - 2, c(col))    # 上方弧光
    elif kind == 'droplet':                   # 弹跳起落的水花
        y = BASE_Y + p['dy'] + 1
        for dx, dy, col in ((-13, 0, 3), (-14, -1, 9), (-12, -2, 5),
                            (13, 0, 3), (14, -1, 9), (12, -2, 5)):
            setpx(im, cx + dx, y + dy, c(col))
    elif kind == 'splash':                    # 小史莱姆落地溅开（在其右侧）
        mx = max(1, cx - 15) + 6
        my = FOOT_Y - 1
        for dx, dy, col in ((-2, 0, 9), (2, 0, 9), (-1, -1, 5), (1, -1, 5),
                            (-2, -1, 3), (2, -1, 3)):
            setpx(im, mx + dx, my + dy, c(col))
    elif kind == 'shockwave':                 # 咆哮：双环（内环金黄方框 + 外环白色四弧）
        h, _ = body_shape(p)
        base = BASE_Y + p['dy']
        top = base - h + 1
        eye_y = top + max(3, int(round(h * 0.36))) + p['eyeoff']
        mx, my = cx, eye_y + 5                # 嘴心
        ix0, iy0, ix1, iy1 = mx - 6, my - 5, mx + 6, my + 5
        for gx in range(ix0, ix1 + 1):
            setpx(im, gx, iy0, c(10)); setpx(im, gx, iy1, c(10))
        for gy in range(iy0, iy1 + 1):
            setpx(im, ix0, gy, c(10)); setpx(im, ix1, gy, c(10))
        ox0, oy0, ox1, oy1 = mx - 10, my - 9, mx + 10, my + 9
        for gx in range(ox0 + 1, ox1):        # 外环去四角 = 四弧
            setpx(im, gx, oy0, c(5)); setpx(im, gx, oy1, c(5))
        for gy in range(oy0 + 1, oy1):
            setpx(im, ox0, gy, c(5)); setpx(im, ox1, gy, c(5))
    elif kind == 'aftershock':                # 余波：单环放大 + 地面两粒尘埃
        for gx in range(5, 26):
            setpx(im, gx, 12, c(10)); setpx(im, gx, 29, c(10))
        for gy in range(12, 30):
            setpx(im, 5, gy, c(10)); setpx(im, 25, gy, c(10))
        setpx(im, cx - 12, 28, c(9))
        setpx(im, cx + 11, 28, c(9))
    elif kind == 'dissipate':                 # 死亡末帧：向上飘散的粒子
        for x, y, col in ((8, 21, 5), (13, 18, 9), (18, 20, 12),
                          (23, 16, 9), (16, 14, 5), (11, 15, 12)):
            setpx(im, x, y, c(col))
    if p['gem_flare']:
        draw_gem_flare(im, p, c)


# ---------------- 5. 动作表（统一走 pose() 一个入口）----------------
def pose(dy=0, lean=0, squash=0, wobble=0, eyes='open', eyeoff=0, reach=0,
         flash=0, tint=0, puddle=0, fx=None, swing=0, mouth='none',
         gem_flare=0, spawn='none'):
    p = dict(dy=dy, lean=lean, squash=squash, wobble=wobble, eyes=eyes,
             eyeoff=eyeoff, reach=reach, flash=flash, tint=tint,
             puddle=puddle, fx=fx, swing=swing, mouth=mouth,
             gem_flare=gem_flare, spawn=spawn)
    remap = {}
    if flash:                                 # 受击闪白：描边转红、身披宝石转白、皇冠留金
        p['eyes'] = 'line'
        remap = {1: 8, 2: 5, 3: 5, 4: 5, 6: 5, 8: 5, 9: 5, 11: 10,
                 13: 5, 14: 5, 15: 5}
    elif tint:                                # 带一点受击暗红
        remap = {1: 7, 4: 15, 13: 14, 14: 15}
    p['remap'] = remap
    return p


# move：压扁蓄力 -> 弹起拉伸离地 -> 落地压扁 -> 回弹中立（收尾接近起始）
MOVE = [
    pose(dy=0, lean=1, squash=3, wobble=1, swing=-1),
    pose(dy=-4, lean=0, squash=-2, wobble=-2, swing=2, fx='droplet'),
    pose(dy=1, lean=1, squash=4, wobble=2, swing=-2),
    pose(dy=-1, lean=0, squash=1, wobble=0, swing=1),
]
# hit：第 0 帧闪白压扁（横线眼，皇冠留金）-> 第 1 帧回弹带暗红
HIT = [
    pose(dy=0, lean=1, squash=1, wobble=1, swing=-2, flash=1),
    pose(dy=-1, lean=1, squash=-1, wobble=-1, swing=1, eyeoff=1, tint=1),
]
# attack：后缩蓄力 -> 伪足甩出（拉长）-> 命中（伪足最前 + 冲击星 + 宝石闪光）-> 收回
ATTACK = [
    pose(dy=1, lean=2, squash=0, wobble=-1, swing=-2, reach=0),
    pose(dy=-1, lean=2, squash=-1, wobble=1, swing=-1, reach=3),
    pose(dy=-1, lean=3, squash=-3, wobble=2, swing=0, reach=5, gem_flare=1,
         fx='impact'),
    pose(dy=0, lean=2, squash=0, wobble=-1, swing=-1, reach=2),
]
# death：受击抖 -> 塌陷变矮 -> 摊平 -> 水渍 + 粒子 + 皇冠残骸
DEATH = [
    pose(dy=0, lean=-1, squash=-1, wobble=2, eyes='x', swing=1, tint=1),
    pose(dy=0, lean=1, squash=3, wobble=1, eyes='closed', tint=1),
    pose(dy=0, lean=1, squash=4, wobble=0, eyes='closed', eyeoff=-1, swing=-2,
         tint=1),
    pose(dy=0, puddle=1, fx='dissipate'),
]
# roar：仰头涨大 -> 张口咆哮（大口 + 双环音环）-> 余波（音环放大 + 尘埃）-> 收势
ROAR = [
    pose(dy=-2, lean=0, squash=-3, wobble=-1, swing=2, eyeoff=-1, gem_flare=1),
    pose(dy=-1, lean=0, squash=-2, wobble=0, swing=1, eyeoff=-1, mouth='wide',
         gem_flare=1, fx='shockwave'),
    pose(dy=0, lean=0, squash=-1, wobble=1, mouth='open', fx='aftershock'),
    pose(dy=0, lean=1, squash=1, wobble=0, swing=-1),
]
# summon：低头蓄力（宝石聚光）-> 张嘴弹出小史莱姆 -> 落地溅开 -> 回弹
SUMMON = [
    pose(dy=1, lean=1, squash=3, wobble=1, swing=-2, eyes='closed', eyeoff=1,
         gem_flare=1),
    pose(dy=-1, lean=2, squash=-2, wobble=0, swing=1, mouth='open',
         spawn='mouth'),
    pose(dy=0, lean=2, squash=0, wobble=1, mouth='open', spawn='land',
         fx='splash'),
    pose(dy=-1, lean=1, squash=-1, wobble=-1, swing=1, spawn='land'),
]

ACTIONS = {'move': MOVE, 'hit': HIT, 'attack': ATTACK, 'death': DEATH,
           'roar': ROAR, 'summon': SUMMON}


# ---------------- 6. 渲染 + 导出 ----------------
def render_frame(p):
    layers = {}
    c = lambda i: p['remap'].get(i, i)             # noqa: E731
    im = new_layer(); draw_back(im, p, c);    layers['back'] = im
    im = new_layer(); draw_body(im, p, c);    layers['body'] = im
    im = new_layer(); draw_weapon(im, p, c);  layers['weapon'] = im
    im = new_layer(); draw_fx(im, p, c);      layers['fx'] = im
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for name in LAYER_ORDER:
        sp = layers[name].load()
        for yy in range(SIZE):
            for xx in range(SIZE):
                if sp[xx, yy]:
                    px[xx, yy] = PALETTE[sp[xx, yy]]
    return out


def check_bounds(im, fid):
    """界断言：不透明像素须在 [1,30]x[1,30] 安全区、alpha∈{0,255}、不透明色数 <=15。
    把 DESIGN.md 的手算边界变成机器强制，越界即报帧 ID + 坐标。"""
    px = im.load()
    colors = set()
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = px[x, y]
            if a:
                if not (1 <= x <= 30 and 1 <= y <= 30):
                    raise SystemExit(
                        f'帧 {fid} 出界：({x},{y}) 超出 [1,30] 安全区')
                if a != 255:
                    raise SystemExit(f'帧 {fid} 存在半透明像素：({x},{y}) a={a}')
                colors.add((r, g, b, a))
    if len(colors) > 15:
        raise SystemExit(f'帧 {fid} 不透明色数 {len(colors)} > 15，调色板超标')


def export(pack, out_dir):
    if out_dir.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{out_dir}')
    (out_dir / 'frames').mkdir(parents=True)
    frames, imgs = [], []
    for action in PACKS[pack]:
        for i, p in enumerate(ACTIONS[action]):
            im = render_frame(p)
            fid = f'{action}_{i}'
            check_bounds(im, fid)
            im.save(out_dir / 'frames' / f'{fid}.png')
            imgs.append(im)
            frames.append({'id': fid, 'action': action, 'order': len(imgs) - 1,
                           'file': f'frames/{fid}.png',
                           'rect': [(len(imgs) - 1) * SIZE, 0, SIZE, SIZE],
                           'rgba_sha256': hashlib.sha256(im.tobytes()).hexdigest()})
    sheet = Image.new('RGBA', (len(imgs) * SIZE, SIZE), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        sheet.paste(im, (i * SIZE, 0))
    sheet.save(out_dir / 'sprite-sheet.png')
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.Resampling.NEAREST).save(
        out_dir / 'contact-sheet-8x.png')     # 放大一律 NEAREST
    atlas = {'size': [sheet.width, SIZE], 'frame_size': SIZE,
             'palette_size': len(PALETTE), 'layer_order': LAYER_ORDER,
             'pack': pack, 'actions': PACKS[pack], 'frames': frames}
    (out_dir / 'atlas.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2),
                                        encoding='utf-8')
    (out_dir / 'palette.json').write_text(json.dumps(PALETTE, ensure_ascii=False),
                                          encoding='utf-8')
    hashes = [f['rgba_sha256'] for f in frames]
    if len(set(hashes)) != len(hashes):
        dup = [f['id'] for f in frames if hashes.count(f['rgba_sha256']) > 1]
        raise SystemExit(f'姿态重复，必须让每帧有真实差异：{dup}')
    if not any((out_dir / f['file']).stat().st_size for f in frames):
        raise SystemExit('所有帧都是空白，角色未绘制')
    lines = []
    for f in frames:
        sha = hashlib.sha256((out_dir / f['file']).read_bytes()).hexdigest()
        lines.append(f'{sha}  {f["file"]}')
    with open(out_dir / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'OK -> {out_dir}  包={pack}  帧数={len(imgs)}  画布={SIZE}  '
          f'颜色数={len(PALETTE)}  帧间差异校验=PASS  界断言=PASS')
    print('   帧清单: ' + ', '.join(f['id'] for f in frames))


if __name__ == '__main__':
    packs = [PACK] if PACK else list(PACKS)
    for pk in packs:
        if pk not in PACKS:
            raise SystemExit(f'未知包名 {pk}，可选：{list(PACKS)}')
        export(pk, BASE / f'{NAME}-{PACK_SUFFIX[pk]}{REV}')
    print('下一步：真实打开 contact-sheet-8x.png 目检轮廓/姿态差异/部位一致/不截断')
