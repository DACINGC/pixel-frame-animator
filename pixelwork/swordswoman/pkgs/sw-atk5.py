# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 连招 atk5 下劈终结（4 帧，非循环）'


def build():
    return [
        # 承接 J4 → 蹲身举剑过头(legs6 深蹲) → 跳劈砸地(slash-heavy + 地面冲击)
        # → 拄剑喘息收势（deg 260 剑尖拄地 + 落地余尘）
        S.Frame('atk5_0', S.pose(dy=1, lean=0, legs=1, swing=1, skirt=-2, arm=(41, 33), sword=212)),
        S.Frame('atk5_1', S.pose(dy=3, lean=-1, legs=6, swing=-1, skirt=-1, tail=-1,
                                 arm=(45, 34), sword=98)),
        S.Frame('atk5_2', S.pose(dy=2, lean=4, legs=4, swing=-2, skirt=1, tail=-2,
                                 arm=(40, 27), sword=255, fx='slash-heavy')),
        S.Frame('atk5_3', S.pose(dy=0, lean=1, legs=1, swing=1, skirt=1, arm=(41, 30),
                                 sword=260, fx='dust')),
    ]
