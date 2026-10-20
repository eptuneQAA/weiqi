# 围棋 deb 安装包设计规格

- 日期：2026-10-20
- 状态：已确认
- 项目路径：`/home/UOS/weiqi`
- 目标平台：UOS Desktop 20 / Debian 系，amd64 构建环境

## 1. 目标

为现有围棋程序生成标准 Debian 二进制安装包 `weiqi_1.0.0_all.deb`，满足：

1. 双击或用 apt 安装，自动安装 `python3-pyqt5` 依赖。
2. 安装后可从开始菜单点击“围棋”启动，也可在终端执行 `weiqi`。
3. 提供应用图标、桌面入口、man 手册和文档。
4. 构建过程可重复，构建时运行现有测试。
5. 卸载干净，不残留程序文件。

明确不做：AppImage/PyInstaller 独立包、APT 软件源、包签名、自动安装到当前系统。

## 2. 包元数据

| 字段 | 值 |
| --- | --- |
| 源码包名 | `weiqi` |
| 二进制包名 | `weiqi` |
| 版本 | `1.0.0`（Debian native） |
| 架构 | `all` |
| 分类 | `games` |
| 优先级 | `optional` |
| 维护者 | `xiyucheng <xiyucheng@uniontech.com>` |
| 许可证 | GPL-3+ |
| 源码格式 | `3.0 (native)` |
| 标准版本 | `4.5.1` |

运行时依赖：`python3 (>= 3.7)`、`python3-pyqt5 (>= 5.11)`。
构建依赖：`debhelper-compat (= 13)`、`python3`、`python3-pyqt5`。

许可证选 GPL-3+，与 PyQt5 的 GPL 授权兼容；项目根目录增加 GPL-3 全文 `LICENSE`，并在 `debian/copyright` 中声明。

## 3. 安装布局

```
/usr/games/weiqi
/usr/lib/weiqi/main.py
/usr/lib/weiqi/weiqi/...
/usr/share/applications/weiqi.desktop
/usr/share/icons/hicolor/scalable/apps/weiqi.svg
/usr/share/man/man1/weiqi.1.gz
/usr/share/doc/weiqi/README.md
/usr/share/doc/weiqi/changelog.gz
/usr/share/doc/weiqi/copyright
```

- `/usr/games/weiqi` 为启动脚本，根据自身路径解析前缀并执行 `/usr/bin/python3 <prefix>/lib/weiqi/main.py "$@"`。
- 选择 `/usr/games` 是为了符合 Debian games 分类，避免 `lintian` 的 `package-section-games-but-contains-no-game` 错误；UOS/Debian 默认 PATH 包含 `/usr/games`，终端直接输入 `weiqi` 即可启动。
- `/usr/lib/weiqi` 存放 `main.py` 与 `weiqi` 包，不安装测试和文档源码。
- 安装时不生成 Python 字节码（构建时清理 `__pycache__` 与 `.pyc`）。

## 4. 新增与修改文件

```
debian/
  changelog
  control
  copyright
  rules
  source/format
  weiqi-launcher
  weiqi.desktop
  weiqi.svg
  weiqi.1
  weiqi.docs
  weiqi.manpages
build_deb.sh
LICENSE
README.md（增加安装包章节）
.gitignore（忽略构建产物）
```

`debian/rules` 使用 `dh $@`，并覆盖：

- `override_dh_auto_build`：不执行额外构建。
- `override_dh_auto_test`：运行 `python3 -m unittest discover -s tests -v`。
- `override_dh_auto_install`：复制运行时代码、启动脚本、桌面文件、图标和文档；清理字节码。

`debian/weiqi.desktop`：

```
[Desktop Entry]
Type=Application
Version=1.0
Name=围棋
Name[en]=Weiqi
GenericName=围棋游戏
GenericName[en]=Go Game
Comment=人机对战、局域网对战与聊天
Comment[en]=Play Go against AI or over LAN with chat
Exec=/usr/games/weiqi
Icon=weiqi
Terminal=false
Categories=Game;BoardGame;
Keywords=围棋;Go;Weiqi;
StartupNotify=true
```

图标为自绘 SVG：木纹圆角棋盘、网格、黑白棋子，安装在 `hicolor/scalable/apps`。

man 手册 `weiqi.1` 记录命令用法、`--no-discovery` 选项、联机端口和配置文件位置（本程序无配置文件）。

## 5. 构建流程

`build_deb.sh`：

1. 进入脚本所在目录。
2. 清理并重新创建 `dist/`。
3. 执行 `dpkg-buildpackage -us -uc -b`。
4. 将生成的 `.deb`、`.buildinfo`、`.changes` 移动到 `dist/`。
5. 执行 `fakeroot debian/rules clean` 清理构建树。
6. 输出安装包路径。

构建命令：`./build_deb.sh`。
产物：`dist/weiqi_1.0.0_all.deb`。

## 6. 安装、升级与卸载

```bash
# 安装（自动处理依赖）
sudo apt install ./dist/weiqi_1.0.0_all.deb

# 或手动安装
sudo dpkg -i dist/weiqi_1.0.0_all.deb
sudo apt -f install

# 启动
weiqi
# 或从开始菜单点击“围棋”

# 卸载
sudo apt remove weiqi
```

升级时更新 `debian/changelog` 版本号，重新构建安装即可。

## 7. 质量验证

1. `python3 -m unittest discover -s tests`：30 个测试全部通过。
2. `./build_deb.sh`：成功生成 `.deb`，退出码 0。
3. `lintian dist/weiqi_1.0.0_all.deb`：无 error；warning 逐条评估。
4. `dpkg-deb -I`：检查包名、版本、架构、依赖。
5. `dpkg-deb -c`：核对安装路径完整。
6. `dpkg-deb -x` 解包到临时目录，执行：
   `QT_QPA_PLATFORM=offscreen timeout 3 python3 <tmp>/usr/lib/weiqi/main.py --no-discovery`
   确认进程正常运行到超时，无 Python 异常。
7. `desktop-file-validate debian/weiqi.desktop`：无输出。
8. `rsvg-convert` 渲染图标，确认 SVG 可解析、图形正常。
9. 不执行系统级安装，避免改动当前环境。

## 8. 边界与异常

- 目标机器缺少 `python3-pyqt5` 时，apt 安装会自动拉取；若离线安装，提示用户先安装依赖。
- 端口 `45679`/`45678` 被占用时，程序仍按既有逻辑提示；打包不修改网络行为。
- 安装路径固定为 `/usr/lib/weiqi`，不与 Python site-packages 冲突。
- 不安装到用户目录，不使用用户级服务。

## 9. 验收标准

- 生成 `dist/weiqi_1.0.0_all.deb`，`lintian` 无 error。
- 包内包含启动脚本、代码、桌面入口、图标、man 手册、README、changelog、copyright。
- `Depends` 包含 `python3` 与 `python3-pyqt5`。
- 解包后的程序可正常启动。
- README 提供构建、安装、启动和卸载说明。
