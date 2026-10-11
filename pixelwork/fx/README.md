# 特效帧动画包（fx）

程序化点阵绘制的通用战斗特效，32×32、透明底、≤16 色，可直接叠在
`../monsters/` 的 32px 怪物或其它 32px 角色上播放。

共享约定见 [CONTRACT.md](CONTRACT.md)。命名 `<clip>_<i>.png`，
查看器（`viewer/`）按前缀自动拆分动作。

## 包索引

| 包 | 动作（帧数） | 类型 | 说明 |
|---|---|---|---|
| `fx-impact-r2` | impact (4) / slash (4) | 单发 | 命中冲击星芒（白闪→星芒张开→最大+碎屑→收缩衰减）、斩击弧光（细弧→扫过加宽→最亮白核→断裂消散） |
| `fx-boom-r2` | explode (6) | 单发 | 爆炸：小闪→膨胀→最大（白心+冲击环）→分裂→烟+火星→烟圈消散 |
| `fx-smoke-r3` | smoke (6) | 循环 | 烟雾升腾翻滚消散，末帧接近首帧，可无缝 loop |
| `fx-dust-r3` | dust (4) | 循环 | 跑动脚下扬尘：起尘→扩散→后飘→变淡，整体偏下（中心 y≈23） |
| `fx-cast` | charge (4) / burst (4) | 连招 | 施法蓄力（光点聚集→法阵全开→收拢→蓄满）接技能爆发（光柱→放射星→衰减→余辉） |

## 叠放建议

- 特效以中心锚点 `CX=16, CY=16` 对齐受击点（`fx-dust` 对齐脚下 `GROUND_Y=24`）。
- 播放层在角色层之上；`fx-impact` / `fx-boom` 建议配受击闪白（怪物包 `flash=1`）同帧触发。
- `fx-cast` 的 charge 末帧（蓄满小亮点）正好接 burst 首帧，按 charge→burst 连播。

## 产物

- 每个包内含 `frames/*.png`、`sprite-sheet.png`、`contact-sheet-8x.png`、
  `atlas.json`、`palette.json`、`manifest.sha256`（`sha256sum -c manifest.sha256` 可复核）。
- `_overview-dark.png` / `_overview-light.png`：全部定稿包的总览图（深/浅底各一张），
  用 `python make_overview.py` 重新生成。文件名带 `_` 前缀是为了不让查看器把
  `fx/` 目录本身误判成 png 序列。
- `-rN` 后缀为目检迭代版本，历史包按「永不覆盖」保留；定稿版见上表。

## 重新生成

```bash
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" gen_impact.py fx-impact-r2
"$PY" gen_boom.py   fx-boom-r2
"$PY" gen_smoke.py  fx-smoke-r3 smoke
"$PY" gen_smoke.py  fx-dust-r3  dust
"$PY" gen_cast.py   fx-cast
```
