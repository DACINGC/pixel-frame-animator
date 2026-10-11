# -*- coding: utf-8 -*-
"""生成 32x32 骷髅小兵的逐帧像素动画交付包。"""
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# ---------------- 1. 配置 ----------------
SIZE = 32
TOP_Y = 5
WAIST_Y = 19
FOOT_Y = 27
TORSO_X = 16
SHOULDER_X = 18
SHOULDER_Y = 14

PALETTE = [
    (0, 0, 0, 0),          # 0 透明
    (34, 30, 44, 255),     # 1 描边 / 眼窝
    (232, 227, 208, 255),  # 2 骨白
    (255, 251, 240, 255),  # 3 骨亮
    (168, 160, 138, 255),  # 4 骨暗
    (255, 255, 255, 255),  # 5 受击闪白 / 弧光亮部
    (116, 31, 42, 255),    # 6 暗红魂火
    (211, 67, 72, 255),    # 7 亮红魂火
    (138, 79, 53, 255),    # 8 锈褐
    (101, 47, 53, 255),    # 9 破布暗红
    (112, 75, 54, 255),    # 10 破布褐
    (119, 118, 125, 255),  # 11 灰刃
    (182, 179, 170, 255),  # 12 灰刃亮部
    (163, 54, 63, 255),    # 13 受击红描边
    (232, 201, 138, 255),  # 14 斩击弧光
    (118, 108, 101, 255),  # 15 尘埃
]
LAYER_ORDER = ['back', 'body', 'weapon', 'fx']
PACKS = {'locomotion': ['move', 'hit'], 'combat': ['attack', 'death']}
PACK_DIR_NAMES = {
    'locomotion': 'skeleton-move-hit',
    'combat': 'skeleton-attack-death',
}

# ---------------- 2. 绘制原语 ----------------
def new_layer():
    return Image.new('P', (SIZE, SIZE), 0)


def rect(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)


def ell(d, box, c, outline=None):
    d.ellipse(box, fill=c, outline=outline)


def seg(d, pts, c, w=1):
    d.line(pts, fill=c, width=w)


def body_colors(p):
    if p['flash']:
        return 5, 5, 5, 13
    return 2, 3, 4, 1


def bone_seg(d, pts, p, width=1):
    bone, bright, _, outline = body_colors(p)
    seg(d, pts, outline, width + 2)
    seg(d, pts, bright if width == 1 else bone, width)


def upper_shift(p):
    return p['lean'], p['dy'] + p['torso_bob']


def hand_anchor(p):
    ux, uy = upper_shift(p)
    return SHOULDER_X + ux + p['arm'][0], SHOULDER_Y + uy + p['arm'][1]


# ---------------- 3. 角色造型 ----------------
def draw_back(d, p):
    if p['stage'] in ('scattered', 'remains'):
        return
    ux, uy = upper_shift(p)
    wx = TORSO_X + ux
    wy = WAIST_Y + uy
    swing = p['cloth']
    d.polygon(
        [(wx + 2, wy), (wx + 5, wy + 1),
         (wx + 6 + swing, wy + 5), (wx + 3 + swing, wy + 4)],
        fill=10,
        outline=1,
    )
    seg(d, [(wx + 4, wy + 1), (wx + 5 + swing, wy + 4)], 9, 1)


def draw_skull(d, p, extra_x=0, extra_y=0):
    bone, bright, dark, outline = body_colors(p)
    ux, uy = upper_shift(p)
    x = 11 + ux + extra_x
    y = TOP_Y + uy + p['head_bob'] + extra_y
    squash = p['squash']
    bottom = y + 9 - squash

    d.polygon(
        [(x + 2, y), (x + 7, y), (x + 9, y + 2),
         (x + 9, y + 5), (x + 7, y + 7 - squash),
         (x + 6, bottom), (x, bottom), (x - 1, y + 7 - squash),
         (x, y + 5), (x, y + 2)],
        fill=bone,
        outline=outline,
    )
    rect(d, (x + 2, y + 1, x + 6, y + 1), bright)
    rect(d, (x + 8, y + 3, x + 8, y + 5), dark)

    # 小部件不描边：两个黑眼窝、1px 魂火与鼻孔。
    rect(d, (x + 1, y + 3, x + 3, y + 5), 1)
    rect(d, (x + 5, y + 3, x + 7, y + 5), 1)
    soul = 7 if (p['flash'] or p['soul_bright']) else 6
    rect(d, (x + 1, y + 4, x + 1, y + 4), soul)
    rect(d, (x + 5, y + 4, x + 5, y + 4), soul)
    rect(d, (x, y + 6, x, y + 6), 1)

    # 牙缝：一条横暗线加三条 1px 竖缝。
    teeth_y = bottom - 1
    seg(d, [(x, teeth_y), (x + 6, teeth_y)], dark, 1)
    for tx in (x + 1, x + 3, x + 5):
        rect(d, (tx, teeth_y, tx, bottom), outline)
    if p['bruise']:
        rect(d, (x + 8, y + 6, x + 8, y + 6), 6)
        rect(d, (x + 7, y + 7 - squash, x + 7, y + 7 - squash), 9)


def draw_ribcage(d, p):
    bone, bright, dark, outline = body_colors(p)
    ux, uy = upper_shift(p)
    sx = TORSO_X + ux
    neck_y = SHOULDER_Y + uy
    waist_y = WAIST_Y + uy

    bone_seg(d, [(sx, neck_y - 1), (sx, waist_y + 1)], p)
    rect(d, (sx, neck_y - 1, sx, neck_y - 1), bright)
    # 三根露出肋骨横线，左右长度逐渐收窄。
    ribs = [(-4, 4, 1), (-4, 4, 3), (-3, 3, 5)]
    for left, right, off in ribs:
        ry = neck_y + off
        seg(d, [(sx + left, ry), (sx, ry + 1), (sx + right, ry)], outline, 3)
        seg(d, [(sx + left + 1, ry), (sx, ry + 1), (sx + right - 1, ry)], bone, 1)
    rect(d, (sx - 1, neck_y + 2, sx, waist_y), dark)

    # 破布腰带与骨盆。
    d.polygon(
        [(sx - 4, waist_y), (sx + 4, waist_y),
         (sx + 3, waist_y + 3), (sx - 3, waist_y + 3)],
        fill=dark,
        outline=outline,
    )
    rect(d, (sx - 4, waist_y, sx + 4, waist_y + 1), 9, outline=1)
    rect(d, (sx, waist_y, sx + 1, waist_y + 1), 10)
    if p['bruise']:
        rect(d, (sx - 4, neck_y + 3, sx - 3, neck_y + 3), 6)


def leg_points(p):
    foot_y = FOOT_Y + p['dy']
    if p['legs'] == 1:       # 左腿迈向面朝方向
        return ((12, 24, 9, foot_y), (18, 24, 20, foot_y))
    if p['legs'] == 2:       # 右腿迈出，双腿形成明显交错
        return ((17, 24, 20, foot_y), (14, 24, 10, foot_y))
    if p['legs'] == 3:       # 抬起过渡
        return ((13, 23, 11, foot_y - 2), (18, 24, 19, foot_y))
    if p['legs'] == 4:       # 后仰 / 蓄力时宽站姿
        return ((13, 24, 10, foot_y), (19, 24, 22, foot_y))
    return ((14, 24, 13, foot_y), (18, 24, 19, foot_y))


def draw_legs(d, p):
    ux, uy = upper_shift(p)
    hip_y = WAIST_Y + uy + 2
    hips = ((TORSO_X + ux - 2, hip_y), (TORSO_X + ux + 2, hip_y))
    for (hx, hy), (kx, ky, fx, fy) in zip(hips, leg_points(p)):
        bone_seg(d, [(hx, hy), (kx, ky)], p)
        bone_seg(d, [(kx, ky), (fx, fy)], p)
        _, bright, _, outline = body_colors(p)
        rect(d, (kx, ky, kx, ky), bright)
        direction = -1 if fx <= kx else 1
        seg(d, [(fx, fy), (fx + 2 * direction, fy)], outline, 3)
        seg(d, [(fx, fy), (fx + 2 * direction, fy)], bright, 1)


def draw_arm(d, p):
    ux, uy = upper_shift(p)
    shoulder = (SHOULDER_X + ux, SHOULDER_Y + uy)
    hand = hand_anchor(p)
    elbow = (
        round((shoulder[0] + hand[0]) / 2) + p['elbow'][0],
        round((shoulder[1] + hand[1]) / 2) + p['elbow'][1],
    )
    bone_seg(d, [shoulder, elbow], p)
    bone_seg(d, [elbow, hand], p)
    _, bright, _, outline = body_colors(p)
    rect(d, (elbow[0], elbow[1], elbow[0], elbow[1]), bright)
    rect(d, (hand[0] - 1, hand[1] - 1, hand[0] + 1, hand[1] + 1), outline)
    rect(d, (hand[0], hand[1], hand[0], hand[1]), bright)


def draw_scattered_body(d, p):
    bone, bright, dark, outline = body_colors(p)
    # 落地头骨。
    d.polygon(
        [(5, 22), (7, 20), (12, 20), (14, 22),
         (13, 25), (9, 26), (6, 25)],
        fill=bone,
        outline=outline,
    )
    rect(d, (7, 22, 8, 23), 1)
    rect(d, (10, 22, 11, 23), 1)
    rect(d, (7, 24, 11, 24), dark)
    # 横七竖八的长骨、肋骨与骨盆。
    bone_seg(d, [(15, 23), (21, 27)], p)
    bone_seg(d, [(11, 28), (17, 27)], p)
    bone_seg(d, [(19, 22), (25, 21)], p)
    seg(d, [(15, 25), (18, 24), (21, 25)], outline, 3)
    seg(d, [(16, 25), (18, 24), (20, 25)], bone, 1)
    rect(d, (23, 26, 25, 28), dark, outline=outline)
    rect(d, (17, 27, 17, 27), bright)


def draw_remains(d, p):
    _, bright, dark, outline = body_colors(p)
    bone_seg(d, [(8, 27), (13, 26)], p)
    bone_seg(d, [(19, 27), (22, 25)], p)
    rect(d, (15, 27, 17, 28), dark, outline=outline)
    rect(d, (6, 25, 6, 25), bright)
    rect(d, (24, 28, 24, 28), bright)


def draw_body(d, p):
    if p['stage'] == 'scattered':
        draw_scattered_body(d, p)
        return
    if p['stage'] == 'remains':
        draw_remains(d, p)
        return

    draw_ribcage(d, p)
    draw_legs(d, p)
    draw_arm(d, p)
    if p['stage'] == 'head_fly':
        draw_skull(d, p, p['head_offset'][0], p['head_offset'][1])
    else:
        draw_skull(d, p)


def knife_geometry(anchor, blade, curve):
    hx, hy = anchor
    dx, dy = blade
    length = max(math.hypot(dx, dy), 1.0)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    base = (round(hx + ux * 2), round(hy + uy * 2))
    tip = (hx + dx, hy + dy)
    mid = (
        round(base[0] + (tip[0] - base[0]) * 0.55 + nx * curve),
        round(base[1] + (tip[1] - base[1]) * 0.55 + ny * curve),
    )
    return base, mid, tip, (nx, ny)


def draw_knife(d, anchor, blade, curve=1):
    base, mid, tip, normal = knife_geometry(anchor, blade, curve)
    hx, hy = anchor
    # 刀柄从手部锚点起画；手臂终点与这里共用 anchor。
    seg(d, [anchor, base], 1, 3)
    seg(d, [anchor, base], 8, 1)
    guard_a = (round(base[0] + normal[0] * 2), round(base[1] + normal[1] * 2))
    guard_b = (round(base[0] - normal[0] * 2), round(base[1] - normal[1] * 2))
    seg(d, [guard_a, guard_b], 1, 3)
    seg(d, [guard_a, guard_b], 8, 1)

    # 弯刀轮廓、灰刃、亮刃与锈斑。
    seg(d, [base, mid, tip], 1, 4)
    seg(d, [base, mid, tip], 11, 2)
    seg(d, [mid, tip], 12, 1)
    rust_a = (round(base[0] * 0.45 + mid[0] * 0.55), round(base[1] * 0.45 + mid[1] * 0.55))
    rust_b = (round(mid[0] * 0.4 + tip[0] * 0.6), round(mid[1] * 0.4 + tip[1] * 0.6))
    rect(d, (rust_a[0], rust_a[1], rust_a[0], rust_a[1]), 8)
    rect(d, (rust_b[0], rust_b[1], rust_b[0], rust_b[1]), 8)
    rect(d, (hx, hy, hx, hy), 3)


def draw_weapon(d, p):
    if p['stage'] == 'remains':
        return
    if p['stage'] == 'scattered':
        draw_knife(d, (24, 25), (-8, 2), curve=-1)
        return
    draw_knife(d, hand_anchor(p), p['blade'], p['blade_curve'])


def draw_fx(d, p):
    if p['fx'] == 'slash':
        d.arc((1, 7, 16, 24), 105, 250, fill=14, width=2)
        d.arc((3, 9, 15, 22), 110, 245, fill=5, width=1)
        rect(d, (2, 13, 2, 13), 5)
        rect(d, (4, 21, 4, 21), 14)
    elif p['fx'] == 'scatter_dust':
        rect(d, (3, 27, 4, 27), 15)
        rect(d, (26, 25, 27, 25), 15)
        rect(d, (21, 29, 21, 29), 4)
    elif p['fx'] == 'dust':
        rect(d, (4, 27, 4, 27), 15)
        rect(d, (11, 29, 12, 29), 15)
        rect(d, (20, 24, 20, 24), 4)
        rect(d, (26, 27, 26, 27), 15)


# ---------------- 4. 动作表 ----------------
def pose(
    dy=0,
    lean=0,
    squash=0,
    flash=0,
    fx=None,
    torso_bob=0,
    head_bob=0,
    legs=0,
    arm=(-7, 4),
    elbow=(0, 0),
    blade=(-5, 4),
    blade_curve=1,
    cloth=0,
    soul_bright=0,
    bruise=0,
    stage='normal',
    head_offset=(0, 0),
):
    return {
        'dy': dy,
        'lean': lean,
        'squash': squash,
        'flash': flash,
        'fx': fx,
        'torso_bob': torso_bob,
        'head_bob': head_bob,
        'legs': legs,
        'arm': arm,
        'elbow': elbow,
        'blade': blade,
        'blade_curve': blade_curve,
        'cloth': cloth,
        'soul_bright': soul_bright,
        'bruise': bruise,
        'stage': stage,
        'head_offset': head_offset,
    }


ACTIONS = {
    'move': [
        pose(torso_bob=0, head_bob=0, legs=1, arm=(-7, 4), elbow=(-1, 0), blade=(-5, 4), cloth=-1),
        pose(torso_bob=-1, head_bob=-1, legs=3, arm=(-6, 3), elbow=(0, -1), blade=(-4, 5), cloth=1),
        pose(torso_bob=0, head_bob=0, legs=2, arm=(-6, 4), elbow=(1, 0), blade=(-5, 3), cloth=0),
        pose(torso_bob=1, head_bob=0, legs=0, arm=(-7, 3), elbow=(-1, 0), blade=(-5, 4), cloth=-1),
    ],
    'attack': [
        pose(legs=0, arm=(3, -4), elbow=(0, -1), blade=(7, -5), blade_curve=1, cloth=1),
        pose(lean=1, torso_bob=1, legs=4, arm=(4, -4), elbow=(1, -1), blade=(5, -5), blade_curve=2, cloth=2),
        pose(lean=-1, legs=1, arm=(-9, 2), elbow=(-1, -1), blade=(-5, -2), blade_curve=-2, cloth=-1, fx='slash', soul_bright=1),
        pose(torso_bob=1, legs=0, arm=(-7, -2), elbow=(-1, -1), blade=(-5, -5), blade_curve=-1, cloth=0),
    ],
    'hit': [
        pose(lean=2, squash=1, flash=1, torso_bob=1, legs=4, arm=(-3, 4), elbow=(1, 0), blade=(-4, 4), cloth=2, soul_bright=1),
        pose(lean=1, head_bob=-1, legs=3, arm=(-6, 4), elbow=(0, 1), blade=(-5, 3), cloth=1, bruise=1, soul_bright=1),
    ],
    'death': [
        pose(lean=2, torso_bob=1, legs=4, arm=(-2, 5), elbow=(1, 1), blade=(4, 5), cloth=2, bruise=1, soul_bright=1),
        pose(lean=2, torso_bob=2, legs=3, arm=(3, 5), elbow=(1, 1), blade=(5, 4), cloth=2, bruise=1, stage='head_fly', head_offset=(-6, -5)),
        pose(stage='scattered', fx='scatter_dust'),
        pose(stage='remains', fx='dust'),
    ],
}

# ---------------- 5. 渲染与导出 ----------------
def validate_config():
    if SIZE != 32:
        raise SystemExit(f'SIZE 必须为 32，当前为 {SIZE}')
    if len(PALETTE) > 16:
        raise SystemExit(f'调色板超过 16 色：{len(PALETTE)}')
    if PALETTE[0] != (0, 0, 0, 0):
        raise SystemExit('调色板索引 0 必须透明')
    if PALETTE[1] != (34, 30, 44, 255):
        raise SystemExit('调色板索引 1 必须是共享描边色')
    if any(color[3] != 255 for color in PALETTE[1:]):
        raise SystemExit('除透明色外，调色板 alpha 必须全部为 255')
    expected = {'move': 4, 'attack': 4, 'hit': 2, 'death': 4}
    actual = {name: len(poses) for name, poses in ACTIONS.items()}
    if actual != expected:
        raise SystemExit(f'动作帧数不符合约定：{actual}')


def render_frame(p):
    layers = {}
    im = new_layer()
    draw_back(ImageDraw.Draw(im), p)
    layers['back'] = im
    im = new_layer()
    draw_body(ImageDraw.Draw(im), p)
    layers['body'] = im
    im = new_layer()
    draw_weapon(ImageDraw.Draw(im), p)
    layers['weapon'] = im
    im = new_layer()
    draw_fx(ImageDraw.Draw(im), p)
    layers['fx'] = im

    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for name in LAYER_ORDER:
        sp = layers[name].load()
        for yy in range(SIZE):
            for xx in range(SIZE):
                if sp[xx, yy]:
                    px[xx, yy] = PALETTE[sp[xx, yy]]
    return out


def export(out, pack_name):
    if out.exists():
        raise SystemExit(f'输出目录已存在，换一个新名字：{out}')
    if pack_name not in PACKS:
        raise SystemExit(f'未知包 {pack_name!r}，可选：{list(PACKS)}')
    (out / 'frames').mkdir(parents=True)

    frames = []
    imgs = []
    for action in PACKS[pack_name]:
        for i, p in enumerate(ACTIONS[action]):
            im = render_frame(p)
            fid = f'{action}_{i}'
            file_name = f'frames/{fid}.png'
            im.save(out / file_name)
            imgs.append((fid, im))
            frames.append({
                'id': fid,
                'action': action,
                'order': len(imgs) - 1,
                'file': file_name,
                'rect': [(len(imgs) - 1) * SIZE, 0, SIZE, SIZE],
                'rgba_sha256': hashlib.sha256(im.tobytes()).hexdigest(),
            })

    hashes = [frame['rgba_sha256'] for frame in frames]
    if len(set(hashes)) != len(hashes):
        duplicates = [frame['id'] for frame in frames if hashes.count(frame['rgba_sha256']) > 1]
        raise SystemExit(f'姿态重复，必须让每帧有真实差异：{duplicates}')
    if any(not image.getbbox() for _, image in imgs):
        raise SystemExit('存在空白帧，角色未绘制')
    allowed = set(PALETTE)
    for fid, image in imgs:
        used = set(image.getdata())
        if not used.issubset(allowed):
            raise SystemExit(f'{fid} 使用了调色板外颜色')

    sheet = Image.new('RGBA', (len(imgs) * SIZE, SIZE), (0, 0, 0, 0))
    for i, (_, image) in enumerate(imgs):
        sheet.paste(image, (i * SIZE, 0))
    sheet.save(out / 'sprite-sheet.png')
    sheet.resize(
        (sheet.width * 8, sheet.height * 8),
        Image.Resampling.NEAREST,
    ).save(out / 'contact-sheet-8x.png')

    atlas = {
        'size': [sheet.width, SIZE],
        'frame_size': SIZE,
        'palette_size': len(PALETTE),
        'layer_order': LAYER_ORDER,
        'pack': pack_name,
        'anchors': {'TOP_Y': TOP_Y, 'WAIST_Y': WAIST_Y, 'FOOT_Y': FOOT_Y},
        'frames': frames,
    }
    (out / 'atlas.json').write_text(
        json.dumps(atlas, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    (out / 'palette.json').write_text(
        json.dumps(PALETTE, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    lines = []
    for frame in frames:
        sha = hashlib.sha256((out / frame['file']).read_bytes()).hexdigest()
        lines.append(f'{sha}  {frame["file"]}')
    with open(out / 'manifest.sha256', 'w', encoding='utf-8', newline='\n') as manifest:
        manifest.write('\n'.join(lines) + '\n')

    print(
        f'OK -> {out}  包={pack_name}  帧数={len(imgs)}  '
        f'画布={SIZE}  颜色数={len(PALETTE)}  帧间差异校验=PASS'
    )


def main():
    validate_config()
    if len(sys.argv) > 3:
        raise SystemExit('用法：gen_skeleton.py [输出目录] [locomotion|combat]')
    if len(sys.argv) >= 3:
        export(Path(sys.argv[1]), sys.argv[2])
        return

    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd() / 'skeleton-output'
    for pack_name in PACKS:
        export(root / PACK_DIR_NAMES[pack_name], pack_name)


if __name__ == '__main__':
    main()
