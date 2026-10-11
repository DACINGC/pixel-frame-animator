# -*- coding: utf-8 -*-
"""临时目检探针：把 sw-atk34 的 8 帧分两张 2x2 大图输出（不碰已有文件）。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runpy
import sw_lib as S

ns = runpy.run_path(str(Path(__file__).resolve().parent.parent / 'pkgs' / 'sw-atk34.py'))
frames = ns['build']()

out = Path(__file__).resolve().parent
for name, sel in (('atk3', lambda fid: fid.startswith('atk3')),
                  ('atk4', lambda fid: fid.startswith('atk4'))):
    fs = [f for f in frames if sel(f.id)]
    imgs = []
    for f in fs:
        S.check_pose(f.id, f.pose)
        imgs.append(S.mk_frame(f.id, f.pose))
    sheet = S.contact_sheet(imgs, scale=12, cols=2)
    p = out / f'_probe-atk34-{name}.png'
    sheet.save(p)
    print(p)
