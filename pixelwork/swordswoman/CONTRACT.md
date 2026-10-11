# 金发双马尾女剑士 —— 共享工程契约（7 个子 Agent 必须统一）

> **本文件与 `sw_lib.py` 由主 Agent 独占，子 Agent 只读，禁止修改。**
> `sw_lib.py` 冻结哈希：`7023d9109ec52d7e6bce74a571ea27a4e49c3a83377ed76e81c1dc96b349eddd`
> 回报时必须附上你本地的 `sha256sum sw_lib.py` 以证明没改。

## 0. 环境与资源

- 解释器（Pillow 12.3.0 已装在隔离 venv，禁止再装包、禁止用其它 python）：
  `C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
- 绘制规范（出问题先查它的「常见失败对照表」）：
  `C:/Users/Administrator/.workbuddy/skills/pixel-frame-animator/references/pixel-drawing-spec.md`
- 运行：在 `pixelwork/swordswoman/` 下 `python run.py <包名>`；
  迭代重跑同名包加 `--overwrite`（只覆盖本脚本会写的文件）；只看不建包用 `--preview`。

## 1. 硬性约定

1. `SIZE = 64`，全帧**面朝左**，中途不得翻转。
2. 16 色调色板；索引 0 = `(0,0,0,0)` 透明；其余 alpha=255，**禁半透明**。
3. `fill=` / `outline=` 一律传**调色板索引**，传 RGB 不报错但会大面积画错色。
4. 索引 1 = 描边 `(46,34,54)`；主色块外一圈描边；**≤4px 部件（眼睛）不描边**。
5. 闪白只走 `flash` 参数（纯索引 remap）；`0/5/6/7/13/14/15` 绝不进 remap 表
   （否则闪白帧瞳孔/发带消失）。
6. **锚点写死**：`CX=32 HEAD_Y=8 HEAD_BOT=23 EYE_Y=15 SHOUL_Y=28 WAIST_Y=33 HIP_Y=36
   HEM_Y=41 FOOT_Y=58 SWORD_LEN=30`；姿态只做相对偏移。
7. `dy ≤ DY_MAX[legs]` = `{0:4, 1:4, 2:4, 3:7, 4:4, 5:4, 6:3, 7:4}`；
   `fx='dust'` → dy ≤ +1；`fx='slash-heavy'` → dy ≤ +2；`fx='slash-up'` → lean ≤ −3；
   `fx='afterimage'` → lean ≥ +6。
8. 帧间必须有真实差异（同一 clip 内重复帧会被拒绝；跨 clip 关节帧允许相同）。
9. 帧 id 严格 `<clip>_<n>`（如 `walk_0`、`idle-guard_1`）—— viewer 靠前缀拆动作。
10. 循环动作收尾帧必须接近起始帧；死亡/大招等非循环动作除外。
11. 循环动作的动画必须「看得出推进」：相邻帧至少 2 个部件做**不同方向**的偏移，
    整体平移不算差异。

## 2. 剑的几何（只认公式，禁止用"朝左下"这类文字）

```
剑尖 = 手 + 30 × (cos deg, −sin deg)      # 画布 y 向下；手 = (arm[0], arm[1]+dy)
deg: 0=画面右(身后)  90=正上  180=画面左(正前)  270=正下
硬约束（export 自动断言）：
  · 剑尖 ∈ x[2,61] y[2,60]
  · 剑身线段与头框 (CX+lean−10, 8+dy)..(CX+lean+6, 23+dy) 零交点
  · lean − 2·swing ∈ [−14, 13]（否则马尾出界）
```

## 3. fx 注册表（只能从中选，需要新的立即回报主 Agent）

注意：Pillow 的 arc 在图像坐标下是**顺时针**（270°=顶部），所有弧特效的几何都按
「弧顶不高于眼(15+dy)」校准过：

| fx | 层 | 几何 | 硬约束 |
|---|---|---|---|
| `dust` | fx | 尘团最低行 62+dy | **dy ≤ +1** |
| `slash-up` | fx | 竖向大弧 bbox (6,4+y,56,52+y)，弧顶 y=4+dy（头顶上方） | **lean ≤ −3** |
| `slash-wide` | fx | 横扫弧 bbox (2,24+y,48,52+y)，弧顶 y=24+dy 在脸底(23+dy)之下 | 无 |
| `slash-heavy` | fx | 左半重弧 bbox (20,4+y,52,56+y)+地面冲击线，弧身只在脸下/脸左 | **dy ≤ +2** |
| `thrust` | fx | 水平冲线（手 y 高度）+白色箭头 | 与该帧剑身同线 |
| `afterimage` | fx | 原地白色简化轮廓 x 22~38 | **本体 lean ≥ +6** 让开 |
| `charge` / `charge-max` | fx | 脚下能量池+粒子；charge-max 顶弧 y=10+dy（眼上方） | — |
| `burst` | fx | 身前(x−14)冲击环 | — |
| `burst-wide` | **fx_back** | 屏幕级扩散环（放 backfx 层） | — |
| `spark` | fx | 残留火星 | — |

**没有 `slash`**（旧版天生出框，已删除）。

## 4. 连招关节帧（硬一致，一个数字都不许改）

| 关节 | 相等关系 | arm | dy | deg | lean | legs |
|---|---|---|---|---|---|---|
| J1 | atk1_3 == atk2_0 | (38,31) | 0 | 220 | −1 | 2 |
| J2 | atk2_3 == atk3_0 | (45,34) | −1 | 98 | −2 | 2 |
| J3 | atk3_3 == atk4_0 | (44,31) | 0 | 170 | +1 | 1 |
| J4 | atk4_3 == atk5_0 | (41,33) | +1 | 212 | 0 | 1 |

（swing/skirt/tail 允许 ±2 惯性差，其余硬一致；`_qa/check_combo.py` 会机器断言）

## 5. 交付与目检

每包产物：`frames/*.png`、`sprite-sheet.png`、`contact-sheet-8x.png`、`atlas.json`、
`palette.json`、`manifest.sha256`、`poses.json`。
目检（强制）：用 Read 打开 `contact-sheet-8x.png`，检查
① 轮廓清晰不被背景吃掉 ② 相邻帧看得出动作推进而非整体平移
③ 眼睛/发带/双马尾帧间不消失不错位 ④ 手脚剑尖特效不被 64 边界切掉。
不过就改参数 → `--overwrite` 重跑，最多 3 轮；中间预览用 `--preview`（写 `_qa/`）。

## 6. 十个交付包与分工

| 包 | clips | 帧数 | Agent |
|---|---|---|---|
| `sw-walk-run` | walk_0..3, run_0..3 | 8 | A |
| `sw-idles` | idle_0..3, idle-guard_0..3 | 8 | A |
| `sw-jump-climb` | jump_0..3, climb_0..3 | 8 | B |
| `sw-dodge-slide` | dodge_0..3, slide_0..3 | 8 | B |
| `sw-hurt` | hurt_0..3 | 4 | C |
| `sw-death` | death_0..5 | 6 | C |
| `sw-ultimate` | ultimate_0..7 | 8 | D |
| `sw-atk12` | atk1_0..3, atk2_0..3 | 8 | E |
| `sw-atk34` | atk3_0..3, atk4_0..3 | 8 | F |
| `sw-atk5` | atk5_0..3 | 4 | G |

基线脚本已在 `pkgs/`，全部通过机械校验。**子 Agent 的职责是让它"看起来对"**：
逐帧目检 → 调整姿态参数（dy/lean/legs/swing/skirt/tail/arm/deg/head/fx）→ 重跑 → 再目检。
参数可以大改，但①关节帧硬一致 ②fx 注册表 ③第 1 节硬约束 不可破。
