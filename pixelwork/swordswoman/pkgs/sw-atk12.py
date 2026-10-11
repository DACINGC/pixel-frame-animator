# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 连招 atk1 横斩 + atk2 上挑（各 4 帧）'


def build():
    return [
        # atk1 横斩：右后下拉 → 高举蓄力 → 自右上经头顶扫向左(slash-wide 弧同向) → 收势
        S.Frame('atk1_0', S.pose(dy=1, lean=1, legs=0, swing=-2, skirt=-1, arm=(36, 32), sword=315)),
        S.Frame('atk1_1', S.pose(dy=2, lean=3, legs=1, swing=-3, skirt=-2, arm=(38, 29), sword=55)),
        S.Frame('atk1_2', S.pose(dy=0, lean=2, legs=1, swing=2, skirt=-2, arm=(38, 31), sword=168, fx='slash-wide')),
        # 关节 J1（= atk2_0，硬一致：arm/dy/deg/lean/legs 逐值相等）
        S.Frame('atk1_3', S.pose(dy=0, lean=-1, legs=2, swing=1, skirt=2, arm=(38, 31), sword=220)),
        # atk2 上挑：贴地 → 蹲身引剑 → 自下而上撩起(slash-up, lean≤-3) → 举剑过头收势
        S.Frame('atk2_0', S.pose(dy=0, lean=-1, legs=2, swing=1, skirt=2, arm=(38, 31), sword=220)),
        S.Frame('atk2_1', S.pose(dy=2, lean=-2, legs=5, swing=-1, skirt=1, arm=(40, 31), sword=240)),
        S.Frame('atk2_2', S.pose(dy=-2, lean=-4, legs=4, swing=-2, skirt=-2, arm=(44, 34), sword=105, fx='slash-up')),
        # 关节 J2（= atk3_0）
        S.Frame('atk2_3', S.pose(dy=-1, lean=-2, legs=2, swing=2, skirt=1, arm=(45, 34), sword=98)),
    ]
