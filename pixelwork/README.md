# pixelwork 目录结构

```
pixelwork/
├── README.md              ← 本文件，结构说明
├── GUIDE.md               ← 方法论：图片怎么生成的、绘制约定、如何让其他Agent复用
│
├── template/              ← 【纯净模板】独立、可复制给任何 Agent
│   ├── frame_anim_template.py    只依赖 Pillow 的通用模板
│   └── README.md                 三步上手说明
│
├── archer/                ← 【本次角色：原创像素弓箭手·云纹游侠】
│   ├── gen_project.py            角色设计脚本（参数化绘制 → 工程 JSON）
│   ├── gen_extra.py              追加动作脚本：死亡 / 大招（复用 gen_project 的造型代码）
│   ├── project/                  3 个可编辑工程 JSON（同源：行走+跳跃 / 攻击+奔跑 / 闪避）
│   └── delivery/                 最终交付包（已 verify + 目检通过）
│       ├── v2-walk-jump/         行走4 + 跳跃4
│       ├── v2-attack-run/        攻击4 + 奔跑4
│       ├── v2-dodge/             闪避4
│       ├── v3-death/             死亡6（受击→踉跄→跪地→倾倒→躺地→消散）
│       └── v3-ultimate/          大招8（起手→满弦→聚能→腾空→光矛→余波→回落→收势）
│
├── demo/                  ← 模板运行示例输出（示例角色「斗篷剑士」16 帧）
│
└── _archive/              ← 历史版本，保留不删除（可安全清理）
    ├── fresh/                    v1 行走+跳跃（已被 v2 取代）
    ├── fresh-attack-run/         v1 攻击+奔跑
    ├── fresh-dodge/              v1 闪避
    ├── cloud-archer.json         v1 的 20 帧单工程版本（超出 8 帧上限，已拆包）
    └── _zoom_*.png               目检用临时放大图
```

## 交付包的 SHA256（务必自行保存，后续改图复核需要）

| 包 | manifest SHA256 |
|---|---|
| `archer/delivery/v2-walk-jump` | `ce65c8712e66b0f2123d731c970bfaae04459acb5e43a02fad9f0f60243f84cd` |
| `archer/delivery/v2-attack-run` | `f40b2ffbb0647190b5df42faf6700c28d10864c26050a3805f8d10842b494949` |
| `archer/delivery/v2-dodge` | `f35c23a46ef8714ae77404602e53941dd9f9777ec3890cc8d2a6a39848d343d9` |
| `archer/delivery/v3-death` | `826273cc677eb7aef9f5c6a5555212a61a1266ed18d5f951049b90d9a80ab29b` |
| `archer/delivery/v3-ultimate` | `dc85525049c7dc5248ea655099bc1031b20ebf4d26bcd392ad084ebaeb6a84dd` |

上表的 SHA256 是 `manifest.sha256` **文件本身**的哈希（包外留存，用于事后确认包没被改动）。
**这些包保持原样、不重新导出** —— 一旦重 `build`，上表登记值就失效了。

### 历史包的 manifest 有个已知坑

`v3-death`、`v3-ultimate`、`demo` 由旧导出逻辑生成，它们的 `manifest.sha256` 记的是
**内存 RGBA 哈希**（而不是 PNG 文件哈希），且行尾是 CRLF。因此：

```bash
sha256sum -c manifest.sha256     # 在这几个包里会全部 FAILED，这是格式问题，不是文件损坏
```

复核这些旧包请用 `atlas.json` 中每帧的 `rgba_sha256`，比对 `frames/*.png` 解码后的 RGBA 字节。

`gen_extra.py` 与 `template/frame_anim_template.py` 已修正为「PNG 文件哈希 + LF 行尾」，
**之后新出的包**可以直接 `sha256sum -c` 复核；旧包不追溯修改。

## 快速上手

- 想**预览/检查这些动画** → 运行 `viewer/start.bat`（或 `python viewer/serve.py`），浏览器自动打开
- 想**换个新角色做动画** → 复制 `template/`，按 `template/README.md` 三步改
- 想**改弓箭手的某一帧** → 改 `archer/gen_project.py`（基础动作）或 `archer/gen_extra.py`（死亡/大招）的姿态参数 → 重新出包（不要覆盖旧包）
- 想**搞懂原理和约定** → 看 `GUIDE.md`
