# -*- coding: utf-8 -*-
"""32x32 哥布林：行走 / 攻击 / 受击 / 死亡。颜色只来自 spec_lock 的 PICO-8。"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 32
FOOT_Y = 28
SKILL_PROJECT = Path(
    r"D:\zm\AIProj\Cursor\pixel-anim\pixel-asset-master-skills\projects\goblin_32x32_20261012"
)
PACK_NAME = "goblin-actions-r3"
HERE = Path(__file__).resolve().parent

# 索引 0 透明。其余 RGB 与 spec_lock.md 的 HEX 一一对应。
PALETTE = [
    (0, 0, 0, 0),            # 0 透明
    (0, 0, 0, 255),          # 1 #000000 描边 / 瞳孔深线
    (29, 43, 83, 255),       # 2 #1D2B53 冷暗部
    (0, 135, 81, 255),       # 3 #008751 皮肤
    (0, 228, 54, 255),       # 4 #00E436 左上高光
    (255, 204, 170, 255),    # 5 #FFCCAA 肚皮 / 耳内
    (171, 82, 54, 255),      # 6 #AB5236 腰布
    (95, 87, 79, 255),       # 7 #5F574F 刀柄 / 靴 / 尘
    (194, 195, 199, 255),    # 8 #C2C3C7 刀刃
    (255, 241, 232, 255),    # 9 #FFF1E8 牙 / 刃口 / 闪白
    (126, 37, 83, 255),      # 10 #7E2553 腰布暗纹
    (255, 0, 77, 255),       # 11 #FF004D 受击红
    (255, 163, 0, 255),      # 12 #FFA300 火花
    (255, 236, 39, 255),     # 13 #FFEC27 眼睛 / 火花核
]
INK, NAVY, GREEN, LIME = 1, 2, 3, 4
PEACH, LEATHER, GRIP, STEEL = 5, 6, 7, 8
CREAM, CLOTH, RED, ORANGE, YELLOW = 9, 10, 11, 12, 13
LAYER_ORDER = ["back", "body", "weapon", "fx"]
ACTIONS_ORDER = ("walk", "attack", "hurt", "die")

OOB = []


def new_layer():
    return Image.new("P", (SIZE, SIZE), 0)


def rect(d, box, c, outline=None):
    x0, y0, x1, y1 = (int(v) for v in box)
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    if x0 < 0 or y0 < 0 or x1 >= SIZE or y1 >= SIZE:
        OOB.append(("rect", box))
    d.rectangle((x0, y0, x1, y1), fill=c, outline=outline)


def ell(d, box, c, outline=None):
    x0, y0, x1, y1 = (int(v) for v in box)
    if x0 < 0 or y0 < 0 or x1 >= SIZE or y1 >= SIZE:
        OOB.append(("ell", box))
    d.ellipse((x0, y0, x1, y1), fill=c, outline=outline)


def seg(d, pts, c, w=1):
    extra = w // 2
    clean = []
    for x, y in pts:
        x, y = int(x), int(y)
        clean.append((x, y))
        if x - extra < 0 or y - extra < 0 or x + extra >= SIZE or y + extra >= SIZE:
            OOB.append(("seg", (x, y), w))
    d.line(clean, fill=c, width=w)


def poly(d, pts, c, outline=None):
    clean = [(int(x), int(y)) for x, y in pts]
    for x, y in clean:
        if x < 0 or y < 0 or x >= SIZE or y >= SIZE:
            OOB.append(("poly", (x, y)))
    d.polygon(clean, fill=c, outline=outline)


def limb(d, pts, fill, ink, fw=1, ow=3):
    seg(d, pts, ink, ow)
    seg(d, pts, fill, fw)


def colors(p):
    if p["flash"]:
        return CREAM, CREAM, CREAM, RED
    return GREEN, LIME, NAVY, INK


def pose(
    dy=0,
    lean=0,
    squash=0,
    flash=0,
    bruise=0,
    fx=None,
    legs=0,
    cloth=0,
    tail=0,
    head_dx=0,
    head_dy=0,
    eyes="normal",
    arm_f=(-4, 3),
    arm_b=(2, 4),
    knife=(-4, -1),
    knife_back=0,
    stage="stand",
):
    return {
        "dy": dy,
        "lean": lean,
        "squash": squash,
        "flash": flash,
        "bruise": bruise,
        "fx": fx,
        "legs": legs,
        "cloth": cloth,
        "tail": tail,
        "head_dx": head_dx,
        "head_dy": head_dy,
        "eyes": eyes,
        "arm_f": arm_f,
        "arm_b": arm_b,
        "knife": knife,
        "knife_back": knife_back,
        "stage": stage,
    }


def rig(p):
    ox, oy, sq = p["lean"], p["dy"], p["squash"]
    tx, ty = 12 + ox, 14 + oy + sq
    sf = (tx + 2, ty + 1)
    sb = (tx + 8, ty)
    hand_f = (sf[0] + p["arm_f"][0], sf[1] + p["arm_f"][1])
    hand_b = (sb[0] + p["arm_b"][0], sb[1] + p["arm_b"][1])
    tip = (hand_f[0] + p["knife"][0], hand_f[1] + p["knife"][1])
    return {
        "tx": tx,
        "ty": ty,
        "th": 8 - sq,
        "head": (11 + ox + p["head_dx"], 5 + oy + sq + p["head_dy"]),
        "sf": sf,
        "sb": sb,
        "hand_f": hand_f,
        "hand_b": hand_b,
        "tip": tip,
        "hip_f": (tx + 2, 22 + oy),
        "hip_b": (tx + 7, 22 + oy),
        "foot_y": FOOT_Y + oy,
        "skirt_y": 21 + oy,
    }


def leg_chain(p, r):
    tx, fy = r["tx"], r["foot_y"]
    hy = r["hip_f"][1]
    hf, hb = r["hip_f"], r["hip_b"]
    kind = p["legs"]
    if kind == 1:
        return (hf, (tx - 1, hy + 3), (tx - 2, fy)), (hb, (tx + 8, hy + 3), (tx + 9, fy))
    if kind == 2:
        return (hf, (tx + 2, hy + 3), (tx + 1, fy)), (hb, (tx + 9, hy + 3), (tx + 11, fy))
    if kind == 3:
        return (hf, (tx, hy + 2), (tx - 1, fy - 3)), (hb, (tx + 8, hy + 3), (tx + 8, fy))
    if kind == 4:
        return (hf, (tx - 2, hy + 3), (tx - 4, fy)), (hb, (tx + 9, hy + 3), (tx + 11, fy))
    return (hf, (tx + 1, hy + 3), (tx, fy)), (hb, (tx + 8, hy + 3), (tx + 8, fy))


def draw_boot(d, hip, foot, p):
    mid, _, shade, ink = colors(p)
    fx, fy = foot
    boot = CREAM if p["flash"] else GRIP
    direction = -1 if fx <= hip[0] else 1
    x0 = fx - 2 if direction < 0 else fx
    rect(d, (x0, fy - 1, x0 + 2, fy), boot)
    rect(d, (x0, fy - 1, x0 + 1, fy - 1), mid)
    rect(d, (x0, fy, x0 + 2, fy), shade if not p["flash"] else RED)


def draw_legs(d, p, r):
    mid, _, _, ink = colors(p)
    for hip, knee, foot in leg_chain(p, r):
        limb(d, [hip, knee], mid, ink)
        limb(d, [knee, foot], mid, ink)
        draw_boot(d, hip, foot, p)


def draw_tail(d, p, r):
    mid, _, _, ink = colors(p)
    x, y = r["tx"] + 10, r["ty"] + 4
    sw = p["tail"]
    limb(d, [(x, y), (x + 3, y - 1 + sw), (x + 6, y + 2)], mid, ink)


def draw_hand(d, hand, p):
    mid, hi, shade, _ = colors(p)
    x, y = hand
    rect(d, (x, y, x + 1, y), hi if not p["flash"] else mid)
    rect(d, (x, y + 1, x + 1, y + 1), shade if not p["flash"] else mid)


def draw_arm(d, shoulder, hand, p):
    mid, _, _, ink = colors(p)
    elbow = (
        (shoulder[0] + hand[0]) // 2,
        (shoulder[1] + hand[1]) // 2 + 1,
    )
    limb(d, [shoulder, elbow], mid, ink)
    limb(d, [elbow, hand], mid, ink)
    draw_hand(d, hand, p)


def draw_torso(d, p, r):
    mid, hi, shade, ink = colors(p)
    tx, ty, th = r["tx"], r["ty"], r["th"]
    poly(
        d,
        [
            (tx + 1, ty),
            (tx + 8, ty - 1),
            (tx + 11, ty + 2),
            (tx + 9, ty + th),
            (tx + 2, ty + th),
            (tx, ty + 3),
        ],
        mid,
        ink,
    )
    rect(d, (tx + 2, ty + 1, tx + 5, ty + 2), hi)
    if th >= 6:
        rect(d, (tx + 7, ty + 4, tx + 9, ty + th - 1), shade)
    if not p["flash"] and ty + th - 2 >= ty + 3:
        rect(d, (tx + 2, ty + 3, tx + 5, ty + th - 2), PEACH)
    sy = r["skirt_y"]
    sw = p["cloth"]
    leather = CREAM if p["flash"] else LEATHER
    poly(
        d,
        [
            (tx + 1, sy),
            (tx + 8, sy),
            (tx + 8 + sw, sy + 4),
            (tx + 1 + sw, sy + 4),
        ],
        leather,
        ink,
    )
    band = RED if p["flash"] else CLOTH
    rect(d, (tx + 2, sy, tx + 7, sy + 1), band)


def draw_head(d, x, y, p):
    mid, hi, shade, ink = colors(p)
    # 耳朵先铺描边，颅骨盖住内侧，皮肤再盖住接缝，避免耳朵和脸断开。
    poly(d, [(x + 6, y), (x + 13, y - 2), (x + 14, y + 3), (x + 6, y + 4)], ink)
    poly(d, [(x + 4, y + 2), (x - 4, y), (x - 3, y + 5), (x + 4, y + 6)], ink)
    ell(d, (x + 1, y, x + 10, y + 8), mid, outline=ink)
    poly(d, [(x + 7, y + 1), (x + 12, y - 1), (x + 13, y + 2), (x + 7, y + 3)], mid)
    poly(d, [(x + 5, y + 3), (x - 3, y + 1), (x - 2, y + 4), (x + 5, y + 5)], mid)
    rect(d, (x, y + 1, x + 6, y + 4), mid)
    rect(d, (x + 6, y + 1, x + 9, y + 3), mid)
    rect(d, (x + 2, y + 3, x + 8, y + 8), mid)
    seg(d, [(x + 2, y + 8), (x + 8, y + 8)], ink)
    rect(d, (x + 3, y + 1, x + 5, y + 1), hi)
    if not p["flash"]:
        rect(d, (x + 8, y + 6, x + 9, y + 7), shade)
        rect(d, (x + 11, y - 1, x + 12, y), PEACH)
        rect(d, (x - 2, y + 2, x - 1, y + 3), PEACH)
    poly(d, [(x + 2, y + 5), (x - 2, y + 6), (x - 1, y + 8), (x + 3, y + 7)], mid)
    seg(d, [(x - 2, y + 6), (x - 1, y + 8)], ink)
    if not p["flash"]:
        rect(d, (x - 1, y + 6, x, y + 6), hi)
    if p["eyes"] == "line" or p["flash"]:
        seg(d, [(x + 3, y + 4), (x + 5, y + 4)], RED)
        seg(d, [(x + 7, y + 4), (x + 9, y + 4)], RED)
        seg(d, [(x + 4, y + 7), (x + 7, y + 7)], RED)
    else:
        seg(d, [(x + 3, y + 3), (x + 5, y + 3)], shade)
        seg(d, [(x + 7, y + 3), (x + 9, y + 3)], shade)
        for ex in (x + 3, x + 7):
            rect(d, (ex, y + 4, ex + 1, y + 5), YELLOW)
            rect(d, (ex, y + 4, ex, y + 4), CREAM)
            rect(d, (ex, y + 5, ex, y + 5), NAVY)
        rect(d, (x + 4, y + 8, x + 4, y + 9), CREAM)
        rect(d, (x + 7, y + 8, x + 7, y + 9), CREAM)
    if p["bruise"]:
        rect(d, (x + 1, y + 5, x + 2, y + 6), RED)


def draw_knife(d, hand, tip, p):
    hx, hy = hand
    tx, ty = tip
    gx = hx + (tx - hx) // 3
    gy = hy + (ty - hy) // 3
    ink = RED if p["flash"] else INK
    grip = CREAM if p["flash"] else GRIP
    blade = CREAM if p["flash"] else STEEL
    guard = RED if p["flash"] else LEATHER
    seg(d, [(hx, hy), (gx, gy)], ink, 3)
    seg(d, [(hx, hy), (gx, gy)], grip, 1)
    seg(d, [(gx, gy), (tx, ty)], ink, 3)
    seg(d, [(gx, gy), (tx, ty)], blade, 1)
    if 0 <= tx - 1 < SIZE and 0 <= ty - 1 < SIZE:
        rect(d, (tx - 1, ty - 1, tx - 1, ty - 1), CREAM if not p["flash"] else YELLOW)
    seg(d, [(gx, gy - 2), (gx, gy + 2)], guard, 1)


def draw_sparks(d, tip):
    tx, ty = tip
    for dx, dy, col in ((-1, -3, YELLOW), (-2, -1, ORANGE), (-1, 2, YELLOW), (1, -2, ORANGE)):
        rect(d, (tx + dx, ty + dy, tx + dx + 1, ty + dy), col)


def draw_stand(layers, p):
    r = rig(p)
    back = ImageDraw.Draw(layers["back"])
    body = ImageDraw.Draw(layers["body"])
    draw_tail(back, p, r)
    draw_arm(back, r["sb"], r["hand_b"], p)
    # 后拉的持刃手臂画在身体后面，刀尖从耳后露出来。
    if p["knife_back"]:
        draw_arm(back, r["sf"], r["hand_f"], p)
        draw_knife(back, r["hand_f"], r["tip"], p)
    draw_legs(body, p, r)
    draw_torso(body, p, r)
    hx, hy = r["head"]
    draw_head(body, hx, hy, p)
    if not p["knife_back"]:
        draw_arm(body, r["sf"], r["hand_f"], p)
        draw_knife(ImageDraw.Draw(layers["weapon"]), r["hand_f"], r["tip"], p)
    if p["fx"] == "slash":
        draw_sparks(ImageDraw.Draw(layers["fx"]), r["tip"])


def draw_flat(layers, p):
    body = ImageDraw.Draw(layers["body"])
    draw_head(body, 6, 16, p)
    mid, hi, shade, ink = colors(p)
    poly(body, [(14, 20), (25, 19), (27, 23), (24, 27), (14, 27), (12, 23)], mid, ink)
    rect(body, (15, 20, 19, 21), hi)
    rect(body, (21, 23, 25, 25), shade)
    if not p["bruise"]:
        rect(body, (16, 22, 19, 24), PEACH)
    else:
        rect(body, (16, 22, 19, 24), PEACH)
        rect(body, (22, 21, 23, 22), RED)
    poly(body, [(14, 25), (20, 25), (21, 28), (15, 29)], LEATHER, ink)
    rect(body, (15, 25, 19, 26), CLOTH)
    limb(body, [(24, 24), (27, 26)], mid, ink)
    limb(body, [(27, 26), (28, 28)], mid, ink)
    rect(body, (26, 28, 28, 29), GRIP)
    draw_knife(ImageDraw.Draw(layers["weapon"]), (3, 27), (8, 29), p)


def draw_remains(layers, p):
    body = ImageDraw.Draw(layers["body"])
    mid, hi, _, ink = colors(p)
    poly(body, [(18, 21), (22, 19), (23, 22), (19, 23)], mid, ink)
    rect(body, (20, 20, 21, 20), PEACH)
    rect(body, (21, 19, 21, 19), hi)
    poly(body, [(15, 24), (20, 23), (20, 26), (16, 27)], mid, ink)
    rect(body, (17, 25, 17, 26), CREAM)
    poly(body, [(12, 27), (18, 26), (17, 29), (11, 29)], LEATHER, ink)
    rect(body, (13, 27, 16, 27), CLOTH)
    draw_knife(ImageDraw.Draw(layers["weapon"]), (6, 27), (11, 25), p)
    fx = ImageDraw.Draw(layers["fx"])
    rect(fx, (4, 28, 5, 28), GRIP)
    rect(fx, (23, 26, 24, 26), NAVY)
    rect(fx, (26, 29, 27, 29), GRIP)
    rect(fx, (9, 24, 10, 24), NAVY)


def render_frame(p):
    OOB.clear()
    layers = {name: new_layer() for name in LAYER_ORDER}
    if p["stage"] == "flat":
        draw_flat(layers, p)
    elif p["stage"] == "remains":
        draw_remains(layers, p)
    else:
        draw_stand(layers, p)
    if OOB:
        raise SystemExit(f"画出画布：{OOB[:8]}")
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    for name in LAYER_ORDER:
        sp = layers[name].load()
        for yy in range(SIZE):
            for xx in range(SIZE):
                idx = sp[xx, yy]
                if idx:
                    px[xx, yy] = PALETTE[idx]
    return out


ACTIONS = {
    "walk": [
        pose(dy=1, legs=1, cloth=-1, tail=1, arm_f=(-2, 2), arm_b=(3, 4), knife=(-4, -1)),
        pose(dy=-1, legs=3, cloth=0, tail=-1, head_dy=-1, arm_f=(-4, 2), arm_b=(2, 3), knife=(-4, -1)),
        pose(dy=1, legs=2, cloth=1, tail=0, arm_f=(-6, 3), arm_b=(1, 5), knife=(-4, -2)),
        pose(dy=0, legs=0, cloth=0, tail=1, arm_f=(-3, 2), arm_b=(2, 4), knife=(-4, 0)),
    ],
    "attack": [
        pose(lean=1, legs=0, cloth=1, tail=1, knife_back=1, arm_f=(8, -6), arm_b=(2, 4), knife=(4, -4)),
        pose(lean=1, dy=1, legs=4, cloth=2, tail=2, knife_back=1, arm_f=(7, -8), arm_b=(3, 3), knife=(4, -5)),
        pose(lean=-1, legs=1, cloth=-1, tail=-1, arm_f=(-7, 1), arm_b=(1, 5), knife=(-4, -2), fx="slash"),
        pose(dy=1, legs=0, cloth=0, tail=0, arm_f=(-6, 2), arm_b=(2, 4), knife=(-3, -3)),
    ],
    "hurt": [
        pose(
            lean=2, dy=1, squash=1, flash=1, eyes="line", legs=4, cloth=1, tail=2,
            arm_f=(-2, 3), arm_b=(2, 4), knife=(-3, 1),
        ),
        pose(
            lean=1, dy=-1, bruise=1, legs=3, cloth=0, tail=1, head_dy=-1,
            arm_f=(-4, 3), arm_b=(3, 4), knife=(-4, -1),
        ),
    ],
    "die": [
        pose(
            lean=2, dy=1, bruise=1, legs=4, cloth=2, tail=2, knife_back=1,
            arm_f=(5, 1), arm_b=(2, 5), knife=(3, 2),
        ),
        pose(
            lean=2, dy=2, squash=2, head_dy=2, bruise=1, legs=3, cloth=1, tail=1,
            arm_f=(3, 4), arm_b=(2, 4), knife=(2, 3),
        ),
        pose(stage="flat", bruise=1),
        pose(stage="remains", fx="dust"),
    ],
}


def assert_lock():
    text = (SKILL_PROJECT / "spec_lock.md").read_text(encoding="utf-8")
    if "base_size: 32x32" not in text:
        raise SystemExit("spec_lock 画布不是 32x32")
    if "outline_color: #000000" not in text:
        raise SystemExit("spec_lock 描边色漂移")
    if "max_colors: 15" not in text:
        raise SystemExit("spec_lock 用色上限漂移")
    for color in PALETTE[1:]:
        hex_c = f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"
        if hex_c not in text:
            raise SystemExit(f"{hex_c} 不在 spec_lock 调色板中")
    counts = {name: len(ACTIONS[name]) for name in ACTIONS_ORDER}
    if counts != {"walk": 4, "attack": 4, "hurt": 2, "die": 4}:
        raise SystemExit(f"帧数漂移：{counts}")


def check_frames(frames):
    allowed = set(PALETTE)
    hashes = []
    for fid, im in frames:
        if im.size != (SIZE, SIZE):
            raise SystemExit(f"{fid} 尺寸不是 32x32")
        if im.getbbox() is None:
            raise SystemExit(f"{fid} 是空白帧")
        used = set(im.getdata())
        if not used.issubset(allowed):
            raise SystemExit(f"{fid} 出现调色板外颜色")
        opaque = {c for c in used if c[3] == 255}
        if any(c[3] not in (0, 255) for c in used):
            raise SystemExit(f"{fid} 存在半透明像素")
        if len(opaque) > 15:
            raise SystemExit(f"{fid} 不透明颜色 {len(opaque)} 超过 15")
        hashes.append(hashlib.sha256(im.tobytes()).hexdigest())
    if len(set(hashes)) != len(hashes):
        raise SystemExit("存在完全相同的帧")
    return hashes


def write_pack(out, frames, hashes):
    if out.exists():
        raise SystemExit(f"输出目录已存在，换一个新名字：{out}")
    (out / "frames").mkdir(parents=True)
    meta = []
    for i, ((fid, im), digest) in enumerate(zip(frames, hashes)):
        action, order = fid.rsplit("_", 1)
        im.save(out / "frames" / f"{fid}.png")
        meta.append({
            "id": fid,
            "action": action,
            "order": i,
            "file": f"frames/{fid}.png",
            "rect": [i * SIZE, 0, SIZE, SIZE],
            "rgba_sha256": digest,
        })
    sheet = Image.new("RGBA", (len(frames) * SIZE, SIZE), (0, 0, 0, 0))
    for i, (_, im) in enumerate(frames):
        sheet.paste(im, (i * SIZE, 0))
    sheet.save(out / "sprite-sheet.png")
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.Resampling.NEAREST).save(
        out / "contact-sheet-8x.png"
    )
    gray = Image.new("RGBA", (8 * (SIZE + 1), 2 * (SIZE + 1)), (194, 195, 199, 255))
    for i, (_, im) in enumerate(frames):
        col, row = i % 8, i // 8
        gray.paste(im, (col * (SIZE + 1), row * (SIZE + 1)), im)
    gray.resize((gray.width * 8, gray.height * 8), Image.Resampling.NEAREST).save(
        out / "preview-gray-8x.png"
    )
    atlas = {
        "size": [sheet.width, SIZE],
        "frame_size": SIZE,
        "palette_size": len(PALETTE),
        "layer_order": LAYER_ORDER,
        "facing": "left",
        "anchors": {"FOOT_Y": FOOT_Y},
        "fps": 8,
        "loop": {"walk": True, "attack": False, "hurt": False, "die": False},
        "frames": meta,
    }
    (out / "atlas.json").write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "palette.json").write_text(json.dumps(PALETTE, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "project.json").write_text(json.dumps({
        "title": "哥布林",
        "description": "SNES Retro 32x32。行走、攻击、受击、死亡。面朝左。",
        "size": SIZE,
        "palette": "PICO-8",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = []
    for frame in meta:
        sha = hashlib.sha256((out / frame["file"]).read_bytes()).hexdigest()
        lines.append(f"{sha}  {frame['file']}")
    (out / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_asset_frames(frames):
    dest = SKILL_PROJECT / "assets" / "characters"
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("goblin_*.png"):
        old.unlink()
    for fid, im in frames:
        im.save(dest / f"goblin_{fid}.png")


def main():
    assert_lock()
    frames = []
    for action in ACTIONS_ORDER:
        for i, p in enumerate(ACTIONS[action]):
            frames.append((f"{action}_{i}", render_frame(p)))
    hashes = check_frames(frames)
    write_asset_frames(frames)
    write_pack(SKILL_PROJECT / "animations" / PACK_NAME, frames, hashes)
    write_pack(HERE / PACK_NAME, frames, hashes)
    print(f"OK frames={len(frames)} colors_in_palette={len(PALETTE) - 1}")


if __name__ == "__main__":
    sys.exit(main())
