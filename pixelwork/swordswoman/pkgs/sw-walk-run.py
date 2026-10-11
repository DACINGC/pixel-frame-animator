# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 行走 4 帧 + 奔跑 4 帧（均循环）'


def build():
    return [
        # walk：contact → passing → contact → passing；马尾/裙摆/持剑臂两拍反相
        #   0 迈左(接触) 1 经过(并立抬重心) 2 迈右(接触) 3 经过(并立落重心)
        S.Frame('walk_0', S.pose(dy=1, lean=-1, legs=1, swing=-2, skirt=1, arm=(42, 27), sword=208)),
        S.Frame('walk_1', S.pose(dy=-1, lean=-1, legs=0, swing=1, skirt=-1, arm=(40, 27), sword=214)),
        S.Frame('walk_2', S.pose(dy=1, lean=-1, legs=2, swing=2, skirt=-1, arm=(38, 27), sword=202)),
        S.Frame('walk_3', S.pose(dy=0, lean=-1, legs=0, swing=-1, skirt=1, arm=(40, 27), sword=210)),
        # run：大跨前冲 → 收腿腾空 → 伸腿 → 前脚；马尾一路向后飘
        S.Frame('run_0', S.pose(dy=1, lean=-5, legs=4, swing=-3, skirt=2, arm=(40, 31), sword=200, fx='dust')),
        S.Frame('run_1', S.pose(dy=-2, lean=-6, legs=3, swing=-2, skirt=-3, arm=(42, 29), sword=188)),
        S.Frame('run_2', S.pose(dy=1, lean=-4, legs=1, swing=-3, skirt=2, arm=(39, 32), sword=208)),
        S.Frame('run_3', S.pose(dy=0, lean=-5, legs=2, swing=-2, skirt=-2, arm=(41, 30), sword=194, fx='dust')),
    ]
