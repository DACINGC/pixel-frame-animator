# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 待机 4 帧 + 戒备待机 4 帧（均循环）'


def build():
    return [
        # idle：并立呼吸，剑尖垂地（tip≈(19,54)），幅度极小，帧2眨眼
        S.Frame('idle_0', S.pose(dy=0, lean=0, legs=0, swing=1, skirt=0, arm=(41, 34), sword=222)),
        S.Frame('idle_1', S.pose(dy=-1, lean=0, legs=0, swing=-1, skirt=1, arm=(41, 34), sword=226)),
        S.Frame('idle_2', S.pose(dy=0, lean=0, legs=0, swing=1, skirt=-1, arm=(42, 34), sword=230, head='blink')),
        S.Frame('idle_3', S.pose(dy=0, lean=0, legs=0, swing=-1, skirt=0, arm=(40, 34), sword=225)),
        # idle-guard：前后脚 + 含胸后坐，剑横抬身前（tip≈(14,27)），四帧全睁眼
        S.Frame('idle-guard_0', S.pose(dy=1, lean=1, legs=1, swing=1, skirt=0, arm=(44, 30), sword=172)),
        S.Frame('idle-guard_1', S.pose(dy=2, lean=2, legs=2, swing=-1, skirt=1, arm=(43, 29), sword=175)),
        S.Frame('idle-guard_2', S.pose(dy=1, lean=2, legs=2, swing=1, skirt=-1, arm=(44, 31), sword=168)),
        S.Frame('idle-guard_3', S.pose(dy=2, lean=1, legs=1, swing=-1, skirt=0, arm=(43, 30), sword=174)),
    ]
