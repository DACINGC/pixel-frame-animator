# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

TITLE = '金发双马尾女剑士 —— 受伤闪烁 4 帧（非循环）'


def build():
    return [
        # 闪烁靠 flash 三级衰减（纯索引 remap，禁半透明）；瞳/发带索引不进 remap 表
        # 帧0 全闪白+描边变红（被打退后坐）→ 帧1 余韵（主色变白、保留描边）
        # → 帧2 反相回弹（马尾向前甩、后脚蹬地、眨眼）→ 帧3 站稳
        S.Frame('hurt_0', S.pose(dy=2, lean=-3, legs=1, swing=-2, skirt=-2, arm=(44, 30), sword=214, flash=1)),
        S.Frame('hurt_1', S.pose(dy=1, lean=-2, legs=1, swing=-3, skirt=-3, arm=(45, 31), sword=208, flash=2)),
        S.Frame('hurt_2', S.pose(dy=-1, lean=2, legs=2, swing=3, skirt=2, arm=(42, 29), sword=200, head='blink')),
        S.Frame('hurt_3', S.pose(dy=0, lean=0, legs=0, swing=1, skirt=0, arm=(41, 32), sword=206)),
    ]
