# -*- coding: utf-8 -*-
"""
金发双马尾女剑士 —— 共享造型库（唯一定义源 / SOURCE OF TRUTH）

子 Agent 只读引用，禁止修改。需要新部件 / 新特效请回报主 Agent。
本文件只依赖 Pillow。所有 fill / outline 一律传调色板索引，绝不传 RGB。
"""
import math, json, hashlib, re, shutil
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- 常量

SIZE = 64
CX = 32          # 身体水平中心；所有躯干部件 x = CX + lean + 相对偏移
HEAD_Y = 8       # 头顶
HEAD_BOT = 23    # 下巴
EYE_Y = 15       # 眼睛顶行（4x4 眼）
SHOUL_Y = 28     # 肩线
WAIST_Y = 33     # 腰带
HIP_Y = 36       # 裙摆上沿
HEM_Y = 41       # 裙摆下沿（中性）
FOOT_Y = 58      # 靴底（dy=0）
SWORD_LEN = 30   # 剑长（全项目恒定）

DY_MAX = {0: 4, 1: 4, 2: 4, 3: 7, 4: 4, 5: 4, 6: 3, 7: 4}

# 索引别名
C_TR, C_OUT, C_HAIR, C_HAIR_L, C_HAIR_D = 0, 1, 2, 3, 4
C_WHITE, C_SKIN, C_SKIN_D = 5, 6, 7
C_PINK, C_PINK_D = 8, 9
C_STEEL, C_STEEL_D, C_GOLD = 10, 11, 12
C_EYE, C_RIBBON, C_FX = 13, 14, 15

PALETTE = [
    (0, 0, 0, 0),            # 0  透明（必须）
    (46, 34, 54, 255),       # 1  描边暖深色
    (240, 198, 96, 255),     # 2  金发·主
    (255, 232, 160, 255),    # 3  金发·亮
    (196, 148, 58, 255),     # 4  金发·暗
    (248, 250, 252, 255),    # 5  白
    (255, 222, 196, 255),    # 6  皮肤
    (230, 180, 144, 255),    # 7  皮肤暗
    (238, 166, 192, 255),    # 8  裙甲粉·主
    (198, 120, 152, 255),    # 9  裙甲粉·暗 / 靴
    (156, 208, 228, 255),    # 10 剑刃青
    (88, 126, 152, 255),     # 11 剑身暗 / 剑柄
    (214, 164, 64, 255),     # 12 金饰
    (96, 156, 232, 255),     # 13 蓝瞳     ← 禁入 flash remap
    (214, 72, 86, 255),      # 14 发带红   ← 禁入 flash remap
    (130, 232, 255, 255),    # 15 特效青
]

# 闪白：纯索引替换，禁止半透明。6/7/13/14/15/0/5 绝不能做 key。
FLASH_FULL = {1: C_RIBBON, 2: C_WHITE, 3: C_WHITE, 4: C_WHITE,
              8: C_WHITE, 9: C_WHITE, 10: C_WHITE, 11: C_WHITE, 12: C_WHITE}
FLASH_SOFT = {2: C_WHITE, 3: C_WHITE, 4: C_WHITE,
              8: C_WHITE, 9: C_WHITE, 10: C_WHITE, 11: C_WHITE, 12: C_WHITE}
FORBIDDEN_REMAP = {0, 5, 6, 7, 13, 14, 15}

LAYER_ORDER = ['backfx', 'hair', 'body', 'weapon', 'fx']
FX_SCREEN_LEVEL = {'burst-wide'}          # 允许贴边的屏幕级特效
FID_RE = re.compile(r'^[a-z0-9-]+_\d+$')  # 帧 id 规范（viewer 靠它拆动作）

# ---------------------------------------------------------------- 原语


def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)


def rect(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)


def ell(d, box, c, outline=None):
    d.ellipse(box, fill=c, outline=outline)


def seg(d, pts, c, w=1):
    d.line(pts, fill=c, width=w, joint='curve')


def limb(d, pts, fill, w):
    """先画粗描边再画细芯，得到带 1px 硬描边的肢体（避免小部件被描边吃掉）。"""
    seg(d, pts, C_OUT, w + 2)
    seg(d, pts, fill, w)


# ---------------------------------------------------------------- 姿态


def pose(dy=0, lean=0, legs=0, swing=0, skirt=0, tail=0,
         arm=(42, 30), back_arm=None,
         sword=(0, 0, 205, 30), head='normal', flash=0,
         fx=None, fx_back=None):
    if isinstance(sword, int):
        sword = (0, 0, sword, SWORD_LEN)
    return {'dy': dy, 'lean': lean, 'legs': legs, 'swing': swing, 'skirt': skirt,
            'tail': tail, 'arm': tuple(arm),
            'back_arm': (None if back_arm is None else tuple(back_arm)),
            'sword': tuple(sword), 'head': head, 'flash': flash,
            'fx': fx, 'fx_back': fx_back}


class Frame:
    def __init__(self, fid, p):
        self.id = fid
        self.pose = p


def _hand(p):
    """持剑手绝对坐标（手 y = arm[1] + dy）。"""
    return (p['arm'][0], p['arm'][1] + p['dy'])


def sword_tip(hand, deg, length=SWORD_LEN):
    """剑尖 = 手 + length × (cos deg, −sin deg)。deg: 0=右(身后) 90=上 180=左(正前) 270=下"""
    r = math.radians(deg)
    return (round(hand[0] + length * math.cos(r)), round(hand[1] - length * math.sin(r)))


# ---------------------------------------------------------------- 图层绘制


def draw_backfx(d, p):
    k = p['fx_back']
    if k is None:
        return
    if k == 'burst-wide':
        for i, (b, w) in enumerate([((2, 2, 61, 61), 3), ((8, 8, 55, 55), 2)]):
            d.arc(b, 0, 360, fill=(C_FX if i == 0 else C_WHITE), width=w)
        for a in range(0, 360, 45):
            r = math.radians(a)
            x = 31 + 30 * math.cos(r)
            y = 31 + 30 * math.sin(r)
            d.point((round(x), round(y)), fill=C_WHITE)
    elif k == 'spin':
        d.arc((10, 14, 54, 50), 20, 200, fill=C_FX, width=2)
        d.arc((14, 18, 50, 46), 200, 340, fill=C_FX, width=2)
    else:
        raise SystemExit(f'未知 fx_back: {k}')


def draw_hair_back(d, p):
    """脑后发 + 双马尾。swing 负=向身后(画面右)飘，正=向身前(画面左)甩。"""
    y, x = p['dy'], CX + p['lean']
    off = -p['swing'] * 2          # swing=-3 → off=+6（向后飘）
    tl = p['tail']
    # 脑后发团（只到肩，别盖住身体）
    ell(d, (x - 9, 7 + y, x + 9, 26 + y), C_HAIR_D, outline=C_OUT)
    ell(d, (x - 7, 10 + y, x + 7, 22 + y), C_HAIR)
    # 双马尾：垂在身体两侧、与身体轮廓分离
    for dirx in (-1, 1):
        bx = x + dirx * 10
        pts = [(bx, 13 + y),
               (bx + dirx * 2 + off * 0.45, 27 + y + tl * 0.5),
               (bx + dirx * 5 + off, 42 + y + tl)]
        seg(d, pts, C_OUT, 6)
        seg(d, pts, C_HAIR, 4)
        seg(d, pts, C_HAIR_L, 1)
    # 发梢暗边
    for dirx in (-1, 1):
        tx = x + dirx * 10 + dirx * 5 + off
        rect(d, (tx - 2, 40 + y + tl, tx + 2, 43 + y + tl), C_HAIR_D)


def draw_head(d, p):
    y, x, mode = p['dy'], CX + p['lean'], p['head']
    # 脸
    ell(d, (x - 10, HEAD_Y + y, x + 6, HEAD_BOT + y), C_SKIN, outline=C_OUT)
    # 刘海 / 顶部发块（斜切圆角 + 锯齿下沿，露出眼睛）
    d.polygon([(x - 8, 6 + y), (x + 5, 6 + y), (x + 9, 9 + y), (x + 9, 12 + y),
               (x + 6, 14 + y), (x + 4, 10 + y), (x + 1, 14 + y),
               (x - 2, 10 + y), (x - 5, 14 + y), (x - 8, 10 + y), (x - 12, 13 + y),
               (x - 12, 9 + y)],
              fill=C_HAIR, outline=C_OUT)
    # 高光带
    seg(d, [(x - 7, 8 + y), (x + 3, 9 + y)], C_HAIR_L, 2)
    # 侧发（鬓角）
    rect(d, (x - 12, 12 + y, x - 9, 22 + y), C_HAIR_D, outline=C_OUT)
    rect(d, (x + 7, 12 + y, x + 10, 22 + y), C_HAIR_D, outline=C_OUT)
    # 蝴蝶结（禁入 flash remap，闪白帧仍是红的）
    for bx in (x - 12, x + 6):
        rect(d, (bx, 9 + y, bx + 4, 12 + y), C_RIBBON, outline=C_OUT)
        d.point((bx + 2, 10 + y), fill=C_WHITE)
    # 眼睛
    if mode == 'dead':
        for ex in (x - 8, x - 1):
            seg(d, [(ex, EYE_Y + y), (ex + 3, EYE_Y + 3 + y)], C_OUT, 1)
            seg(d, [(ex + 3, EYE_Y + y), (ex, EYE_Y + 3 + y)], C_OUT, 1)
    elif mode == 'blink':
        for ex in (x - 8, x - 1):
            seg(d, [(ex, EYE_Y + 2 + y), (ex + 3, EYE_Y + 2 + y)], C_OUT, 1)
    else:
        ec = C_FX if mode == 'glow' else C_EYE
        for ex in (x - 8, x - 1):
            rect(d, (ex, EYE_Y + y, ex + 3, EYE_Y + 3 + y), ec)
            seg(d, [(ex, EYE_Y - 1 + y), (ex + 3, EYE_Y - 1 + y)], C_OUT, 1)
            d.point((ex + 1, EYE_Y + 1 + y), fill=C_WHITE)
    # 嘴 + 腮红
    rect(d, (x - 2, 21 + y, x - 1, 21 + y), C_OUT)
    rect(d, (x - 8, 20 + y, x - 7, 20 + y), C_PINK)
    rect(d, (x + 3, 20 + y, x + 4, 20 + y), C_PINK)


def draw_body(d, p):
    y, x = p['dy'], CX + p['lean']
    # 颈
    rect(d, (x - 2, 22 + y, x + 1, 25 + y), C_SKIN_D)
    # 躯干
    rect(d, (x - 6, 25 + y, x + 6, HIP_Y + y), C_PINK, outline=C_OUT)
    # 胸甲白件 + 金边
    rect(d, (x - 4, 26 + y, x + 4, 31 + y), C_WHITE)
    seg(d, [(x - 4, 26 + y), (x + 4, 26 + y)], C_GOLD, 1)
    # 肩甲
    ell(d, (x - 8, 25 + y, x - 3, 30 + y), C_WHITE, outline=C_OUT)
    ell(d, (x + 3, 25 + y, x + 8, 30 + y), C_WHITE, outline=C_OUT)
    # 腰带
    rect(d, (x - 6, WAIST_Y - 1 + y, x + 6, WAIST_Y + 1 + y), C_GOLD, outline=C_OUT)
    rect(d, (x - 2, WAIST_Y - 1 + y, x + 1, WAIST_Y + 1 + y), C_WHITE)
    # 裙摆
    draw_skirt(d, x, y, p['skirt'])
    # 腿
    draw_legs(d, x, y, p['legs'])
    # 头（脸/刘海/眼睛 —— 必须画，放在躯干之上）
    draw_head(d, p)
    # 手臂（副臂在躯干之前画，持剑臂在躯干之后画 → 持剑臂压在上面）
    draw_arm_back(d, x, y, p['back_arm'])
    draw_arm(d, x, y, p['arm'])


def draw_skirt(d, x, y, skirt):
    hip = HIP_Y - 2 + y
    if skirt >= 4:                        # 铺地
        hem = 46 + y
        d.polygon([(x - 7, hip), (x + 7, hip), (x + 13, hem), (x - 13, hem)],
                  fill=C_PINK, outline=C_OUT)
        seg(d, [(x - 12, hem - 1), (x + 12, hem - 1)], C_PINK_D, 2)
    else:
        hem = HEM_Y + y + abs(skirt)
        off = skirt * 2
        d.polygon([(x - 7, hip), (x + 7, hip), (x + 7 + off, hem), (x - 7 + off, hem)],
                  fill=C_PINK, outline=C_OUT)
        seg(d, [(x - 6 + off, hem - 1), (x + 6 + off, hem - 1)], C_PINK_D, 2)


def draw_legs(d, x, y, legs):
    hip = HIP_Y + y
    foot = FOOT_Y + y
    P = {
        0: [((x - 4, hip), (x - 4, foot - 5), (x - 4, foot)),
            ((x + 3, hip), (x + 3, foot - 5), (x + 3, foot))],
        1: [((x - 4, hip), (x - 8, hip + 9), (x - 9, foot)),
            ((x + 3, hip), (x + 3, foot - 5), (x + 3, foot))],
        2: [((x - 4, hip), (x - 4, foot - 5), (x - 4, foot)),
            ((x + 3, hip), (x + 7, hip + 9), (x + 8, foot))],
        3: [((x - 4, hip), (x - 9, hip + 5), (x - 6, hip + 10)),
            ((x + 3, hip), (x + 6, hip + 4), (x + 3, hip + 11))],
        4: [((x - 4, hip), (x - 11, hip + 8), (x - 12, foot)),
            ((x + 3, hip), (x + 9, hip + 8), (x + 10, foot))],
        5: [((x - 4, hip), (x - 9, hip + 8), (x - 8, foot)),
            ((x + 3, hip), (x + 6, foot - 2), (x + 2, foot))],
        6: [((x - 4, hip), (x - 9, hip + 6), (x - 5, foot)),
            ((x + 3, hip), (x + 7, hip + 6), (x + 4, foot))],
        7: [((x - 4, hip), (x - 10, hip + 7), (x - 16, foot - 2)),
            ((x + 3, hip), (x + 9, hip + 7), (x + 14, foot))],
    }[legs]
    for pts in P:
        # 线帽会超出端点约 3px → 腿身收短，靴子负责到底（否则戳穿画布底边）
        body = [(px_, py_) for px_, py_ in pts[:-1]] + [(pts[-1][0], pts[-1][1] - 3)]
        limb(d, body, C_WHITE, 4)
        fx_, fy_ = pts[-1]
        rect(d, (fx_ - 3, fy_ - 5, fx_ + 3, fy_), C_PINK_D, outline=C_OUT)
        seg(d, [(fx_ - 3, fy_ - 5), (fx_ + 3, fy_ - 5)], C_GOLD, 1)


def draw_arm(d, x, y, arm):
    sh = (x + 5, SHOUL_Y + y)
    hx, hy = arm[0], arm[1] + y
    elb = ((sh[0] + hx) // 2 + 2, (sh[1] + hy) // 2)
    limb(d, [sh, elb, (hx, hy)], C_SKIN, 3)
    ell(d, (hx - 2, hy - 2, hx + 2, hy + 2), C_SKIN, outline=C_OUT)


def draw_arm_back(d, x, y, back_arm):
    sh = (x - 5, SHOUL_Y + y)
    if back_arm is None:
        pts = [sh, (x - 8, SHOUL_Y + 6 + y), (x - 8, SHOUL_Y + 12 + y)]
    else:
        bx, by = back_arm[0], back_arm[1] + y
        elb = ((sh[0] + bx) // 2 - 1, (sh[1] + by) // 2 - 2)
        pts = [sh, elb, (bx, by)]
    limb(d, pts, C_SKIN, 3)
    ell(d, (pts[-1][0] - 2, pts[-1][1] - 2, pts[-1][0] + 2, pts[-1][1] + 2),
        C_SKIN, outline=C_OUT)


def draw_weapon(d, p):
    hand = _hand(p)
    _dx, _dy, deg, length = p['sword']
    draw_sword(d, hand, deg, length)


def draw_sword(d, hand, deg, length=SWORD_LEN):
    hx, hy = hand
    r = math.radians(deg)
    ux, uy = math.cos(r), -math.sin(r)
    px, py = -uy, ux

    def P(t, o=0):
        return (round(hx + ux * t + px * o), round(hy + uy * t + py * o))

    # 剑柄 + 柄头
    seg(d, [P(-6), P(1)], C_STEEL_D, 3)
    rect(d, (P(-8)[0] - 1, P(-8)[1] - 1, P(-8)[0] + 1, P(-8)[1] + 1), C_GOLD)
    # 护手
    seg(d, [P(2, 3), P(2, -3)], C_GOLD, 3)
    # 剑身（粗描边 → 芯）
    seg(d, [P(3), P(28)], C_OUT, 5)
    seg(d, [P(3), P(28)], C_STEEL, 3)
    seg(d, [P(28), P(30)], C_STEEL, 1)
    # 高光 / 暗边
    seg(d, [P(5, 1), P(25, 1)], C_WHITE, 1)
    seg(d, [P(5, -1), P(25, -1)], C_STEEL_D, 1)


# ---------------------------------------------------------------- 特效


def draw_fx(d, p):
    k = p['fx']
    if k is None:
        return
    fn = {
        'dust': fx_dust, 'slash-up': fx_slash_up, 'slash-wide': fx_slash_wide,
        'slash-heavy': fx_slash_heavy, 'thrust': fx_thrust, 'afterimage': fx_afterimage,
        'charge': fx_charge, 'charge-max': fx_charge_max, 'burst': fx_burst,
        'spark': fx_spark,
    }.get(k)
    if fn is None:
        raise SystemExit(f'未知 fx: {k}（只能用 CONTRACT 注册表里的名字）')
    fn(d, p)


def fx_dust(d, p):
    y, x = p['dy'], CX + p['lean']
    base = FOOT_Y + y                       # 最低行 = 62 + dy → 要求 dy ≤ 1
    for dx, dy2, w, h in ((-16, 1, 8, 4), (-11, -1, 6, 5), (5, 0, 9, 4), (13, 2, 6, 3)):
        ell(d, (x + dx, base - 3 + dy2, x + dx + w, base + 1 + dy2), C_WHITE)
    for dx, dy2 in ((-13, 0), (-4, 2), (9, 1), (17, 3)):
        d.point((x + dx, base - 1 + dy2), fill=C_FX)
    seg(d, [(x - 14, base + 1), (x + 14, base + 1)], C_FX, 1)


def fx_slash_up(d, p):
    y = p['dy']
    d.arc((6, 4 + y, 56, 52 + y), 70, 215, fill=C_FX, width=5)
    d.arc((11, 9 + y, 51, 47 + y), 75, 210, fill=C_WHITE, width=2)


def fx_slash_wide(d, p):
    # Pillow 的 arc 在图像坐标下是「顺时针」：270° = 顶部。
    # 弧顶必须落在脸底(23+dy)之下，否则会横过嘴/眼 —— bbox 上边 24+y 即为此定值。
    y = p['dy']
    d.arc((2, 24 + y, 48, 52 + y), 200, 355, fill=C_FX, width=5)
    d.arc((6, 28 + y, 44, 48 + y), 205, 350, fill=C_WHITE, width=2)


def fx_slash_heavy(d, p):
    # 走左半弧（120°→240° 顺时针经 180°=左侧），弧身只在脸下方/脸左侧，绝不穿脸
    y, x = p['dy'], CX + p['lean']
    d.arc((20, 4 + y, 52, 56 + y), 120, 240, fill=C_FX, width=6)
    d.arc((24, 8 + y, 48, 52 + y), 125, 235, fill=C_WHITE, width=2)
    seg(d, [(x - 18, FOOT_Y - 1 + y), (x + 16, FOOT_Y - 1 + y)], C_FX, 3)
    seg(d, [(x - 16, FOOT_Y + 1 + y), (x + 14, FOOT_Y + 1 + y)], C_WHITE, 1)


def fx_thrust(d, p):
    y, x = p['dy'], CX + p['lean']
    hy = p['arm'][1] + y
    hx = p['arm'][0]
    seg(d, [(4, hy - 2), (hx - 2, hy - 2)], C_FX, 2)
    seg(d, [(4, hy + 2), (hx - 2, hy + 2)], C_FX, 2)
    seg(d, [(4, hy), (hx - 4, hy)], C_WHITE, 2)
    d.polygon([(4, hy - 4), (4, hy + 4), (11, hy)], fill=C_WHITE)


def fx_afterimage(d, p):
    """原地白色简化轮廓（x 22~37）；本体必须靠 lean ≥ +6 让开。"""
    ell(d, (25, 10, 36, 22), C_WHITE)
    rect(d, (26, 23, 35, 33), C_WHITE)
    d.polygon([(25, 34), (36, 34), (38, 41), (23, 41)], fill=C_WHITE)
    rect(d, (26, 42, 29, 54), C_WHITE)
    rect(d, (32, 42, 35, 54), C_WHITE)


def fx_charge(d, p):
    y, x = p['dy'], CX + p['lean']
    base = FOOT_Y + y
    ell(d, (x - 14, base - 3, x + 14, base + 2), C_FX)
    ell(d, (x - 10, base - 5, x + 10, base + 1), C_WHITE)
    for i, (dx, dy2) in enumerate(((-13, -12), (11, -18), (-9, -26), (8, -30))):
        d.point((x + dx, base + dy2), fill=(C_FX if i % 2 else C_HAIR_L))
    d.arc((x - 20, 10 + y, x + 20, 50 + y), 30, 150, fill=C_FX, width=2)


def fx_charge_max(d, p):
    fx_charge(d, p)
    y, x = p['dy'], CX + p['lean']
    base = FOOT_Y + y
    ell(d, (x - 17, base - 6, x + 17, base + 3), C_FX)
    ell(d, (x - 12, base - 8, x + 12, base + 2), C_WHITE)
    for dx, dy2 in ((-15, -16), (13, -22), (-10, -32), (11, -36)):
        d.point((x + dx, base + dy2), fill=C_HAIR_L)
    # 顶弧上边 10+y：弧顶 y=10+dy 落在眼(15+dy)上方 5px，否则会横穿眼线
    d.arc((x - 19, 10 + y, x + 19, 42 + y), 200, 340, fill=C_WHITE, width=1)


def fx_burst(d, p):
    # 圆心必须落在身前(x-14)而非躯干上，否则三层同心圆会糊住角色本体
    y, x = p['dy'], CX + p['lean']
    cx, cy = x - 14, 36 + y
    for rr, c, w in ((13, C_FX, 3), (9, C_WHITE, 2), (5, C_FX, 2)):
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=c, width=w)
    for a in range(0, 360, 45):
        r = math.radians(a)
        x0 = min(61, max(2, round(cx + 15 * math.cos(r))))
        y0 = min(61, max(2, round(cy + 15 * math.sin(r))))
        x1 = min(61, max(2, round(cx + 20 * math.cos(r))))
        y1 = min(61, max(2, round(cy + 20 * math.sin(r))))
        seg(d, [(x0, y0), (x1, y1)], C_HAIR_L, 2)


def fx_spark(d, p):
    y, x = p['dy'], CX + p['lean']
    pts = ((-16, -6), (-12, -20), (12, -14), (16, -26), (-6, -34), (6, -40), (0, -50))
    for i, (dx, dy2) in enumerate(pts):
        c = C_HAIR_L if i % 2 == 0 else C_FX
        rect(d, (x + dx, FOOT_Y + y + dy2, x + dx + 1, FOOT_Y + y + dy2 + 1), c)


# ---------------------------------------------------------------- 合成


def _remap(im, table):
    for k in table:
        if k in FORBIDDEN_REMAP:
            raise SystemExit(f'flash remap 含禁用索引 {k}：会让瞳孔/发带消失')
    out = im.copy()
    px = out.load()
    for yy in range(SIZE):
        for xx in range(SIZE):
            v = px[xx, yy]
            if v in table:
                px[xx, yy] = table[v]
    return out


def mk_frame(fid, p):
    layers = {}
    im = new_layer()
    draw_backfx(ImageDraw.Draw(im), p)
    layers['backfx'] = im
    im = new_layer()
    draw_hair_back(ImageDraw.Draw(im), p)
    layers['hair'] = im
    im = new_layer()
    draw_body(ImageDraw.Draw(im), p)
    layers['body'] = im
    im = new_layer()
    draw_weapon(ImageDraw.Draw(im), p)
    layers['weapon'] = im
    im = new_layer()
    draw_fx(ImageDraw.Draw(im), p)
    layers['fx'] = im

    for name, mx in (('hair', p['flash']), ('body', p['flash']), ('weapon', p['flash'])):
        if mx:
            layers[name] = _remap(layers[name], FLASH_FULL if mx == 1 else FLASH_SOFT)

    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for name in LAYER_ORDER:
        sp = layers[name].load()
        for yy in range(SIZE):
            for xx in range(SIZE):
                v = sp[xx, yy]
                if v:
                    px[xx, yy] = PALETTE[v]
    return out


# ---------------------------------------------------------------- 校验


def check_pose(fid, p):
    if not FID_RE.match(fid):
        raise SystemExit(f'帧 id 不合规：{fid}（必须 <clip>_<n>，否则 viewer 拆不出动作）')
    if p['dy'] > DY_MAX.get(p['legs'], 4):
        raise SystemExit(f'{fid}: dy={p["dy"]} 超过 legs={p["legs"]} 的上限 '
                         f'{DY_MAX.get(p["legs"], 4)}（靴底会被切）')
    if p['fx'] == 'dust' and p['dy'] > 1:
        raise SystemExit(f'{fid}: fx=dust 时 dy 必须 ≤ 1（尘团最低行 61+dy）')
    if p['fx'] == 'slash-heavy' and p['dy'] > 2:
        raise SystemExit(f'{fid}: fx=slash-heavy 时 dy 必须 ≤ 2')
    if p['fx'] == 'slash-up' and p['lean'] > -3:
        raise SystemExit(f'{fid}: fx=slash-up 时 lean 必须 ≤ -3（否则弧光糊住脸）')
    if p['fx'] == 'afterimage' and p['lean'] < 6:
        raise SystemExit(f'{fid}: fx=afterimage 时 lean 必须 ≥ +6（本体要让开原地残影）')
    if p['head'] not in ('normal', 'blink', 'dead', 'glow'):
        raise SystemExit(f'{fid}: head 取值非法 {p["head"]}')
    if not (-3 <= p['swing'] <= 3):
        raise SystemExit(f'{fid}: swing 越界 {p["swing"]}')
    if not (-3 <= p['skirt'] <= 4):
        raise SystemExit(f'{fid}: skirt 越界 {p["skirt"]}')
    if not (-4 <= p['tail'] <= 3):
        raise SystemExit(f'{fid}: tail 越界 {p["tail"]}')

    # 双马尾水平范围：tip_x = CX + lean ± 15 − 2·swing（线宽 6 → ±3）
    tail_off = p['lean'] - 2 * p['swing']
    if not (-14 <= tail_off <= 13):
        raise SystemExit(f'{fid}: lean={p["lean"]} + swing={p["swing"]} 会让马尾出界'
                         f'（lean − 2·swing = {tail_off}，须在 [-14, 13]）')

    hand = _hand(p)
    _dx, _dy, deg, length = p['sword']
    tip = sword_tip(hand, deg, length)
    if not (2 <= tip[0] <= 61 and 2 <= tip[1] <= 60):
        raise SystemExit(f'{fid}: 剑尖 {tip} 越界（hand={hand} deg={deg}）'
                         f'— 剑尖 = 手 + {length}×(cos deg, −sin deg)')

    # 剑身不得横穿脸部
    hx0, hy0 = CX + p['lean'] - 10, HEAD_Y + p['dy']
    hx1, hy1 = CX + p['lean'] + 6, HEAD_BOT + p['dy']
    r = math.radians(deg)
    ux, uy = math.cos(r), -math.sin(r)
    for i in range(61):
        t = 3 + i * 0.5
        sx = round(hand[0] + ux * t)
        sy = round(hand[1] + uy * t)
        if hx0 <= sx <= hx1 and hy0 <= sy <= hy1:
            raise SystemExit(f'{fid}: 剑身穿过头部（交点 {sx},{sy}）'
                             f'— 调 hand/deg/lean 让开头框')


def check_image(fid, im, p):
    if im.getbbox() is None:
        raise SystemExit(f'{fid}: 空白帧，角色没画出来')
    screen = (p['fx'] in FX_SCREEN_LEVEL) or (p['fx_back'] in FX_SCREEN_LEVEL)
    if not screen:
        b = im.getbbox()          # (l, t, r, b)，r/b 为开区间
        if b[0] == 0 or b[1] == 0 or b[2] >= SIZE or b[3] >= SIZE:
            raise SystemExit(f'{fid}: 内容贴边 bbox={b}（手脚/特效被 64 边界切掉）')


# ---------------------------------------------------------------- 导出


def contact_sheet(imgs, scale=8, cols=None):
    n = len(imgs)
    cols = cols or n
    rows = (n + cols - 1) // cols
    sheet = Image.new('RGBA', (SIZE * cols * scale, SIZE * rows * scale), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        sheet.paste(im.resize((SIZE * scale, SIZE * scale), Image.Resampling.NEAREST),
                    (c * SIZE * scale, r * SIZE * scale))
    return sheet


def dump_preview(frames, path, title='', cols=6, scale=6):
    """零副作用预览：只写一张 _ 前缀的 png，不建交付包。"""
    imgs = []
    for f in frames:
        check_pose(f.id, f.pose)
        imgs.append(mk_frame(f.id, f.pose))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    contact_sheet(imgs, scale=scale, cols=cols).save(path)
    print(f'[preview] {path}  ({len(imgs)} 帧)')


def export(outdir, title, frames, overwrite=False):
    out = Path(outdir)
    if out.exists() and any(out.iterdir()):
        if not overwrite:
            raise SystemExit(f'输出目录已存在：{out}\n'
                             f'  迭代请加 --overwrite（只覆盖本脚本自己会写的文件）或换 -r2 后缀')
        for f in ('atlas.json', 'palette.json', 'manifest.sha256', 'poses.json',
                  'sprite-sheet.png', 'contact-sheet-8x.png'):
            (out / f).unlink(missing_ok=True)
        if (out / 'frames').exists():
            for f in (out / 'frames').glob('*.png'):
                f.unlink()
    # 先全部校验 + 渲染，任何一帧不过就不落盘（避免留下半包）
    imgs, recs = [], []
    for f in frames:
        check_pose(f.id, f.pose)
        im = mk_frame(f.id, f.pose)
        check_image(f.id, im, f.pose)
        imgs.append(im)
        recs.append((f, im))

    (out / 'frames').mkdir(parents=True, exist_ok=True)

    hashes = [hashlib.sha256(im.tobytes()).hexdigest() for im in imgs]
    # 重复帧判定：只在同一 clip（动作）内拒绝；跨 clip 的关节帧（连招收势==下段起手）允许相同
    by_clip = {}
    for (f, im), h in zip(recs, hashes):
        by_clip.setdefault(f.id.rsplit('_', 1)[0], []).append((f.id, h))
    for clip, items in by_clip.items():
        ids = [i for i, h in items if len([1 for _, hh in items if hh == h]) > 1]
        if ids:
            raise SystemExit(f'姿态重复（clip={clip}），必须让每帧有真实差异：{ids}')

    atlas_frames, manifest = [], []
    for i, (f, im) in enumerate(recs):
        fid = f.id
        fp = out / 'frames' / f'{fid}.png'
        im.save(fp)
        h = hashlib.sha256(Path(fp).read_bytes()).hexdigest()
        manifest.append(f'{h}  frames/{fid}.png')
        clip = fid.rsplit('_', 1)[0]
        atlas_frames.append({'id': fid, 'action': clip, 'order': i,
                             'file': f'frames/{fid}.png',
                             'rect': [i * SIZE, 0, SIZE, SIZE],
                             'rgba_sha256': hashes[i], 'file_sha256': h})

    sheet = Image.new('RGBA', (SIZE * len(imgs), SIZE), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        sheet.paste(im, (i * SIZE, 0))
    sheet.save(out / 'sprite-sheet.png')
    contact_sheet(imgs).save(out / 'contact-sheet-8x.png')

    (out / 'palette.json').write_text(
        json.dumps({'size': len(PALETTE), 'colors': [list(c) for c in PALETTE]},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'atlas.json').write_text(json.dumps({
        'title': title, 'size': SIZE, 'frame_size': SIZE,
        'palette_size': len(PALETTE), 'layer_order': LAYER_ORDER,
        'anchors': {'CX': CX, 'HEAD_Y': HEAD_Y, 'HEAD_BOT': HEAD_BOT,
                    'SHOUL_Y': SHOUL_Y, 'WAIST_Y': WAIST_Y, 'HIP_Y': HIP_Y,
                    'FOOT_Y': FOOT_Y, 'SWORD_LEN': SWORD_LEN},
        'frames': atlas_frames}, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'poses.json').write_text(json.dumps(
        {'title': title, 'frames': [{'id': f.id, 'pose': f.pose} for f, _ in recs]},
        ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    with open(out / 'manifest.sha256', 'w', newline='\n', encoding='utf-8') as fh:
        fh.write('\n'.join(manifest) + '\n')

    print(f'[ok] {out}  {len(imgs)} 帧  → contact-sheet-8x.png 待目检')
