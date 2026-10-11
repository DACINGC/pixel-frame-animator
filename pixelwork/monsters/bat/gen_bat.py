# -*- coding: utf-8 -*-
"""
洞穴蝙蝠（Bat）—— 32x32 像素帧动画生成脚本
从 frame_anim_template.py 复制改造（原模板未做任何修改）。

用法：
  PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
  "$PY" gen_bat.py <outdir> locomotion     # move_0..3 + hit_0..1
  "$PY" gen_bat.py <outdir> combat         # attack_0..3 + death_0..3
"""
import hashlib, json, sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32                                   # 硬性：四个怪物统一 32x32，禁止改 64
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / 'bat-output'
PACK = sys.argv[2] if len(sys.argv) > 2 else None

PALETTE = [                                  # 索引 -> RGBA（16 色，0 透明，其余 alpha=255）
    (0, 0, 0, 0),        # 0  透明
    (34, 30, 44, 255),   # 1  描边深色
    (107, 78, 158, 255), # 2  主色紫   #6B4E9E
    (155, 127, 212, 255),# 3  主色亮部 #9B7FD4
    (67, 47, 107, 255),  # 4  主色暗部 #432F6B
    (240, 240, 248, 255),# 5  白（獠牙 / 闪白 / 高光）
    (150, 138, 190, 255),# 6  翼膜亮紫灰（近翼）
    (96, 84, 132, 255),  # 7  翼膜暗紫灰（远翼）
    (198, 70, 70, 255),  # 8  红（受击描边 / 伤痕）
    (122, 59, 94, 255),  # 9  内耳 / 口腔 暗紫红
    (72, 32, 58, 255),   # 10 口腔深处
    (245, 210, 90, 255), # 11 眼睛亮黄
    (168, 226, 255, 255),# 12 特效青白
    (198, 178, 236, 255),# 13 淡紫（速度线 / 残影）
    (186, 156, 224, 255),# 14 尘埃紫
    (58, 42, 80, 255),   # 15 残骸暗紫
]

LAYER_ORDER = ['back', 'body', 'weapon', 'fx']
PACKS = {'locomotion': ['move', 'hit'], 'combat': ['attack', 'death']}

# ---------------- 2. 锚点常量（写死，姿态只做相对偏移） ----------------
TOP_Y   = 7     # 耳尖所在行（轮廓最高点）
BASE_Y  = 16    # 身体重心行：压扁 / 翻转 / 落地的变换中心
CLAW_Y  = 23    # 爪根所在行
WSX, WSY = 14, 14   # 翅根（肩点）
AXIS = 31           # 左右镜像轴：rx = AXIS - lx（轴心 x=15.5）
BODY_CX = 15.5      # 身体水平中心（与镜像轴一致）

# ---------------- 3. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)

def rect(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)

def ell(d, box, c, outline=None):
    d.ellipse(box, fill=c, outline=outline)

def seg(d, pts, c, w=1):
    d.line(pts, fill=c, width=w)

def mir(pts):                       # 以 x=15.5 为轴左右镜像
    return [(AXIS - x, y) for x, y in pts]

def off(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]

def sq(pts, s):                     # 压扁：以 (BODY_CX, BASE_Y) 为中心纵向压缩 / 横向拉伸
    if not s:
        return pts
    return [(int(round(BODY_CX + (x - BODY_CX) * 1.12)),
             int(round(BASE_Y + (y - BASE_Y) * 0.82))) for x, y in pts]

# ---------------- 4. 造型：身体轮廓 ----------------
# 单个多边形囊括 头+躯干+吻+双耳，避免部件拼接产生内部描边缝
def body_sil(ear):
    if ear:                          # 耳后掠（蓄力 / 受击 / 失衡）
        return [(10, 13), (14, 9), (14, 12), (15, 13), (16, 12), (20, 9), (21, 13),
                (22, 16), (22, 19), (21, 22), (17, 23), (14, 21), (13, 20),
                (10, 20), (9, 18), (10, 15)]
    return [(10, 13), (12, TOP_Y), (14, 12), (15, 13), (16, 12), (19, TOP_Y), (21, 13),
            (22, 16), (22, 19), (21, 22), (17, 23), (14, 21), (13, 20),
            (10, 20), (9, 18), (10, 15)]

INNER_EAR_L = [[(12, 9), (13, 12), (11, 12)], [(13, 10), (14, 12), (12, 12)]]
INNER_EAR_R = [[(19, 9), (20, 12), (18, 12)], [(20, 10), (20, 12), (18, 12)]]
SHADOW      = [(16, 18), (20, 17), (20, 20), (17, 21), (15, 20)]
MOUTH       = [(10, 17), (13, 17), (13, 19), (10, 19)]
MOUTH_OPEN  = [(10, 16), (13, 16), (14, 18), (13, 19), (10, 19)]

# ---------------- 5. 造型：翅膀（back 层） ----------------
# 0=完全展开上扬  1=平展（中）  2=完全下压  3=收起折叠
WING = {
    0: [(14, 13), (11, 10), (6, 7), (3, 7), (4, 11), (7, 13), (10, 16), (14, 17)],
    1: [(14, 13), (11, 11), (7, 11), (3, 13), (4, 16), (7, 17), (10, 18), (14, 18)],
    2: [(14, 14), (11, 15), (8, 18), (5, 21), (6, 24), (9, 22), (11, 21), (14, 19)],
    3: [(14, 14), (11, 15), (9, 18), (8, 21), (9, 23), (11, 22), (13, 20), (14, 18)],
}
BONE = {                             # 每条翼 2 根翅骨线的终点（起点=翅根）
    0: [(3, 7), (7, 13)],
    1: [(3, 13), (7, 17)],
    2: [(5, 21), (9, 22)],
    3: [(8, 21), (9, 18)],
}
WRAP_L   = [(13, 12), (10, 13), (8, 15), (8, 18), (10, 20), (13, 20), (13, 17)]   # 蜷缩：翼紧贴包裹身体
WRAP_BONE = [(13, 13), (8, 17)]

# 咬击特效（绝对坐标手绘像素月牙 + 冲击星；Pillow arc 在小半径下会断成珠链，弃用）
BITE_ARC   = [(6, 12), (5, 13), (4, 14), (3, 15), (2, 16), (2, 18), (3, 19), (4, 20), (5, 21), (6, 22)]
BITE_INNER = [(6, 13), (5, 14), (4, 15), (3, 16), (3, 18), (4, 19), (5, 20), (6, 21)]
BITE_STAR  = (3, 17)
CURL_BALL = (10, 12, 21, 20)
CURL_EAR_L = [(12, 10), (14, 13), (11, 13)]
CURL_EAR_R = [(19, 10), (17, 13), (20, 13)]

# ---------------- 6. 造型：粒子（fx 层） ----------------
SPECKS = [(15, 26), (16, 26), (15, 27)]                                  # 残骸
DUST   = [(12, 24), (18, 23), (13, 21), (17, 20), (20, 25), (11, 27), (19, 28), (14, 29)]

# ---------------- 7. 图层绘制 ----------------
def draw_back(d, p):
    dx, dy, fl = p['lean'], p['dy'], p['flash']
    if p['vanish']:
        return
    mfill = 5 if fl else 7            # 远翼（右，镜像）
    nfill = 5 if fl else 6            # 近翼（左）
    ocol  = 8 if fl else 1
    bcol  = 8 if fl else 4
    if p['curl']:                     # 死亡蜷缩：双翼包裹身体（近翼亮 / 远翼暗）
        d.polygon(off(WRAP_L, dx, dy), fill=nfill, outline=ocol)
        d.polygon(off(mir(WRAP_L), dx, dy), fill=mfill, outline=ocol)
        seg(d, [(WRAP_BONE[0][0] + dx, WRAP_BONE[0][1] + dy),
                (WRAP_BONE[1][0] + dx, WRAP_BONE[1][1] + dy)], bcol, 1)
        seg(d, [(AXIS - WRAP_BONE[0][0] + dx, WRAP_BONE[0][1] + dy),
                (AXIS - WRAP_BONE[1][0] + dx, WRAP_BONE[1][1] + dy)], bcol, 1)
        return
    # 远翼（镜像到右侧，再向右上偏移 1px 制造纵深）
    wi = p['wingR'] if p['wingR'] is not None else p['wing']
    d.polygon(off(mir(WING[wi]), dx + 1, dy - 1), fill=mfill, outline=ocol)
    for bx, by in BONE[wi]:
        seg(d, [(WSX + 1 + dx, WSY - 1 + dy), (AXIS - bx + 1 + dx, by - 1 + dy)], bcol, 1)
    # 近翼
    wi = p['wing']
    d.polygon(off(WING[wi], dx, dy), fill=nfill, outline=ocol)
    for bx, by in BONE[wi]:
        seg(d, [(WSX + dx, WSY + dy), (bx + dx, by + dy)], bcol, 1)

def draw_body(d, p):
    dx, dy, fl = p['lean'], p['dy'], p['flash']
    if p['vanish']:
        return
    C_MAIN = 5 if fl else 2
    C_LIT  = 5 if fl else 3
    C_DARK = 8 if fl else (8 if p['hurt'] else 4)
    C_OUT  = 8 if fl else 1
    C_IN   = 5 if fl else 9
    if p['curl']:                     # 蜷成一小团
        x0, y0, x1, y1 = CURL_BALL
        ell(d, (x0 + dx, y0 + dy, x1 + dx, y1 + dy), C_MAIN, outline=C_OUT)
        for tri in (CURL_EAR_L, CURL_EAR_R):
            d.polygon(off(tri, dx, dy), fill=C_MAIN, outline=C_OUT)
        rect(d, (12 + dx, 15 + dy, 14 + dx, 15 + dy), C_OUT)     # 闭眼横线
        rect(d, (17 + dx, 15 + dy, 19 + dx, 15 + dy), C_OUT)
        return
    d.polygon(off(sq(body_sil(p['ear']), p['squash']), dx, dy), fill=C_MAIN, outline=C_OUT)
    d.polygon(off(INNER_EAR_L[p['ear']], dx, dy), fill=C_IN)
    d.polygon(off(INNER_EAR_R[p['ear']], dx, dy), fill=C_IN)
    ell(d, (12 + dx, 14 + dy, 19 + dx, 19 + dy), C_LIT)          # 亮部
    d.polygon(off(SHADOW, dx, dy), fill=C_DARK)                  # 暗部
    if fl:                                                        # 受击：眼睛变横线
        rect(d, (12 + dx, 15 + dy, 13 + dx, 15 + dy), 1)
        rect(d, (16 + dx, 15 + dy, 17 + dx, 15 + dy), 1)
    else:
        rect(d, (12 + dx, 14 + dy, 13 + dx, 15 + dy), 11)         # 左眼（2px，不描边）
        rect(d, (12 + dx, 16 + dy, 13 + dx, 16 + dy), 1)          # 单侧暗线定位
        rect(d, (16 + dx, 14 + dy, 17 + dx, 15 + dy), 11)         # 右眼
        rect(d, (16 + dx, 16 + dy, 17 + dx, 16 + dy), 1)
    d.polygon(off(MOUTH_OPEN if p['open'] else MOUTH, dx, dy), fill=C_IN)
    rect(d, (11 + dx, 18 + dy, 12 + dx, 19 + dy), 10)             # 口腔深处
    if p['hurt']:
        rect(d, (12 + dx, 17 + dy, 13 + dx, 17 + dy), 8)          # 受击暗红

def draw_weapon(d, p):
    dx, dy = p['lean'], p['dy']
    if p['vanish'] or p['curl']:
        return
    flen = 22 if p['open'] else 21                                # 獠牙（1px 宽，不描边）
    for fx0 in (10, 12):
        rect(d, (fx0 + dx, 20 + dy, fx0 + dx, flen + dy), 5)
    for cx0 in (15, 19):                                          # 倒挂小挂钩爪
        seg(d, [(cx0 + dx, CLAW_Y - 1 + dy), (cx0 + dx, CLAW_Y + 1 + dy)], 1, 1)
        rect(d, (cx0 - 1 + dx, CLAW_Y + 1 + dy, cx0 - 1 + dx, CLAW_Y + 1 + dy), 1)

def draw_fx(d, p):
    k, dx, dy = p['fx'], p['lean'], p['dy']
    if k is None:
        return
    if k == 'bite':                   # 命中特效用屏幕绝对坐标（本体已前冲到最左，特效不随 lean 再移）
        dx = 0
    if k == 'bite':                   # 咬击弧光（手绘像素月牙，避免 Pillow arc 的断点）+ 冲击星
        for x, y in BITE_ARC:
            rect(d, (x + dx, y + dy, x + dx, y + dy), 12)
        for x, y in BITE_INNER:
            rect(d, (x + dx, y + dy, x + dx, y + dy), 5)
        sx, sy = BITE_STAR
        rect(d, (sx + dx, sy - 1 + dy, sx + dx, sy + 1 + dy), 5)
        rect(d, (sx - 1 + dx, sy + dy, sx + 1 + dx, sy + dy), 5)
        rect(d, (sx + dx, sy - 2 + dy, sx + dx, sy - 2 + dy), 12)
        rect(d, (sx + dx, sy + 2 + dy, sx + dx, sy + 2 + dy), 12)
        rect(d, (sx - 2 + dx, sy + dy, sx - 2 + dx, sy + dy), 12)
        rect(d, (sx + 2 + dx, sy + dy, sx + 2 + dx, sy + dy), 12)
    elif k == 'dash':                                             # 前冲速度线（身后缀）
        seg(d, [(24 + dx, 13 + dy), (29 + dx, 13 + dy)], 13, 1)
        seg(d, [(25 + dx, 16 + dy), (30 + dx, 16 + dy)], 13, 1)
        seg(d, [(24 + dx, 19 + dy), (28 + dx, 19 + dy)], 13, 1)
    elif k == 'puff':                                             # 收势余尘（离脸远一点、低一点）
        ell(d, (2 + dx, 21 + dy, 6 + dx, 24 + dy), 14)
        ell(d, (5 + dx, 23 + dy, 8 + dx, 25 + dy), 14)
        rect(d, (3 + dx, 20 + dy, 4 + dx, 20 + dy), 3)
    elif k == 'fall':                                             # 下坠拖线
        seg(d, [(13 + dx, 3 + dy), (13 + dx, 7 + dy)], 13, 1)
        seg(d, [(18 + dx, 2 + dy), (18 + dx, 6 + dy)], 13, 1)
        seg(d, [(21 + dx, 4 + dy), (21 + dx, 7 + dy)], 13, 1)
    elif k == 'poof':                                             # 死亡最后一帧：残骸 + 尘埃
        for x, y in SPECKS:
            rect(d, (x, y, x, y), 15)
        for x, y in DUST:
            rect(d, (x, y, x, y), 14)

# ---------------- 8. 动作表 ----------------
def pose(dy=0, lean=0, wing=1, wingR=None, ear=0, squash=0, flash=0,
         open=0, hurt=0, curl=0, vanish=0, fx=None):
    return {'dy': dy, 'lean': lean, 'wing': wing, 'wingR': wingR, 'ear': ear,
            'squash': squash, 'flash': flash, 'open': open, 'hurt': hurt,
            'curl': curl, 'vanish': vanish, 'fx': fx}

ACTIONS = {
    # 振翅飞行（循环）：翼上扬(体最高) → 翼平展(体下沉) → 翼下压(推进/前移) → 翼回中(上升)
    'move': [pose(dy=-2, wing=0, wingR=0, ear=0),
             pose(dy=1,  wing=1, wingR=1, ear=0),
             pose(dy=0,  lean=1, wing=2, wingR=2, ear=1),
             pose(dy=-1, wing=1, wingR=0, ear=1)],
    # 俯冲咬击：后仰蓄力(翼收/体右移) → 前冲(翼后掠) → 命中(獠牙最前+弧光) → 收势
    'attack': [pose(dy=-1, lean=2,  wing=3, wingR=3, ear=1),
               pose(dy=-1, lean=-1, wing=2, wingR=1, ear=1, open=1, fx='dash'),
               pose(dy=0,  lean=-2, wing=1, wingR=1, ear=1, open=1, fx='bite'),
               pose(dy=1,  lean=-1, wing=3, wingR=2, ear=0, fx='puff')],
    # 受击：闪白压扁 → 回弹带伤
    'hit': [pose(dy=1,  lean=1, wing=2, wingR=2, ear=1, squash=1, flash=1),
            pose(dy=-1, lean=1, wing=0, wingR=1, ear=0, hurt=1)],
    # 死亡：翻转失衡 → 下坠 → 落地缩成团 → 残骸 + 尘埃
    'death': [pose(dy=-1, lean=1, wing=0, wingR=2, ear=1, fx='fall'),
              pose(dy=3,  lean=0, wing=2, wingR=2, ear=1, fx='fall'),
              pose(dy=5,  lean=0, curl=1),
              pose(dy=0,  lean=0, vanish=1, fx='poof')],
}

# ---------------- 9. 渲染 + 导出 ----------------
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
    acts = ACTIONS
    if PACK:
        if PACK not in PACKS:
            raise SystemExit(f'未知包：{PACK}，可选 {list(PACKS)}')
        acts = {k: ACTIONS[k] for k in PACKS[PACK]}
    if OUT.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{OUT}')
    (OUT / 'frames').mkdir(parents=True)
    imgs, frames, sheet_w = [], [], 0
    for action, poses in acts.items():
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
        OUT / 'contact-sheet-8x.png')
    atlas = {'size': [sheet_w, SIZE], 'frame_size': SIZE, 'palette_size': len(PALETTE),
             'layer_order': LAYER_ORDER, 'pack': PACK, 'frames': frames}
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
    print(f'OK -> {OUT}  包={PACK}  帧={[f["id"] for f in frames]}')
    print(f'    画布={SIZE}  颜色数={len(PALETTE)}  帧间差异校验=PASS')

if __name__ == '__main__':
    export()
