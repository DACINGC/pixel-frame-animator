# -*- coding: utf-8 -*-
"""
史莱姆（Slime）怪物帧动画生成器 —— 32x32 像素画，纯 Pillow 程序化点阵绘制。

造型：半圆顶 + 平底的绿色果冻块（底宽约 22px、高约 14px，坐在 FOOT_Y=27 接地线上），
      头顶弧形高光、左上白泽光、体内一颗深绿内核、两只圆眼（面朝左，无 outline）。

用法（第二个参数选包，缺省两个包都生成）：
  PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
  "$PY" gen_slime.py <父目录> locomotion          -> <父目录>/slime-move-hit
  "$PY" gen_slime.py <父目录> combat              -> <父目录>/slime-attack-death
  "$PY" gen_slime.py <父目录>                     -> 两个包都生成
  "$PY" gen_slime.py <父目录> locomotion -r2      -> 迭代版落到 slime-move-hit-r2（绝不覆盖旧包）

约定遵循 pixelwork/monsters/CONTRACT.md：
  SIZE=32 固定；有限调色板（15 色，索引 0 透明、索引 1 描边）；fill 一律传索引；
  锚点常量写死（TOP_Y/BASE_Y/FOOT_Y），姿态只做相对偏移；每帧有真实差异；统一面朝左。
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

# ---------------- 1. 配置 ----------------
SIZE = 32
NAME = 'slime'
BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
PACKS = {'locomotion': ['move', 'hit'], 'combat': ['attack', 'death']}
PACK_SUFFIX = {'locomotion': 'move-hit', 'combat': 'attack-death'}
PACK = sys.argv[2] if len(sys.argv) > 2 else None
REV = sys.argv[3] if len(sys.argv) > 3 else ''      # 迭代后缀，如 -r2

PALETTE = [                             # 索引 -> RGBA（15 色，<=16）
    (0, 0, 0, 0),           # 0  透明
    (34, 30, 44, 255),      # 1  描边深色
    (63, 163, 77, 255),     # 2  青绿主色 #3FA34D
    (111, 217, 122, 255),   # 3  亮部     #6FD97A
    (42, 122, 60, 255),     # 4  暗部     #2A7A3C
    (240, 245, 238, 255),   # 5  白（高光/水渍亮/眼高光）
    (26, 90, 50, 255),      # 6  深绿内核
    (150, 52, 58, 255),     # 7  受击暗红（描边染色）
    (226, 74, 74, 255),     # 8  受击红（闪白帧描边）
    (168, 235, 150, 255),   # 9  淡绿（水渍/淡特效）
    (255, 236, 140, 255),   # 10 冲击黄
    (255, 255, 214, 255),   # 11 亮白黄（特效核心）
    (120, 220, 140, 255),   # 12 果冻边缘亮
    (22, 28, 30, 255),      # 13 眼睛深色
    (92, 60, 64, 255),      # 14 受击暗部红（暗部染色）
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']      # 自下而上合成

# ---- 锚点常量（写死，姿态只做相对偏移，绝不逐帧重算绝对坐标）----
CX = 16          # 身体水平中心
TOP_Y = 14       # 中立姿态头顶 y
BASE_Y = 27      # 中立姿态平底（接地面）y
FOOT_Y = 27      # 接地线
HALF_W = 11      # 中立姿态半宽（底宽 2*HALF_W = 22px）
DOME_H = BASE_Y - TOP_Y + 1         # 14 行（高度约 14px）


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
    return max(5, min(h, 24)), max(5, min(hw, 15))


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

    根部只埋进身体 inset 像素，避免粗壮的臂根把体内内核整片盖掉。
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
        hh = max(1, int(round(3.0 * (1 - frac) ** 0.5)))
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


# ---------------- 4. 四层绘制 ----------------
def draw_back(im, p):
    """back：底部接地阴影（腾空时收窄，凸显弹跳）。"""
    cx = CX + p['lean']
    lift = max(0, -p['dy'])
    sw = HALF_W + int(round(p['squash'] * 0.5)) - int(round(lift * 1.0))
    sw = max(3, min(15, sw))
    y = BASE_Y + 1
    hline(im, cx - sw, cx + sw, y, 1)
    hline(im, cx - sw + 3, cx + sw - 3, y + 1, 1)


def draw_body(im, p):
    """body：果冻主体 + 体内内核 + 眼睛。"""
    if p['puddle']:
        draw_puddle(im, p)
        return
    m = body_mask(p)
    if not m:
        return
    remap = p['remap']
    c = lambda i: remap.get(i, i)             # noqa: E731

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

    # 眼睛行（先算，内核要挂在它下面，避免压扁帧里眼/核粘成一团）
    eye_y = top + max(3, int(round(h * 0.36))) + p['eyeoff']
    ex_l, ex_r = cx - 6, cx - 1               # 整体偏左 => 面朝左

    def eye(mx, my, col):
        if (mx, my) in m and (mx, my) not in ring:
            setpx(im, mx, my, c(col))

    # 体内深绿内核（偏右下、挂在眼睛下方）。核本体落在暗部里，必须整圈包边才立得住：
    # 左上亮边 (12) + 右下暗边 (1)，否则只看得见一道亮弧，会被误读成嘴。
    if h >= 9 and eye_y + 5 <= base - 2:
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
                    eye(q[0], q[1], 12 if (dx <= 0 and dy <= 0) else 1)
        for (x, y) in core:
            eye(x, y, 6)

    # 眼睛（<=4px 小部件，绝不 outline，用深色 + 白色高光点）
    mode = p['eyes']
    if mode == 'open':
        for ex in (ex_l, ex_r):
            for k in range(3):
                for j in range(3):
                    eye(ex + j, eye_y + k, 13)
            eye(ex, eye_y, 5)                 # 眼高光
    elif mode == 'line':                      # 闪白帧：眼睛变横线
        for ex in (ex_l, ex_r):
            for j in range(3):
                eye(ex + j, eye_y + 1, 13)
    elif mode == 'closed':
        for ex in (ex_l, ex_r):
            for j in range(3):
                eye(ex + j, eye_y, 13)
    elif mode == 'x':                         # 受击/死亡：X 眼
        for ex in (ex_l, ex_r):
            eye(ex, eye_y, 13)
            eye(ex + 2, eye_y, 13)
            eye(ex + 1, eye_y + 1, 13)
            eye(ex, eye_y + 2, 13)
            eye(ex + 2, eye_y + 2, 13)


def draw_puddle(im, p):
    """death 末帧：只剩一滩浅色水渍 + 少量残留深色小点。"""
    cx = CX + p['lean']
    y0 = BASE_Y
    hline(im, cx - 12, cx + 11, y0, 9)
    hline(im, cx - 8, cx + 8, y0 - 1, 9)
    hline(im, cx - 4, cx + 4, y0 - 2, 12)
    hline(im, cx - 2, cx + 2, y0 - 3, 12)
    setpx(im, cx - 5, y0 - 1, 5)
    setpx(im, cx + 4, y0 - 1, 5)
    setpx(im, cx + 1, y0 - 2, 5)
    for x in (cx - 9, cx + 7, cx + 10, cx - 11):
        setpx(im, x, y0, 1)                   # 残留深色碎屑


def draw_weapon(im, p):
    """weapon：身前件 —— 向左甩出的伪足。与身体融合处不留描边。"""
    if p['reach'] <= 0 or p['puddle']:
        return
    m = pseudo_mask(p)
    if not m:
        return
    ring = outline_of(m)
    body = body_mask(p)
    remap = p['remap']

    def c(i):
        return remap.get(i, i)

    for (x, y) in m:                          # 先整块铺描边色
        setpx(im, x, y, c(1))
    for x, (yc, hh, _) in pseudo_cols(p).items():
        for k in range(-hh, hh + 1):
            y = yc + k
            if (x, y) not in m:
                continue
            if (x, y) in ring and (x, y) not in body:
                continue                      # 体外沿保留描边
            col = 3 if k < 0 else (4 if k > 0 else 2)
            setpx(im, x, y, c(col))
    # 尖端一点点亮（果冻拉伸反光）
    tip = pseudo_tip(p)
    if tip:
        setpx(im, tip[0], tip[1] - 1, c(12))


def draw_fx(im, p):
    """fx：命中冲击星 / 弹跳水花 / 消散粒子。"""
    kind = p['fx']
    cx = CX + p['lean']
    if kind == 'impact':
        tip = pseudo_tip(p)
        if not tip:
            return
        tx, ty = tip
        for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0)):
            setpx(im, tx + dx, ty + dy, 10)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (0, 0)):
            setpx(im, tx + dx, ty + dy, 11)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            setpx(im, tx + dx, ty + dy, 10)
        setpx(im, tx - 1, ty - 3, 9)          # 上方弧光
        setpx(im, tx, ty - 3, 5)
        setpx(im, tx + 1, ty - 3, 9)
    elif kind == 'droplet':                   # 弹跳起落的水花
        y = BASE_Y + p['dy'] + 1
        for dx, dy, col in ((-13, 0, 3), (-14, -1, 9), (-12, -2, 5),
                            (13, 0, 3), (14, -1, 9), (12, -2, 5)):
            setpx(im, cx + dx, y + dy, col)
    elif kind == 'dissipate':                 # 死亡末帧：向上飘散的粒子
        for x, y, col in ((cx - 6, BASE_Y - 6, 5), (cx - 2, BASE_Y - 9, 9),
                          (cx + 3, BASE_Y - 7, 12), (cx + 6, BASE_Y - 11, 9),
                          (cx + 1, BASE_Y - 13, 5), (cx - 4, BASE_Y - 12, 12)):
            setpx(im, x, y, col)


# ---------------- 5. 动作表（统一走 pose() 一个入口）----------------
def pose(dy=0, lean=0, squash=0, wobble=0, eyes='open', eyeoff=0, reach=0,
         flash=0, tint=0, puddle=0, fx=None):
    p = dict(dy=dy, lean=lean, squash=squash, wobble=wobble, eyes=eyes,
             eyeoff=eyeoff, reach=reach, flash=flash, tint=tint,
             puddle=puddle, fx=fx)
    remap = {}
    if flash:                                 # 受击闪白：描边转红、主体转白
        p['eyes'] = 'line'
        remap = {1: 8, 2: 5, 3: 5, 4: 5, 6: 5, 12: 5}
    elif tint:                                # 带一点受击暗红
        remap = {1: 7, 4: 14}
    p['remap'] = remap
    return p


# move：压扁蓄力 -> 弹起拉伸离地 -> 落地压扁 -> 回弹中立（收尾接近起始）
MOVE = [
    pose(dy=0, squash=2, wobble=1, eyes='open'),
    pose(dy=-6, squash=-3, wobble=-2, eyes='open', fx='droplet'),
    pose(dy=1, squash=4, wobble=2, eyes='open'),
    pose(dy=-1, squash=-1, wobble=-1, eyes='open'),
]
# attack：后缩蓄力 -> 伪足甩出（拉长）-> 命中（伪足最前 + 冲击星）-> 收回
ATTACK = [
    pose(dy=1, lean=3, squash=2, wobble=-2, eyes='open', reach=0),
    pose(dy=-1, lean=2, squash=0, wobble=1, eyes='open', reach=5),
    pose(dy=-1, lean=4, squash=-2, wobble=2, eyes='open', reach=7, fx='impact'),
    pose(dy=0, lean=3, squash=1, wobble=-2, eyes='open', reach=3),
]
# hit：第 0 帧闪白压扁（横线眼）-> 第 1 帧回弹带暗红
HIT = [
    pose(dy=0, lean=1, squash=3, wobble=1, flash=1),
    pose(dy=-1, lean=0, squash=-2, wobble=-1, eyes='open', tint=1, eyeoff=1),
]
# death：受击抖 -> 塌陷变矮 -> 摊成一滩（最扁最宽）-> 只剩水渍 + 飘散粒子
DEATH = [
    pose(dy=0, lean=-1, squash=1, wobble=2, eyes='x', tint=1),
    pose(dy=0, lean=-1, squash=4, wobble=1, eyes='closed'),
    pose(dy=0, lean=0, squash=7, wobble=0, eyes='closed', eyeoff=-1),
    pose(dy=0, lean=0, puddle=1, fx='dissipate'),
]

ACTIONS = {'move': MOVE, 'attack': ATTACK, 'hit': HIT, 'death': DEATH}


# ---------------- 6. 渲染 + 导出 ----------------
def render_frame(p):
    layers = {}
    im = new_layer(); draw_back(im, p);    layers['back'] = im
    im = new_layer(); draw_body(im, p);    layers['body'] = im
    im = new_layer(); draw_weapon(im, p);  layers['weapon'] = im
    im = new_layer(); draw_fx(im, p);      layers['fx'] = im
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for name in LAYER_ORDER:
        sp = layers[name].load()
        for yy in range(SIZE):
            for xx in range(SIZE):
                if sp[xx, yy]:
                    px[xx, yy] = PALETTE[sp[xx, yy]]
    return out


def export(pack, out_dir):
    if out_dir.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{out_dir}')
    (out_dir / 'frames').mkdir(parents=True)
    frames, imgs = [], []
    for action in PACKS[pack]:
        for i, p in enumerate(ACTIONS[action]):
            im = render_frame(p)
            fid = f'{action}_{i}'
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
          f'颜色数={len(PALETTE)}  帧间差异校验=PASS')
    print('   帧清单: ' + ', '.join(f['id'] for f in frames))


if __name__ == '__main__':
    packs = [PACK] if PACK else list(PACKS)
    for pk in packs:
        if pk not in PACKS:
            raise SystemExit(f'未知包名 {pk}，可选：{list(PACKS)}')
        export(pk, BASE / f'{NAME}-{PACK_SUFFIX[pk]}{REV}')
    print('下一步：真实打开 contact-sheet-8x.png 目检轮廓/姿态差异/部位一致/不截断')
