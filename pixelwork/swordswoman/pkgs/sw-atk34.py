# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 连招 atk3 突刺 + atk4 回旋斩（各 4 帧）'


def build():
    return [
        # atk3 突刺：引剑 → 收剑至腰 → 水平直刺(thrust 冲线) → 抽剑
        S.Frame('atk3_0', S.pose(dy=-1, lean=-2, legs=2, swing=2, skirt=1, arm=(45, 34), sword=98)),
        S.Frame('atk3_1', S.pose(dy=1, lean=1, legs=1, swing=0, skirt=0, arm=(44, 31), sword=205)),
        S.Frame('atk3_2', S.pose(dy=0, lean=-4, legs=4, swing=-3, skirt=2, arm=(42, 30), sword=180, fx='thrust')),
        # 关节 J3（= atk4_0）
        S.Frame('atk3_3', S.pose(dy=0, lean=1, legs=1, swing=1, skirt=1, arm=(44, 31), sword=170)),
        # atk4 回旋斩：抽剑回身 → 拧腰拉开 → 转身回斩(slash-wide + 回旋气流) → 回正
        S.Frame('atk4_0', S.pose(dy=0, lean=1, legs=1, swing=1, skirt=1, arm=(44, 31), sword=170)),
        S.Frame('atk4_1', S.pose(dy=1, lean=-3, legs=2, swing=3, skirt=-3, arm=(47, 32), sword=225)),
        S.Frame('atk4_2', S.pose(dy=-1, lean=3, legs=4, swing=-3, skirt=4, arm=(38, 28), sword=186,
                                 fx='slash-wide', fx_back='spin')),
        # 关节 J4（= atk5_0）
        S.Frame('atk4_3', S.pose(dy=1, lean=0, legs=1, swing=1, skirt=-2, arm=(41, 33), sword=212)),
    ]
