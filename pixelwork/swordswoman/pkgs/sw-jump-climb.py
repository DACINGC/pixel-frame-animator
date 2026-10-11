# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 跳跃 4 帧（单次起落）+ 攀爬 4 帧（循环）'


def build():
    return [
        # jump：蓄力蹲(legs6) → 起跳伸展 → 空中收腿(最高点) → 落地扬尘
        # dy 3→-2→-5→+1 完整起落弧；legs 6→0→3→4；剑随动作从垂前(226)抬到前平(196)再下压
        S.Frame('jump_0', S.pose(dy=3, lean=0, legs=6, swing=1, skirt=1, tail=-1, arm=(40, 30), sword=226)),
        S.Frame('jump_1', S.pose(dy=-2, lean=0, legs=0, swing=-2, skirt=-2, tail=-2, arm=(42, 27), sword=206)),
        S.Frame('jump_2', S.pose(dy=-5, lean=1, legs=3, swing=-3, skirt=-3, tail=-3, arm=(44, 26), sword=196)),
        S.Frame('jump_3', S.pose(dy=1, lean=1, legs=4, swing=3, skirt=2, tail=0, arm=(41, 29), sword=216, fx='dust')),
        # climb：手扣住固定支点，身体上升时持握手 arm[1] 同步 +2 抵消 dy（绝对 y 守恒）
        # 帧0/1：右手(arm)扣支点，绝对 y=19（18+1 == 20-1）；剑贴背向下垂在右侧
        # 帧2/3：换左手(back_arm=自由手)抓更高支点，绝对 y=15（14+1 == 16-1），
        #        手抬到头顶前上方(x=14)，避免手臂横穿脸颊；右手松开垂到体侧(31→29 随身体上升)
        # swing 恒 0（马尾一甩就进墙里）
        S.Frame('climb_0', S.pose(dy=1, lean=-2, legs=3, swing=0, skirt=0, tail=-1, arm=(42, 18), sword=258)),
        S.Frame('climb_1', S.pose(dy=-1, lean=-2, legs=1, swing=0, skirt=-1, tail=-2, arm=(42, 20), sword=262)),
        S.Frame('climb_2', S.pose(dy=1, lean=-2, legs=2, swing=0, skirt=0, tail=-1, arm=(43, 30),
                                  back_arm=(14, 14), sword=256)),
        S.Frame('climb_3', S.pose(dy=-1, lean=-2, legs=3, swing=0, skirt=-1, tail=-2, arm=(43, 30),
                                  back_arm=(14, 16), sword=264)),
    ]
