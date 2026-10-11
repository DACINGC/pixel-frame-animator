# 金发双马尾女剑士（swordswoman）

64×64 像素女剑士全套帧动画：**16 个动作 / 70 帧 / 10 个交付包**。
架构 = 一个共享造型库 `sw_lib.py`（唯一定义源）+ `pkgs/` 下 10 个只填姿态参数的包脚本，
由主 Agent 建库、7 个子 Agent 并行目检调参完成。

## 动作清单

| 包目录 | clips | 帧数 | 说明 |
|---|---|---|---|
| `sw-walk-run` | walk / run | 4+4 | 行走（contact→passing 节奏）、奔跑（前倾+后飘马尾） |
| `sw-idles` | idle / idle-guard | 4+4 | 两套待机：剑尖垂地呼吸 vs 横剑戒备 |
| `sw-jump-climb` | jump / climb | 4+4 | 跳跃起落弧；攀爬（扣握手绝对高度守恒+换手） |
| `sw-dodge-slide` | dodge / slide | 4+4 | 闪避（原地残影）；滑铲（4 帧全低姿循环） |
| `sw-hurt` | hurt | 4 | 受伤闪烁：flash 三级衰减（纯索引 remap，瞳/发带不变色） |
| `sw-death` | death | 6 | 受击→踉跄→跪地→前扑→蜷缩+X 眼+裙摆铺地 |
| `sw-ultimate` | ultimate | 8 | 大招能量斜坡：聚气→charge→下劈→burst-wide→余波 |
| `sw-atk12` | atk1 / atk2 | 4+4 | 连招①横斩 ②上挑 |
| `sw-atk34` | atk3 / atk4 | 4+4 | 连招③突刺 ④回旋斩（spin 气流） |
| `sw-atk5` | atk5 | 4 | 连招⑤下劈终结+拄剑收势 |

**连招衔接**：五段攻击首尾相接，关节帧 J1~J4 硬一致（收势 == 下段起手），
机器断言见 `_qa/check_combo.py`（跑通输出 `J1..J4 OK`）。

## 复核

```bash
cd <包目录> && sha256sum -c manifest.sha256
"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" _qa/finalize.py
```

## manifest.sha256 文件自身哈希（包外登记，重 build 即失效）

| 包 | SHA256 |
|---|---|
| sw-walk-run | `1109d6dc6cfbf4e15b867ceb7935190f3a923167d189edd2b9013d7e54715fca` |
| sw-idles | `49e5aa71480df086e5c4c31e19a4084048c636bb0fdfdfd67147f9b51e88762f` |
| sw-jump-climb | `8dc75771a40bdd4714c937081af15aa3c8cc9536b647a51017a6416a2a57e6b7` |
| sw-dodge-slide | `d3435fa4f7de941633c50480cb070ba200ecff998db0de2f990c47902f65e197` |
| sw-hurt | `086ee450fe236af056ce340166d763ccac1cc8728b5b1632b4baeb87ce6bd410` |
| sw-death | `1b00eddc0240d063ae35b1d8788a7a60259b3fee04a241c10a74419eff7cdfe8` |
| sw-ultimate | `2d76bb1ab742444d5bf4a53594e696d597b5103925ee8265e5c1cf741818f03b` |
| sw-atk12 | `7273f22f39fccb4c586c9f6a9893f5a63ba1da736540532eecdf3491a79f67c1` |
| sw-atk34 | `e9fa9c5d5924ba4fab9abe8f1cb7ccdae4d157b2dc5dddd3d1893e544c928f2a` |
| sw-atk5 | `744036c14cc662c4b4fc40295c687253603566e453dffa1122ac886356ecb13b` |

## 结构与迭代

```
sw_lib.py      造型唯一定义源（PALETTE/锚点/部件函数/fx 注册表/校验断言）
CONTRACT.md    共享契约（硬约束/剑几何公式/关节帧表/分工）
run.py         运行器：python run.py <包名> [--overwrite|-r2|--preview]
pkgs/*.py      10 个包脚本（只含 TITLE + build() 姿态参数表）
sw-*/          交付包（frames/ + sprite-sheet + contact-sheet-8x + atlas + palette + manifest + poses）
_qa/           校验脚本与中间图（check_combo / finalize / _overview，_ 前缀不被 viewer 收录）
_archive/empty-shells/   上一轮遗留的空壳目录（只移动未删除）
```

改某一帧：改 `pkgs/<包>.py` 的姿态参数 → `python run.py <包> --overwrite` → 目检
`contact-sheet-8x.png`。**绝不覆盖旧包直接改 PNG**；需要保留旧版就输出到 `<包>-r2`。
