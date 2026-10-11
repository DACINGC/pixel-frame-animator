# -*- coding: utf-8 -*-
"""主 Agent 自检探针：渲染代表性姿态到 _qa/_probe.png（不建交付包）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sw_lib as S

P = [
    ('idle_0',    S.pose(dy=0, lean=0, legs=0, swing=1, skirt=0, arm=(41, 34), sword=222)),
    ('guard_0',   S.pose(dy=1, lean=1, legs=1, swing=1, skirt=0, arm=(44, 30), sword=172)),
    ('walk_0',    S.pose(dy=1, lean=-1, legs=1, swing=1, skirt=1, arm=(41, 27), sword=208)),
    ('run_0',     S.pose(dy=1, lean=-5, legs=4, swing=-3, skirt=2, arm=(40, 31), sword=200, fx='dust')),
    ('jump_0',    S.pose(dy=3, lean=0, legs=6, swing=1, skirt=1, arm=(40, 30), sword=226)),
    ('climb_0',   S.pose(dy=1, lean=-2, legs=3, swing=0, skirt=0, arm=(42, 18), sword=258)),
    ('atk2_2',    S.pose(dy=-2, lean=-4, legs=4, swing=-2, skirt=-2, arm=(44, 34), sword=105, fx='slash-up')),
    ('atk1_2',    S.pose(dy=0, lean=-3, legs=1, swing=2, skirt=3, arm=(36, 30), sword=168, fx='slash-wide')),
    ('atk3_2',    S.pose(dy=0, lean=-4, legs=4, swing=-3, skirt=2, arm=(42, 30), sword=180, fx='thrust')),
    ('atk5_2',    S.pose(dy=1, lean=4, legs=4, swing=-2, skirt=1, arm=(40, 28), sword=255, fx='slash-heavy')),
    ('dodge_2',   S.pose(dy=-2, lean=8, legs=4, swing=-3, skirt=-3, arm=(44, 29), sword=226, fx='afterimage')),
    ('hurt_0',    S.pose(dy=2, lean=-3, legs=1, swing=-2, skirt=-2, arm=(44, 30), sword=214, flash=1)),
    ('ult_2',     S.pose(dy=1, lean=-2, legs=1, swing=-3, skirt=-3, tail=-3, arm=(44, 32), sword=99, fx='charge')),
    ('ult_3',     S.pose(dy=-1, lean=-2, legs=2, swing=-2, skirt=-2, tail=-4, arm=(45, 33), sword=96, fx='charge-max', head='glow')),
    ('ult_4',     S.pose(dy=2, lean=6, legs=4, swing=-2, skirt=2, tail=2, arm=(38, 30), sword=245, fx='burst')),
    ('ult_5',     S.pose(dy=0, lean=3, legs=4, swing=2, skirt=3, tail=-1, arm=(40, 30), sword=240, fx_back='burst-wide')),
    ('death_3',   S.pose(dy=4, lean=2, legs=5, swing=1, skirt=2, tail=2, arm=(40, 31), sword=222, head='dead')),
    ('death_5',   S.pose(dy=1, lean=6, legs=3, swing=-3, skirt=4, tail=3, arm=(34, 44), sword=200, head='dead', fx='dust')),
]

frames = [S.Frame(fid, p) for fid, p in P]
for fid, p in P:
    try:
        S.check_pose(fid, p)
    except SystemExit as e:
        print('FAIL', fid, e)
S.dump_preview(frames, str(Path(__file__).resolve().parent / '_probe.png'), 'probe', cols=6)
