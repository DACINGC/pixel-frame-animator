# 纯净像素帧动画模板

只依赖 **Pillow** 的独立模板，不依赖任何专家插件，可直接复制给其他 Agent 使用。

## 目录内容

| 文件 | 作用 |
|---|---|
| `frame_anim_template.py` | 模板本体：配置 → 绘制 → 渲染 → 导出，约 200 行，可直接运行 |

## 三步做出你自己的角色动画

1. **改配色**：修改 `PALETTE`，索引 0 必须是透明 `(0,0,0,0)`，颜色数 ≤ 16。
2. **改造型**：改 `draw_back / draw_body / draw_weapon / draw_fx` 四个函数，
   用 `rect / ell / seg / d.polygon` 在 64×64 网格上画，`fill` 填的是**调色板索引**（不是 RGB）。
3. **填动作**：改 `ACTIONS` 字典，每个动作一组姿态参数，一帧一组。

## 运行

```bash
python frame_anim_template.py                # 输出 ./demo-output
python frame_anim_template.py 你的输出目录    # 指定输出目录（必须是空的新目录）
```

输出目录内容：`frames/*.png`（逐帧）、`sprite-sheet.png`、`contact-sheet-8x.png`（8 倍放大目检用）、
`atlas.json`（帧序与坐标）、`palette.json`、`manifest.sha256`。

__`manifest.sha256` 记的是 PNG 文件的字节哈希__，因此可以直接用系统工具复核：

```bash
cd 输出目录 && sha256sum -c manifest.sha256
```

`atlas.json` 里每帧的 `rgba_sha256` 是**内存 RGBA 哈希**，只用于帧间去重，不要拿它跟 PNG 文件比对。

## 姿态参数约定（改动作只改参数，不动造型代码）

| 参数 | 含义 |
|---|---|
| `dy` | 整体上下位移，正=下沉 |
| `lean` | 身体前倾像素 |
| `legs` | 0并立 1左前 2右前 3收腿 4大跨 |
| `swing` | 披风/头发摆动像素 |
| `arm` | 手坐标 `(x,y)`，`None`=垂放 |
| `fx` | 特效名：`'slash'`斩击 / `'dust'`扬尘 / `None` |

## 硬性规范（违反就不是像素画）

- 有限调色板 ≤ 16 色，索引 0 = 透明
- 只画硬边，放大一律 `NEAREST`，禁止抗锯齿/模糊
- 头/腰/脚锚点固定，姿态只做相对偏移，否则帧间抖动
- 每帧姿态必须有真实差异
- 出图后必须真实打开 `contact-sheet-8x.png` 目检，机械校验通过 ≠ 好看
