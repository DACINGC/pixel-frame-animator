# -*- coding: utf-8 -*-
"""
包运行器（主 Agent 独占，子 Agent 不要改）

    python run.py <包名>              # 输出到 ./<包名>
    python run.py <包名> -r2          # 输出到 ./<包名>-r2
    python run.py <包名> --overwrite  # 覆盖重跑同名包（只删本脚本会写的文件）
    python run.py <包名> --preview    # 只出一张 _qa/_preview-<包名>.png，不建包
"""
import runpy, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sw_lib as S

args = sys.argv[1:]
if not args:
    raise SystemExit('用法：python run.py <包名> [-r2|--overwrite|--preview]')

pkg = args[0]
suffix, overwrite, preview = '', False, False
for a in args[1:]:
    if a.startswith('-r'):
        suffix = a
    elif a == '--overwrite':
        overwrite = True
    elif a == '--preview':
        preview = True

script = HERE / 'pkgs' / (pkg + '.py')
if not script.exists():
    raise SystemExit(f'找不到包脚本：{script}')

ns = runpy.run_path(str(script))
frames = ns['build']()
title = ns.get('TITLE', pkg)

if preview:
    S.dump_preview(frames, str(HERE / '_qa' / f'_preview-{pkg}{suffix}.png'), title)
else:
    S.export(str(HERE / (pkg + suffix)), title, frames, overwrite=overwrite)
