# 怪物帧动画包（slime / bat / skeleton / shroom）

4 个怪物 × 4 动作（移动 move / 受击闪烁 hit / 攻击 attack / 死亡 death），
每个怪物 14 帧，拆成 2 个同源包（每包 ≤ 8 帧）。画布 32×32、面朝左、
有限调色板 ≤16 色（索引 0 透明）、放大一律 NEAREST。
全部由 Python + Pillow 程序化点阵绘制（同一造型函数在不同姿态参数下重绘），
共享约定见 `CONTRACT.md`，可视化预览打开 `preview.html`。

## 最终交付包

| 怪物 | 包 A（locomotion） | 包 B（combat） | 生成脚本 |
|---|---|---|---|
| 史莱姆 | `slime/slime-move-hit-r4` | `slime/slime-attack-death-r4` | `slime/gen_slime.py` |
| 洞穴蝙蝠 | `bat/bat-move-hit` | `bat/bat-attack-death` | `bat/gen_bat.py` |
| 骷髅小兵 | `skeleton/skeleton-move-hit-r2` | `skeleton/skeleton-attack-death-r2` | `skeleton/gen_skeleton.py` |
| 毒蘑菇怪 | `shroom/shroom-move-hit` | `shroom/shroom-attack-death` | `shroom/gen_shroom.py` |

包内文件（每个包相同）：

```
frames/*.png          逐帧 32×32 RGBA 透明底（move_0..3 / hit_0..1 / attack_0..3 / death_0..3）
sprite-sheet.png      横向精灵表
contact-sheet-8x.png  8 倍联系表（目检用）
atlas.json            帧序、rect、调色板大小、图层顺序
palette.json          调色板（索引 -> RGBA）
manifest.sha256       每帧 PNG 的 SHA256，可 sha256sum -c 复核
```

总览拼图：`overview-4x.png`（每行一个怪物，14 帧按 move→hit→attack→death 排列）。

## 动作编排（四怪物统一节奏）

- `move` 4 帧：循环动作，收尾帧贴近起始帧（史莱姆/蘑菇=弹跳挤压，蝙蝠=振翅悬飞，骷髅=迈步行走）
- `hit` 2 帧：第 0 帧 `flash=1` 身体整体闪白 + 描边转红 + 眼变横线 + 压扁；第 1 帧回弹带受击暗红
- `attack` 4 帧：起手 → 蓄力 → 命中帧（带 fx：史莱姆伪足+冲击星、蝙蝠咬击弧光、骷髅挥刀斩弧、蘑菇孢子云）→ 收势
- `death` 4 帧：非循环逐帧衰减，最后一帧只剩少量残骸 + 飘散尘埃

## 重新生成

```bash
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd <怪物目录>
"$PY" gen_<name>.py <父目录> locomotion   # 生成 move+hit 包
"$PY" gen_<name>.py <父目录> combat       # 生成 attack+death 包
```

输出目录必须是不存在的新目录（脚本会拒绝覆盖）。

## 目检结论（主 Agent 复核 8 张 contact-sheet-8x.png 后）

- 四怪物轮廓清晰、相邻帧动作推进明确、五官/部件帧间无错位、无边界截断
- 8 个包 `sha256sum -c manifest.sha256` 全部 OK（6+8+6+8+6+8+6+8 = 56 帧）
- 注意：`death_3`（四怪物均是）是刻意的极稀疏残骸帧，图集工具不要按包围盒裁剪，保留完整 32×32 cell
- `bat` 的 `lean` 参数安全值 |lean| ≤ 2，超出会把翼尖推出画布

## 历史包说明

目录名带 `-r1/-r2/-r3/-r4` 后缀的历史包为目检迭代过程产物，按「永不覆盖」约定保留用于回滚对比。
当前最终版：slime 用 `-r4`、skeleton 用 `-r2`、bat/shroom 用无后缀的官方路径名。
