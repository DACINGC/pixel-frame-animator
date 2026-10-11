# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 死亡 6 帧（非循环）'


def build():
    return [
        # 无旋转 API：倒地 = legs 0→4→2→5(跪)→4(前扑)→3(蜷) + tail 末帧+3 贴地
        # + 末两帧 skirt=4 裙摆铺开 + head='dead'(X眼)；dy 单调下沉后末帧回 +1（dust 限制）
        S.Frame('death_0', S.pose(dy=-1, lean=-4, legs=0, swing=-2, skirt=-1, tail=-1,
                                  arm=(43, 28), sword=214, flash=1)),
        S.Frame('death_1', S.pose(dy=2, lean=-3, legs=4, swing=2, skirt=0, tail=0,
                                  arm=(42, 28), sword=228)),
        S.Frame('death_2', S.pose(dy=4, lean=1, legs=2, swing=1, skirt=1, tail=1,
                                  arm=(41, 29), sword=210)),
        S.Frame('death_3', S.pose(dy=4, lean=2, legs=5, swing=1, skirt=2, tail=2,
                                  arm=(40, 31), sword=222, head='dead')),
        S.Frame('death_4', S.pose(dy=4, lean=8, legs=4, swing=1, skirt=4, tail=2,
                                  arm=(30, 34), sword=225, head='dead')),
        S.Frame('death_5', S.pose(dy=1, lean=6, legs=3, swing=-3, skirt=4, tail=3,
                                  arm=(34, 44), sword=200, head='dead', fx='dust')),
    ]
