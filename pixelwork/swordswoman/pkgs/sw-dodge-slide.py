# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 闪避 4 帧（后跳步）+ 滑铲 4 帧（循环）'


def build():
    return [
        # dodge：向后错步闪避；帧2 原地残影（afterimage 占 x23~38，本体 lean=+12 彻底让开，
        #        剑指向身后下方(deg300)避开残影区，马尾因后跃惯性向前甩 swing=+2）
        S.Frame('dodge_0', S.pose(dy=1, lean=0, legs=2, swing=-1, skirt=-1, arm=(40, 30), sword=212)),
        S.Frame('dodge_1', S.pose(dy=-2, lean=4, legs=3, swing=1, skirt=-2, arm=(42, 28), sword=220, head='blink')),
        S.Frame('dodge_2', S.pose(dy=-2, lean=12, legs=2, swing=2, skirt=2, arm=(43, 30), sword=300, fx='afterimage')),
        S.Frame('dodge_3', S.pose(dy=0, lean=0, legs=0, swing=0, skirt=0, arm=(41, 31), sword=216)),
        # slide：4 帧全低姿循环（入铲 → 铲行），循环首尾无起身跳变；swing 恒负（向后飘）
        # 四帧靠 dy/swing/skirt/arm/deg/head/fx 多处叠加区分
        S.Frame('slide_0', S.pose(dy=1, lean=1, legs=5, swing=-1, skirt=-1, arm=(45, 32), sword=196, fx='dust')),
        S.Frame('slide_1', S.pose(dy=1, lean=0, legs=7, swing=-2, skirt=0, arm=(46, 33), sword=193)),
        S.Frame('slide_2', S.pose(dy=2, lean=0, legs=7, swing=-3, skirt=3, arm=(46, 34), sword=190, head='blink')),
        S.Frame('slide_3', S.pose(dy=1, lean=0, legs=7, swing=-2, skirt=1, arm=(45, 33), sword=186)),
    ]
