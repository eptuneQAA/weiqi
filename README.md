# 围棋

桌面围棋软件，支持人机对战、局域网双人对战、房间内文字聊天和图文新手帮助。

## 运行

```bash
python3 main.py
```

依赖：Python 3.7+、PyQt5。若系统未安装：

```bash
pip3 install -r requirements.txt
```

## 安装包（deb）

构建安装包：

```bash
cd /home/UOS/weiqi
./build_deb.sh
```

产物为 `dist/weiqi_1.0.1_all.deb`。安装（会自动处理 PyQt5 依赖）：

```bash
sudo apt install ./dist/weiqi_1.0.1_all.deb
```

安装后可从开始菜单点击“围棋”启动，或在终端执行（程序位于 `/usr/games/weiqi`，UOS 默认 PATH 已包含该目录）：

```bash
weiqi
```

卸载：

```bash
sudo apt remove weiqi
```

## 新手帮助

菜单“帮助 -> 新手帮助”或按 F1 打开图文帮助中心，包含快速开始、气与提子、
禁入点与劫、眼与活棋、胜负与数子、操作说明、人机/联机指南、常见问题和术语表。
“帮助 -> 规则说明”可直接定位到棋盘与落子章节。

## 人机对战

菜单“对局 -> 人机对战”，选择 9/13/19 路、AI 难度和执子颜色。
AI 为内置纯 Python 引擎，棋力定位休闲；支持悔棋（一次撤销一个回合）。

## 局域网对战

1. 主机：菜单“对局 -> 创建局域网房间”，选择棋盘大小、执子颜色和端口。
   对话框会显示本机 IP。
2. 客机：菜单“对局 -> 加入局域网房间”，从自动发现列表选择房间，
   或手动输入主机 IP 和端口。
3. 双方可随时在侧栏聊天；聊天记录仅保存在内存中。

默认 TCP 端口 `45679`，UDP 发现端口 `45678`。若发现功能被防火墙拦截，
请使用手动 IP 连接。

同一台机器测试两个实例时，使用 `--no-discovery` 关闭 UDP 发现，避免端口冲突：

```bash
python3 main.py --no-discovery
```

## 规则

中国规则数子，贴目 7.5；禁止自杀；位置超级劫；双方连续停一手后进入数子，
可点击棋组标记死子，确认后计算胜负。

## 测试

```bash
python3 -m unittest discover -s tests -t .
```

（`-t .` 让 `tests` 作为包导入，从而在 `tests/__init__.py` 里先创建 offscreen
的 `QApplication`；不带 `-t .` 时 UI 冒烟测试会被跳过而不是报错。）

## 棋谱（SGF）

- 菜单“文件 → 保存棋谱…”（Ctrl+S）把当前对局存为 SGF（FF[4]，含贴目、让子、
  结果与死子标记）。
- 菜单“文件 → 打开棋谱…”（Ctrl+O）载入 `.sgf` 进入复盘模式，用 ← → 逐步查看，
  Home/End 跳到开局/末手。只读取主分支，变体会被忽略。
- 让子通过 `AB`/`HA` 写进棋谱，外部工具（Sabaki、KGS 等）可以直接打开。

## 持续集成（GitHub Actions）

`.github/workflows/ci.yml`，推送到 GitHub 后自动跑：

| 触发 | 行为 |
|---|---|
| push 到 `main` | 单元测试 → 构建 `weiqi_<版本>_all.deb` → 作为构建产物上传（保留 30 天） |
| Pull Request | 只跑单元测试（不消耗打包时间） |
| 推送 `v*` tag | 先校验 tag 与 `debian/changelog` 版本一致，然后构建 deb 并自动创建 Release、附上安装包 |
| 手动 | Actions 页面 “Run workflow” |

本地复现 CI 的打包步骤：

```bash
dpkg-buildpackage -us -uc -b      # 产物在上一级目录
lintian --info ../weiqi_*_all.deb # 仅提示，不阻断
```

发版流程：改 `debian/changelog`（版本号）→ 提交 → `git tag v1.1.0 && git push origin v1.1.0`，
Actions 会自动出包并挂到 Release 上。

## 性能

AI 的 playout 走增量候选点集合，落子路径不再整盘拷贝：

| 棋盘 | 优化前 | 优化后 | 提升 |
|---|---|---|---|
| 9 路 | 41 playout/s | 53 playout/s | 1.3× |
| 13 路 | 51 playout/s | 410 playout/s | 8× |
| 19 路 | 15 playout/s | 374 playout/s | 24× |

同样 3 秒预算下 19 路能多算 20 多倍的分支，棋力与响应都明显改善。复现：

```bash
python3 tools/bench_ai.py 普通 19 3
python3 tools/render_ui.py     # 无显示器环境下渲染主页/对局/复盘截图
```

## 设置与记忆

菜单“设置 → 选项…”可修改默认棋盘大小、AI 难度、执子、贴目、让子数和默认端口；
窗口尺寸、上次使用的配置与上次打开棋谱的目录都会记住（`QSettings`）。
