# -*- coding: utf-8 -*-
"""
连招关节帧机器校验（CONTRACT 第 4 节 J1~J4）

读取 sw-atk12 / sw-atk34 / sw-atk5 的 poses.json，断言相邻包衔接帧硬一致
（arm / dy / lean / legs 与 sword 的 deg）：
    J1  atk1_3 == atk2_0
    J2  atk2_3 == atk3_0
    J3  atk3_3 == atk4_0
    J4  atk4_3 == atk5_0
swing / skirt / tail 允许 ±2 惯性差，超差只警告不判失败。

附带：把 atk1_0..atk5_3 共 20 帧拼成 _qa/_combo-overview.png（一行 20 帧、scale=4）。

用法（在 swordswoman/ 下）：
    python _qa/check_combo.py
退出码：0 = 全部通过或因包未定稿而跳过；1 = 存在硬一致字段不一致。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import sw_lib as S  # noqa: E402  （只用 contact_sheet，保持造型定义单一来源）

HARD_FIELDS = ('arm', 'dy', 'lean', 'legs')
SOFT_FIELDS = ('swing', 'skirt', 'tail')
JOINTS = [
    ('J1', 'sw-atk12', 'atk1_3', 'sw-atk12', 'atk2_0'),
    ('J2', 'sw-atk12', 'atk2_3', 'sw-atk34', 'atk3_0'),
    ('J3', 'sw-atk34', 'atk3_3', 'sw-atk34', 'atk4_0'),
    ('J4', 'sw-atk34', 'atk4_3', 'sw-atk5', 'atk5_0'),
]
OVERVIEW = [f'atk{i}_{n}' for i in (1, 2, 3, 4, 5) for n in range(4)]


def load_poses(pkg):
    path = ROOT / pkg / 'poses.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    return {f['id']: f['pose'] for f in data['frames']}


def sword_deg(pose):
    sw = pose.get('sword')
    if isinstance(sw, (list, tuple)):
        return sw[2]
    return sw  # 旧格式直接存 int


def fmt(v):
    if isinstance(v, (list, tuple)):
        return '(' + ','.join(str(x) for x in v) + ')'
    return str(v)


def main():
    cache = {}
    def poses(pkg):
        if pkg not in cache:
            cache[pkg] = load_poses(pkg)
        return cache[pkg]

    failed = []
    for name, pkg_a, fa, pkg_b, fb in JOINTS:
        pa, pb = poses(pkg_a), poses(pkg_b)
        missing = [f'{p}/poses.json' for p, d in ((pkg_a, pa), (pkg_b, pb)) if d is None]
        if missing:
            print(f'[combo] {name} 跳过：{"、".join(missing)} 缺失（并行 Agent 未定稿）')
            continue
        if fa not in pa or fb not in pb:
            print(f'[combo] {name} 跳过：帧 {fa} 或 {fb} 不在 poses.json 中（包未定稿？）')
            continue
        A, B = pa[fa], pb[fb]
        for field in HARD_FIELDS:
            va, vb = A.get(field), B.get(field)
            if va != vb:
                failed.append(f'{name}.{field}: {fa}={fmt(va)} vs {fb}={fmt(vb)}')
        da, db = sword_deg(A), sword_deg(B)
        if da != db:
            failed.append(f'{name}.deg: {fa}={da} vs {fb}={db}')
        for field in SOFT_FIELDS:
            va, vb = A.get(field, 0), B.get(field, 0)
            if abs(va - vb) > 2:
                print(f'[combo] {name} 警告：{field} 惯性差 {va} vs {vb}（±2 内允许，当前差 {abs(va-vb)}）')
        if not any(f.startswith(name + '.') for f in failed):
            print(f'[combo] {name} OK  {fa} == {fb}')

    # 附带：20 帧连招总览图
    imgs, missing = [], []
    for fid in OVERVIEW:
        pkg = 'sw-atk' + ('12' if fid.startswith('atk') and fid[3] in '12' else '34' if fid[3] in '34' else '5')
        png = ROOT / pkg / 'frames' / f'{fid}.png'
        if png.exists():
            imgs.append(__import__('PIL.Image', fromlist=['Image']).open(png))
        else:
            missing.append(f'{pkg}/{fid}.png')
    if missing:
        print(f'[combo] 总览图跳过：{", ".join(missing)} 缺失')
    elif imgs:
        out = HERE / '_combo-overview.png'
        S.contact_sheet(imgs, scale=4, cols=len(imgs)).save(out)
        print(f'[combo] 总览图已写出 {out}（{len(imgs)} 帧）')

    if failed:
        print('[combo] 失败：')
        for f in failed:
            print('  -', f)
        sys.exit(1)
    if len(failed) == 0 and all(poses(p) is not None for p in ('sw-atk12', 'sw-atk34', 'sw-atk5')):
        print('[combo] J1..J4 OK')
    else:
        print('[combo] 部分关节因包未定稿而跳过，待主 Agent 统一重跑')


if __name__ == '__main__':
    main()
