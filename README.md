# pixel-frame-animator

用 **Python + Pillow 手工绘制**像素风格角色帧动画（行走 / 攻击 / 跳跃 / 奔跑 / 闪避 / 死亡 / 大招），
输出逐帧 PNG、精灵表、atlas 清单与 SHA 校验，并配一个零依赖的本地浏览器逐帧查看/导出 GIF。

> **不是 AI 扩散画图。** 每一帧都是脚本在 64×64 网格上用矩形、椭圆、多边形、线段
> 逐个像素画出来的。同一个角色模型在不同「姿态参数」下重新绘制 N 次，
> 而不是把一张图切成 N 块。

---

## 目录结构

```
.
├── README.md                 ← 本文件
├── .gitignore
│
├── pixelwork/                ← 绘制侧：脚本 + 工程 + 交付包
│   ├── GUIDE.md              方法论：图怎么生成、绘制约定、如何让其他 Agent 复用
│   ├── README.md             pixelwork 结构说明 + 交付包 SHA256
│   │
│   ├── template/             【纯净模板】独立、可复制给任何 Agent
│   │   ├── frame_anim_template.py    只依赖 Pillow 的通用模板（约 200 行）
│   │   └── README.md                 三步上手
│   │
│   ├── archer/               【示例角色：原创像素弓箭手「云纹游侠」】
│   │   ├── gen_project.py            基础动作生成脚本（参数化绘制 → 工程 JSON）
│   │   ├── gen_extra.py              追加动作：死亡 / 大招
│   │   ├── project/                  3 个可编辑工程 JSON
│   │   └── delivery/                 最终交付包（已 verify + 目检通过）
│   │
│   ├── demo/                 模板运行示例输出（示例角色「斗篷剑士」16 帧）
│   └── _archive/             历史版本，保留不删除
│
└── viewer/                   ← 查看侧：本地零依赖帧动画浏览器
    ├── start.bat / start.sh   一键启动（自动开浏览器）
    ├── serve.py               本地服务：实时扫描 / 读文件 / 导出 GIF / 定位文件夹
    ├── scan.py                目录扫描器（识别 atlas.json / frames/ / png 序列）
    ├── gif.py                 零依赖 GIF 导出（自带 PNG 解码 + GIF89a/LZW 编码）
    ├── index.html / viewer.css / viewer.js   前端界面
    └── README.md              完整功能与快捷键说明
```

---

## 快速开始

### 1. 预览 / 检查已有动画

```bash
# Windows
viewer\start.bat

# macOS / Linux
bash viewer/start.sh

# 或手动
python viewer/serve.py --port 9000 --no-browser
```

默认打开 `http://127.0.0.1:8765`。播放器支持逐帧、FPS 1–30、循环 / 往复、
最近邻缩放 1x–16x、棋盘格/绿幕背景、洋葱皮、像素网格与中轴基线，
并按帧名前缀自动拆分动作（`walk_0` → `walk`），可导出 GIF。

> 没有 Python 时也能直接双击 `viewer/index.html`（离线模式），
> 但索引需要先 `python viewer/scan.py --static` 生成，且不能实时刷新 / 导出 GIF。

### 2. 用模板做一个你自己的角色

```bash
cp -r pixelwork/template my-character
cd my-character
python frame_anim_template.py          # 输出 ./demo-output
python frame_anim_template.py ./out    # 或指定输出目录（必须是空的新目录）
```

三步：

1. **改配色** — 修改 `PALETTE`，索引 0 必须是透明 `(0,0,0,0)`，颜色数 ≤ 16。
2. **改造型** — 改 `draw_back / draw_body / draw_weapon / draw_fx` 四个函数，
   在 64×64 网格上画，`fill` 填的是**调色板索引**而不是 RGB。
3. **填动作** — 改 `ACTIONS` 字典，每个动作一组姿态参数，一帧一组。

姿态参数：`dy`（整体上下位移）、`lean`（前倾）、`legs`（0 并立 / 1 左前 / 2 右前 / 3 收腿 / 4 大跨）、
`swing`（披风头发摆动）、`arm`（手坐标）、`fx`（`slash` 斩击 / `dust` 扬尘 / `None`）。
**改动作只改参数，不动造型代码。**

### 3. 改示例角色的某一帧

改 `pixelwork/archer/gen_project.py`（基础动作）或 `gen_extra.py`（死亡 / 大招）的姿态参数 →
生成新包（**不要覆盖旧包**）。

---

## 依赖

- Python 3.8+
- [Pillow](https://pypi.org/project/pillow/)（本仓库用 12.3.0）—— `pip install pillow`
- `viewer/` 本身零第三方依赖（GIF 导出自带编解码，Pillow 可用时自动优先用 Pillow）

---

## 输出产物

每个动画包目录下：

| 文件 | 说明 |
|---|---|
| `frames/*.png` | 逐帧 RGBA PNG（透明底） |
| `sprite-sheet.png` | 精灵表 |
| `contact-sheet-8x.png` | 8 倍放大联系表，人工目检用 |
| `atlas.json` | 帧序、每帧 rect、调色板、工程信息 |
| `palette.json` | 调色板 |
| `manifest.sha256` / `manifest.json` | 完整性校验 |

---

## 绘制规范（违反就不是像素画）

1. **有限调色板** ≤ 16 色（含 0 号透明）。
2. **索引 0 必须是透明** `(0,0,0,0)`，其余颜色完全不透明（alpha=255）。
3. **画布必须是 16 / 32 / 64 正方形**（工程校验器强制）。
4. **只用硬边**：放大一律 `Image.Resampling.NEAREST`，**禁止抗锯齿 / 模糊 / 羽化**。
5. **透明底**：每帧带 alpha，方便直接铺进游戏场景。
6. **有描边**：主色块外一圈深色（索引 1），轮廓才清晰。
7. **关键锚点固定**：头、腰、脚基准坐标写死，姿态只做相对偏移——否则帧间人物会抖动 / 漂移。
8. **单工程帧数上限 8 帧**（校验器限制），超了就拆成多个同源工程包。
9. **帧间要有真实差异**：校验器会拒绝「所有帧渲染结果相同」的工程（`IDENTICAL_POSES`）。
10. **出图后必须人工看图**：机械校验通过 ≠ 好看。第一版正是靠放大目检才发现
    「绿瞳被描边吃成黑块」「持弓手悬空」两个问题。

角色分 4 个图层自下而上合成：`hair`（脑后长发）→ `body`（头/躯干/四肢）→ `bow`（武器）→ `fx`（特效）。

---

## 交付与复核流程

```
check  → 校验工程合法性（零写入，纯内存绘制核验）
build  → 生成新目录交付包（绝不覆盖旧成果）
verify → 用包外独立保存的 manifest SHA256 复核包完整性
目检   → 真实打开 8x 联系表逐帧判断：轮廓 / 姿态差异 / 部位一致 / 不截断
```

要改某一帧的某个部位，正确做法是：
**先读旧工程 + 提供 SHA → 生成 `revision+1` 的新工程 → 限定矩形区域修改 → 新旧对照 → 保留旧包**，
而不是直接覆盖原图。

示例角色「云纹游侠」的交付包与 SHA256 见 [`pixelwork/README.md`](pixelwork/README.md)，
共 5 个包 / 26 帧：行走 4、跳跃 4、攻击 4、奔跑 4、闪避 4、死亡 6、大招 8。

---

## 给其他 Agent 复用

- **方案 A（最快）** — 把 `pixelwork/template/frame_anim_template.py` 当骨架 + 上面的 10 条约定写进 prompt。
- **方案 B（推荐）** — 封装成 Skill，在 `SKILL.md` 里写清触发条件、10 条约定、调用流程、
  交付物清单与目检要求，之后任何会话都能按同一套规范出图。
- **方案 C** — 包成命令行 `pixelanim --character xxx.json --out dir`，适合批量或非 Python 环境。

详细的原理与约定见 [`pixelwork/GUIDE.md`](pixelwork/GUIDE.md)，
查看器的完整功能与快捷键见 [`viewer/README.md`](viewer/README.md)。
