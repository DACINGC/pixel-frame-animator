# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 大招 8 帧（非循环）'


def build():
    return [
        # 能量斜坡：收剑聚气 → 举剑过头 → 光效升起 → 蓄力顶点(发光眼)
        # → 下劈命中(burst) → 冲击扩散(burst-wide 放 backfx 层) → 余波 → 收势
        S.Frame('ultimate_0', S.pose(dy=1, lean=0, legs=0, swing=1, skirt=-1, tail=0,
                                     arm=(40, 34), sword=222)),
        S.Frame('ultimate_1', S.pose(dy=0, lean=-2, legs=1, swing=-2, skirt=-2, tail=-1,
                                     arm=(44, 33), sword=97)),
        S.Frame('ultimate_2', S.pose(dy=1, lean=-2, legs=1, swing=-3, skirt=-3, tail=-3,
                                     arm=(44, 32), sword=99, fx='charge')),
        # charge-max 的白色顶弧顶点正好压在眼睛上缘并横穿脸颊（读作断眼/泪痕），
        # 改用 charge + flash=2 柔闪白保住蓄力顶点的能量强度，发光瞳保留。
        S.Frame('ultimate_3', S.pose(dy=-1, lean=-2, legs=2, swing=-2, skirt=-2, tail=-4,
                                     arm=(45, 33), sword=96, fx='charge',
                                     head='glow', flash=2)),
        # 帧序列的弧形斩击特效（burst/slash-heavy/slash-wide）都不可避免压到躯干或脸：
        # burst 圈心在躯干上、slash-heavy 弧端扫左眼、slash-wide 弧右支横穿下颌。
        # 改用 dust（砸地尘土，dy=1 合规）+ 帧5 屏幕级 burst-wide 组成两帧冲击。
        S.Frame('ultimate_4', S.pose(dy=1, lean=6, legs=4, swing=-2, skirt=2, tail=2,
                                     arm=(38, 30), sword=245, fx='dust')),
        S.Frame('ultimate_5', S.pose(dy=0, lean=3, legs=4, swing=2, skirt=3, tail=-1,
                                     arm=(40, 30), sword=240, fx_back='burst-wide')),
        S.Frame('ultimate_6', S.pose(dy=1, lean=1, legs=2, swing=2, skirt=0, tail=-2,
                                     arm=(40, 29), sword=232, fx='spark')),
        S.Frame('ultimate_7', S.pose(dy=0, lean=0, legs=0, swing=0, skirt=0, tail=0,
                                     arm=(41, 34), sword=226, fx='spark')),
    ]
