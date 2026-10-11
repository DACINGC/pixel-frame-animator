# 怪物帧动画包 —— 共享工程约定（4 个怪物必须统一）

同一套规范、同一画布尺寸、同一图层结构，保证 4 个怪物能直接拼进同一张图集。

## 0. 环境与资源

- 解释器（Pillow 12.3.0 已装在隔离 venv，禁止再装包、禁止用其它 python）：
  `C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
- 模板（复制它，改副本，绝不改原文件）：
  `C:/Users/Administrator/.workbuddy/skills/pixel-frame-animator/scripts/frame_anim_template.py`
- 绘制规范（出问题先查它的「常见失败对照表」）：
  `C:/Users/Administrator/.workbuddy/skills/pixel-frame-animator/references/pixel-drawing-spec.md`
- 已有成果参考：`../demo/contact-sheet-8x.png`

## 1. 硬性约定（违反就不像素画）

1. `SIZE = 32`（32×32 正方形）。四个怪物统一，**任何情况都不要改成 64**。
2. 有限调色板 ≤ 16 色；索引 0 = `(0,0,0,0)` 透明；其余颜色 alpha 必须 255（禁止半透明）。
3. 索引 1 = 描边深色 `(34,30,44,255)`。
4. `fill=` / `outline=` 一律传**调色板索引**，绝不能传 RGB（传了不报错但角色会大面积变黑/怪色）。
5. 只画硬边：放大一律 `Image.Resampling.NEAREST`（模板已处理，不要改）。
6. 主色块外要有索引 1 描边；但**宽度 ≤ 4px 的小部件（眼睛、眼球高光）不要 outline**，
   改用下方/单侧 1px 暗线定位，否则会被描边吃成黑块。
7. **锚点常量写死**（如 `TOP_Y = 8`、`BASE_Y = 24`、`FOOT_Y = 28`），姿态参数只做**相对**偏移。
   绝不逐帧重算绝对坐标，否则播放时角色会呼吸式抖动。
8. 帧间必须有真实差异 —— 模板校验器会拒绝重复帧（`IDENTICAL_POSES`）。
   判定标准：相邻帧不能只是整体平移，必须有不同的部位做不同的偏移。
9. **所有帧统一面朝左**，中途不得翻转。
10. 输出目录必须是全新空目录（模板会拒绝已存在的目录）。

## 2. 图层结构（沿用模板，四层自下而上）

`LAYER_ORDER = ['back', 'body', 'weapon', 'fx']`

| 层 | 怪物身上放什么 |
|---|---|
| `back` | 身后的部件：翅膀、尾巴、菌褶阴影、背后的尘土 |
| `body` | 主体：躯干/头部/四肢 + 五官 |
| `weapon` | 身前的部件：爪、牙、角、触手、喷出的攻击物（没有武器也要用这层放"身前件"） |
| `fx` | 特效：命中弧光、冲击星、孢子云、尘土、消散粒子 |

## 3. 姿态参数（在模板 pose() 基础上扩展）

通用：`dy`（整体上下，正=下沉）、`lean`（整体左右倾）、`squash`（挤压量，正=压扁变宽）、
`flash`（0 正常 / 1 受击闪白）、`fx`（特效名或 None）。
角色专属参数自取（如 `wing`、`hop`、`split`），但**必须统一走 `pose()` 一个入口**。

**受击闪烁的实现**：`flash=1` 时把 body 层的主色/亮部/暗部索引整体替换成亮色（建议索引 5 白，
描边换成索引 8 红），并配合 `squash=+1` 压扁 + 眼睛变成"X"或横线。禁止用半透明做闪烁。

## 4. 动作与帧数（每个怪物 14 帧，拆成 2 个包，每包 ≤ 8 帧）

| 动作 | 帧数 | 编排要点 |
|---|---|---|
| `move` | 4 | 循环动作；**收尾帧必须接近起始帧**，否则 loop 会跳帧 |
| `attack` | 4 | 起手 → 蓄力拉开 → 命中帧（带 `fx`）→ 收势 |
| `hit` | 2 | 第 0 帧 `flash=1` 压扁；第 1 帧回弹（可带一点受击红） |
| `death` | 4 | 非循环、逐帧衰减：踉跄 → 倾倒 → 摊平/散架 → 最后一帧只剩少量残骸 + 尘埃 |

包分组：`PACKS = {'locomotion': ['move', 'hit'], 'combat': ['attack', 'death']}`

## 5. 脚本与输出路径

```
pixelwork/monsters/<name>/gen_<name>.py                 # 生成脚本（从模板复制改造）
pixelwork/monsters/<name>/<name>-move-hit/              # 包 A：move_0..3 + hit_0..1
pixelwork/monsters/<name>/<name>-attack-death/          # 包 B：attack_0..3 + death_0..3
```

运行方式（第二个参数选包，缺省跑两个包）：

```bash
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" gen_<name>.py <outdir> locomotion
"$PY" gen_<name>.py <outdir> combat
```

每个包内含：`frames/*.png`、`sprite-sheet.png`、`contact-sheet-8x.png`、
`atlas.json`、`palette.json`、`manifest.sha256`。

## 6. 目检（强制，不可跳过）

机械校验通过 ≠ 好看。生成后**必须用 Read 工具打开 `contact-sheet-8x.png` 真实看图**，逐帧检查：

1. 轮廓：主色块是否清晰、有没有被背景吃掉
2. 姿态差异：相邻帧看得出动作推进，而不是整体平移
3. 部位一致：眼睛、爪、翅膀在帧间没有错位或消失
4. 不截断：手脚、翅膀、特效有没有被 32×32 边界切掉

发现一处问题就改参数重跑到**新目录**（加后缀 `-r2`、`-r3`，绝不覆盖旧包），最多迭代 3 轮。
最后用 `sha256sum -c manifest.sha256` 复核包完整性。
