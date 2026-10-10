# 帧动画浏览器

本地零依赖的像素帧动画查看器：扫描工作区里所有动画包（atlas.json / frames 目录 / png 序列），
在浏览器里播放、逐帧检查、看图集、导出 GIF。

## 启动

```
viewer/start.bat          # Windows：启动本地服务并自动打开浏览器
bash viewer/start.sh      # macOS / Linux
python viewer/serve.py --port 9000 --no-browser   # 自定义参数
```

默认地址 `http://127.0.0.1:8765`。服务运行期间新增的动画包，点右上角「⟳ 重新扫描」即可看到。

没有 Python 服务时也可以直接双击 `index.html`（file:// 离线模式），
但索引来自上次 `python scan.py --static` 生成的 `data.js`，不能实时刷新和导出 GIF。

## 功能

- **资源树 + 搜索**：按目录分组展示所有动画集，可搜索动画/动作名，可隐藏 `_archive` 归档
- **播放器**：播放/暂停、逐帧、FPS 1–30、循环、往复（ping-pong）、缩放（适应/1x–16x，最近邻硬边）、
  背景（棋盘格/深色/浅色/绿幕/品红）、洋葱皮（叠上一帧残影）、像素网格 + 中轴基线
- **动作分段**：按帧名前缀（walk_0 → walk）自动拆分动作，点击 chips 切换
- **帧网格**：全部帧平铺预览，点击任意帧回到播放器定位
- **图集视图**：sprite-sheet.png 上叠加每帧的 rect 框，点击选帧
- **详情**：当前帧 id/文件/rect/sha、工程调色板色板
- **导出 GIF**：按当前动作、FPS、缩放、背景导出（透明背景保留 alpha）
- **打开文件夹**：在系统文件管理器中定位该动画包

## 快捷键

| 键 | 功能 |
|---|---|
| 空格 | 播放 / 暂停 |
| ← / → | 上一帧 / 下一帧（Shift 步进 5） |
| Home / End | 首帧 / 末帧 |
| ↑ / ↓ | FPS ±1 |
| + / − / F | 缩放 +/− / 适应窗口 |
| O / G | 洋葱皮 / 网格 |
| 1 / 2 / 3 | 播放器 / 帧网格 / 图集 |
| / | 聚焦搜索 |

## 文件

```
viewer/
├── start.bat / start.sh   启动脚本
├── serve.py               本地服务：/api/scan 实时扫描、/files 读文件、/api/gif 导出、/api/open 定位
├── scan.py                目录扫描器（识别 atlas.json / frames/ / png 序列）
├── gif.py                 零依赖 GIF 导出（自带 PNG 解码 + GIF89a/LZW 编码，Pillow 可用则走 Pillow）
├── index.html / viewer.css / viewer.js   前端界面
├── data.js                离线兜底索引（scan.py --static 生成）
└── exports/               导出的 GIF 存放处
```

## 动画包识别规则

满足任一条件即认定为一个动画集（命中后不再向下递归）：

1. 目录含 `atlas.json` 且带 `frames` 数组 —— 以图集清单为准（含 rect、调色板、工程信息）
2. 目录含 `frames/` 子目录且其中有 png —— 按文件名自然排序
3. 目录本身有 ≥2 张 `xxx_0.png` 风格的序列图

动作分段取帧 id 去掉尾部序号（`walk_0` → `walk`），atlas 里的 `action` 字段优先。
以 `_` 开头的目录只按规则 1 识别（避免临时放大图混入）。
