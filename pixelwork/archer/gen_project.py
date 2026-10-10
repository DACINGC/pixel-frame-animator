# -*- coding: utf-8 -*-
"""原创像素弓箭手 "云纹游侠" —— 有限索引像素工程生成器。
专家手工设计的姿态参数化绘制；非通用角色生成器，仅为本次原创设计服务。"""
import json, math
from pathlib import Path
from PIL import Image, ImageDraw

SIZE = 64
PALETTE = [
    (0,0,0,0),          # 0 透明
    (40,34,54,255),     # 1 描边
    (56,120,214,255),   # 2 主蓝
    (120,186,255,255),  # 3 浅蓝
    (30,66,140,255),    # 4 深蓝
    (246,249,253,255),  # 5 白
    (255,222,196,255),  # 6 皮肤
    (236,182,148,255),  # 7 皮肤暗
    (242,132,52,255),   # 8 橙发
    (255,182,96,255),   # 9 橙发亮
    (214,48,62,255),    # 10 红宝石
    (48,46,58,255),     # 11 黑袜
    (232,182,84,255),   # 12 金
    (98,200,96,255),    # 13 绿眼
    (130,232,255,255),  # 14 青色特效
    (86,90,110,255),    # 15 残影灰蓝
]

def new():
    return Image.new('P', (SIZE, SIZE), 0)

def r(d, box, c, outline=None):
    d.rectangle(box, fill=c, outline=outline)

def ell(d, box, c, outline=None, w=1):
    d.ellipse(box, fill=c, outline=outline, width=w)

def line(d, pts, c, wd=1):
    d.line(pts, fill=c, width=wd)

# ---------- 部件绘制（均为专家设计的固定造型，参数控制姿态） ----------

def draw_hair_back(d, sway=0, dy=0):
    """脑后长发：橙色大团，发梢随动作摆动 sway 像素"""
    y0 = 14 + dy
    pts = [(24, y0), (41, y0), (45, y0+10), (44+sway, y0+18),
           (41+sway, y0+24), (42+sway, y0+27), (37+sway, y0+24),
           (33+sway, y0+27), (28+sway, y0+24), (24+sway, y0+26),
           (21+sway, y0+20), (20, y0+10)]
    d.polygon(pts, fill=8, outline=1)
    # 发丝高光
    line(d, [(38, y0+6), (41+sway, y0+18)], 9, 1)
    line(d, [(25, y0+6), (22+sway, y0+18)], 9, 1)

def draw_head(d, dy=0, blink=False):
    y = dy
    # 后发已在外层；头部皮肤
    ell(d, (25, 12+y, 40, 27+y), 6, 1)
    # 刘海
    d.polygon([(25, 14+y), (40, 14+y), (40, 18+y), (37, 17+y), (35, 20+y),
               (33, 17+y), (31, 19+y), (29, 17+y), (27, 20+y), (25, 17+y)], fill=8)
    line(d, [(25, 14+y), (40, 14+y)], 1, 1)
    # 眼睛（绿瞳，无描边以免吃色）
    if not blink:
        r(d, (27, 20+y, 28, 21+y), 13)
        r(d, (33, 20+y, 34, 21+y), 13)
        line(d, [(27, 22+y), (28, 22+y)], 1, 1)
        line(d, [(33, 22+y), (34, 22+y)], 1, 1)
    else:
        line(d, [(27, 21+y), (28, 21+y)], 1, 1)
        line(d, [(33, 21+y), (34, 21+y)], 1, 1)
    # 嘴
    line(d, [(30, 24+y), (31, 24+y)], 7, 1)
    # 帽子
    ell(d, (22, 4+y, 43, 17+y), 2, 1)
    d.chord((22, 4+y, 43, 17+y), 180, 360, fill=2, outline=1)
    r(d, (22, 12+y, 43, 15+y), 4, 1)
    r(d, (30, 6+y, 34, 9+y), 10, 1)      # 红宝石
    # 侧翼白羽
    d.polygon([(41, 7+y), (48, 5+y), (46, 10+y), (49, 12+y), (41, 12+y)], fill=5, outline=1)
    d.polygon([(18, 8+y), (22, 6+y), (22, 12+y), (18, 13+y)], fill=5, outline=1)

def draw_body(d, dy=0, lean=0):
    y = dy
    x = lean
    # 裙身
    d.polygon([(27+x, 26+y), (38+x, 26+y), (41+x, 36+y), (24+x, 36+y)], fill=2, outline=1)
    r(d, (30+x, 27+y, 35+x, 32+y), 5)         # 白色前襟
    line(d, [(27+x, 33+y), (38+x, 33+y)], 12, 1)  # 金腰带
    r(d, (31+x, 33+y, 34+x, 34+y), 12, 1)     # 金饰
    # 裙摆
    d.polygon([(25+x, 35+y), (40+x, 35+y), (43+x, 41+y), (22+x, 41+y)], fill=5, outline=1)
    line(d, [(24+x, 40+y), (42+x, 40+y)], 3, 1)

def draw_legs(d, dy=0, lean=0, pose=0):
    """pose: 0=并立 1=左前右后 2=右前左后 3=收拢(跳) 4=大跨(跑)"""
    y = dy; x = lean
    def shoe(lx, ly):
        r(d, (lx, ly, lx+4, ly+3), 2, 1)
        line(d, [(lx, ly+3), (lx+4, ly+3)], 1, 1)
    if pose == 0:
        r(d, (28+x, 40+y, 30+x, 54+y), 11, 1); shoe(26+x, 54+y)
        r(d, (34+x, 40+y, 36+x, 54+y), 11, 1); shoe(34+x, 54+y)
    elif pose == 1:  # 左腿前伸
        line(d, [(29+x, 41+y), (24+x, 52+y)], 11, 3); shoe(21+x, 52+y)
        line(d, [(35+x, 41+y), (37+x, 52+y)], 11, 3); shoe(36+x, 52+y)
    elif pose == 2:  # 右腿前伸
        line(d, [(29+x, 41+y), (27+x, 52+y)], 11, 3); shoe(24+x, 52+y)
        line(d, [(35+x, 41+y), (40+x, 52+y)], 11, 3); shoe(39+x, 52+y)
    elif pose == 3:  # 收腿
        r(d, (28+x, 40+y, 30+x, 48+y), 11, 1); shoe(26+x, 48+y)
        r(d, (34+x, 40+y, 36+x, 47+y), 11, 1); shoe(35+x, 47+y)
    elif pose == 4:  # 跑步大跨
        line(d, [(28+x, 41+y), (20+x, 50+y)], 11, 3); shoe(17+x, 50+y)
        line(d, [(36+x, 41+y), (43+x, 48+y)], 11, 3); shoe(42+x, 48+y)

def draw_arm_bow(d, dy=0, lean=0, grip=(17, 32)):
    """持弓臂：肩到弓把"""
    y = dy; x = lean
    line(d, [(28+x, 30+y), (grip[0]+2, grip[1]+y)], 6, 3)
    line(d, [(28+x, 30+y), (grip[0]+2, grip[1]+y)], 7, 1)
    # 袖口
    r(d, (23+x, 29+y, 26+x, 32+y), 4, 1)

def draw_arm_string(d, dy=0, lean=0, hand=None):
    """钩弦臂：hand 为手所在坐标，None 表示垂放"""
    y = dy; x = lean
    if hand is None:
        line(d, [(37+x, 30+y), (39+x, 36+y)], 6, 3)
        r(d, (38+x, 36+y, 40+x, 38+y), 6, 1)
    else:
        line(d, [(37+x, 30+y), (hand[0]-1, hand[1])], 6, 3)
        r(d, (hand[0]-1, hand[1]-1, hand[0]+1, hand[1]+1), 6, 1)

GRIP = (9, 32)
BOW_BBOX = (6, 10, 30, 54)

def bow_tips():
    cx, cy = (BOW_BBOX[0]+BOW_BBOX[2])/2, (BOW_BBOX[1]+BOW_BBOX[3])/2
    rx, ry = (BOW_BBOX[2]-BOW_BBOX[0])/2, (BOW_BBOX[3]-BOW_BBOX[1])/2
    def pt(deg):
        a = math.radians(deg)
        return (round(cx+rx*math.cos(a)), round(cy-ry*math.sin(a)))
    return pt(115), pt(245)

def draw_bow(d, dy=0, draw_px=None, arrow=None, string_hand=None):
    """draw_px: 弦拉到该x坐标; arrow: None/'nock'/'fly'/'gone'"""
    y = dy
    top, bot = bow_tips()
    d.arc(BOW_BBOX, 115, 245, fill=1, width=5)
    d.arc(BOW_BBOX, 115, 245, fill=2, width=3)
    d.arc((BOW_BBOX[0]+1, BOW_BBOX[1]+2, BOW_BBOX[2]-1, BOW_BBOX[3]-2), 125, 235, fill=3, width=1)
    # 云纹弓梢
    ell(d, (top[0]-3, top[1]-3+y, top[0]+2, top[1]+2+y), 5, 1)
    ell(d, (bot[0]-3, bot[1]-3+y, bot[0]+2, bot[1]+2+y), 5, 1)
    # 金饰与流苏
    r(d, (11, 44+y, 13, 47+y), 12, 1)
    line(d, [(13, 48+y), (14, 54+y)], 12, 2)
    # 弓弦
    sx = top[0]
    if draw_px is None:
        line(d, [(sx, top[1]+y), (sx, bot[1]+y)], 5, 1)
    else:
        line(d, [(sx, top[1]+y), (draw_px, 32+y)], 5, 1)
        line(d, [(draw_px, 32+y), (sx, bot[1]+y)], 5, 1)
    # 箭
    if arrow == 'nock':
        ax = draw_px if draw_px is not None else sx
        line(d, [(6, 32+y), (ax, 32+y)], 12, 1)
        d.polygon([(3, 32+y), (8, 29+y), (8, 35+y)], fill=3, outline=1)
        line(d, [(ax-2, 30+y), (ax, 32+y)], 5, 1)
        line(d, [(ax-2, 34+y), (ax, 32+y)], 5, 1)
    elif arrow == 'fly':
        line(d, [(-2, 32+y), (10, 32+y)], 12, 1)
        d.polygon([(10, 32+y), (5, 29+y), (5, 35+y)], fill=14, outline=1)

def draw_fx(d, kind, dy=0, dx=0):
    y = dy; x = dx
    if kind == 'release':     # 放箭闪光
        ell(d, (0, 28+y, 8, 36+y), 14)
        line(d, [(2, 30+y), (0, 30+y)], 5, 1)
        line(d, [(2, 34+y), (0, 34+y)], 5, 1)
    elif kind == 'slash':     # 月牙斩击波
        d.arc((2, 24+y, 26, 44+y), 120, 240, fill=14, width=2)
        d.arc((4, 26+y, 24, 42+y), 130, 230, fill=5, width=1)
    elif kind == 'streak1':   # 闪避残影线条
        line(d, [(20, 30+y), (30, 30+y)], 15, 1)
        line(d, [(18, 36+y), (30, 36+y)], 15, 1)
        line(d, [(22, 42+y), (32, 42+y)], 15, 1)
    elif kind == 'streak2':
        line(d, [(12, 28+y), (24, 28+y)], 14, 1)
        line(d, [(10, 40+y), (24, 40+y)], 14, 1)
    elif kind == 'dust':
        ell(d, (44, 54+y, 50, 58+y), 5, 1)
        ell(d, (50, 56+y, 54, 59+y), 15)

# ---------- 帧定义 ----------

def frame_layers(fid, fx_fn=None, **pose):
    """pose: dy, lean, legs, hair, arm_hand, draw_px, arrow, blink"""
    dy = pose.get('dy', 0); lean = pose.get('lean', 0)
    hair = pose.get('hair', 0); legs = pose.get('legs', 0)
    hand = pose.get('arm_hand', None)
    draw_px = pose.get('draw_px', None); arrow = pose.get('arrow', None)
    blink = pose.get('blink', False)
    grip = (GRIP[0]+lean, GRIP[1])

    layers = {}
    im = new(); d = ImageDraw.Draw(im)
    draw_hair_back(d, hair, dy)
    layers['hair'] = im

    im = new(); d = ImageDraw.Draw(im)
    draw_body(d, dy, lean)
    draw_head(d, dy, blink)
    draw_arm_string(d, dy, lean, hand)
    draw_legs(d, dy, lean, legs)
    layers['body'] = im

    im = new(); d = ImageDraw.Draw(im)
    draw_arm_bow(d, dy, lean, grip)
    draw_bow(d, dy, draw_px, arrow, hand)
    layers['bow'] = im

    im = new(); d = ImageDraw.Draw(im)
    if fx_fn: fx_fn(d)
    layers['fx'] = im

    out = {}
    for name, img in layers.items():
        flat = list(img.getdata())
        out[name] = [flat[i*SIZE:(i+1)*SIZE] for i in range(SIZE)]
    return {'id': fid, 'pose': fid, 'layers': out}

def build_walk():
    frames = []
    for i, (dy, legs, hair) in enumerate([(1,1,1),(0,0,0),(1,2,-1),(0,0,0)]):
        frames.append(frame_layers(f'walk_{i}', dy=dy, legs=legs, hair=hair,
                                   blink=(i==2)))
    return frames

def build_attack():
    frames = []
    frames.append(frame_layers('attack_0', arrow='nock'))                       # 搭箭
    frames.append(frame_layers('attack_1', arrow='nock', draw_px=22,
                               arm_hand=(22,32), lean=1))                       # 开弓
    frames.append(frame_layers('attack_2', arrow='nock', draw_px=26,
                               arm_hand=(26,32), lean=2, blink=True))           # 满弦
    frames.append(frame_layers('attack_3', arrow='fly', lean=1,
                               arm_hand=(24,31), blink=True,
                               fx_fn=lambda d: (draw_fx(d,'release'), draw_fx(d,'slash'))))  # 放箭
    return frames

def build_jump():
    frames = []
    frames.append(frame_layers('jump_0', dy=3, legs=3, hair=2))                 # 蓄力蹲
    frames.append(frame_layers('jump_1', dy=-3, legs=0, hair=-2))               # 起跳伸展
    frames.append(frame_layers('jump_2', dy=-7, legs=3, hair=-2))               # 空中收腿
    frames.append(frame_layers('jump_3', dy=-2, legs=0, hair=1,
                               fx_fn=lambda d: draw_fx(d,'dust')))              # 落地
    return frames

def build_run():
    frames = []
    for i, (dy, lean, legs, hair) in enumerate([(0,2,4,-1),(-1,2,2,-2),(0,2,4,1),(-1,2,1,2)]):
        frames.append(frame_layers(f'run_{i}', dy=dy, lean=lean, legs=legs, hair=hair,
                                   blink=(i==1)))
    return frames

def build_dodge():
    frames = []
    frames.append(frame_layers('dodge_0', dy=2, lean=2, legs=3, hair=2,
                               fx_fn=lambda d: draw_fx(d,'streak1')))
    frames.append(frame_layers('dodge_1', dy=4, lean=6, legs=3, hair=3, blink=True,
                               fx_fn=lambda d: (draw_fx(d,'streak2'), draw_fx(d,'streak1'))))
    frames.append(frame_layers('dodge_2', dy=2, lean=9, legs=3, hair=2, blink=True,
                               fx_fn=lambda d: draw_fx(d,'streak2')))
    frames.append(frame_layers('dodge_3', lean=4, legs=2, hair=1,
                               fx_fn=lambda d: draw_fx(d,'dust')))
    return frames

def main():
    # 引擎单project限2-8帧，拆为3个同源工程（同一角色设计/调色板/分层架构）
    groups = {
        'cloud-archer-walk-jump': (build_walk(), build_jump()),
        'cloud-archer-attack-run': (build_attack(), build_run()),
        'cloud-archer-dodge': (build_dodge(),),
    }
    for pid, parts in groups.items():
        frames = [f for part in parts for f in part]
        proj = {
            'schema': 'pixel-project/1',
            'project_id': pid,
            'title': '原创像素弓箭手·云纹游侠',
            'description': '64像素原创弓箭手：蓝帽白翼红宝石、橙色长发、蓝白裙装、黑袜、云纹大弓。'
                           '面向左侧，透明底。本包动作：' + '/'.join(f['id'].rsplit('_',1)[0] for f in frames[:1]) +
                           '等共%d帧（完整20帧分3包交付）。' % len(frames),
            'originality': '基于用户提供的参考图做的原创像素风格演绎，为专家手工设计的有限索引像素工程，'
                           '非对参考图的复制，不承诺与原图逐像素一致。',
            'size': SIZE,
            'revision': 1,
            'palette': [list(c) for c in PALETTE],
            'layer_order': ['hair', 'body', 'bow', 'fx'],
            'frames': frames,
        }
        outdir = Path(__file__).parent / 'project'
        outdir.mkdir(exist_ok=True)
        out = outdir / (pid + '.json')
        out.write_bytes((json.dumps(proj, ensure_ascii=False) + '\n').encode('utf-8'))
        print('wrote', out, 'frames:', len(frames))

if __name__ == '__main__':
    main()
