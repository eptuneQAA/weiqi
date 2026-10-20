# 围棋

桌面围棋软件，支持人机对战、局域网双人对战和房间内文字聊天。

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

产物为 `dist/weiqi_1.0.0_all.deb`。安装（会自动处理 PyQt5 依赖）：

```bash
sudo apt install ./dist/weiqi_1.0.0_all.deb
```

安装后可从开始菜单点击“围棋”启动，或在终端执行（程序位于 `/usr/games/weiqi`，UOS 默认 PATH 已包含该目录）：

```bash
weiqi
```

卸载：

```bash
sudo apt remove weiqi
```

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
python3 -m unittest discover -s tests -v
```
