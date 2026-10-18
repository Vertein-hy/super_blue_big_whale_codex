# 三套小鲸桌宠：安装说明

这是 Codex 的 **V1 8×9 兼容格式**自定义桌宠资源包，不是独立程序。包含三套装扮：白色针织装、棕白披肩裙装、蓝色鲸鱼冬装。已完成资源与安装器测试，尚未在真实 Codex Desktop 实例内验证；不保证所有新版客户端支持该旧版图集。

## 1. 完整解压

不要直接在压缩软件的预览窗口内运行脚本。保留 `pets/`、`checksums.json`、`tools/` 与安装脚本的相对位置。

## 2. 安装

macOS / Linux，在解压后的目录执行：

```bash
bash install.sh
```

macOS 也可以双击 `install.command`。

Windows PowerShell，在解压后的目录执行：

```powershell
py -3 tools/petctl.py install
```

也提供 `install.ps1`。Python 安装器要求 3.10 或更新版本，但不需要安装第三方依赖。

**没有 Python：**手动复制 `pets/` 里的三个文件夹到你的 Codex 用户目录的 `pets/` 下。默认 macOS / Linux 是 `~/.codex/pets/`，Windows 是 `%USERPROFILE%\.codex\pets\`。设置过 `CODEX_HOME` 时以那个目录为准。同名目录已存在时先自行备份，勿覆盖其他桌宠。

最终每个目录里面直接是 `pet.json` 和 `spritesheet.webp`，不要多套一层同名文件夹。

## 3. 在 Codex 中选择

完整退出后重新打开 Codex，在 **设置 → Pets** 选择以下某一项，再用 `/pet` 或 Show pet 显示：

- 小鲸 · 白色针织装
- 小鲸 · 棕白披肩裙装
- 小鲸 · 蓝色鲸鱼冬装

它们是三个独立的桌宠条目，不会自动换装。菜单名称和发现行为以本机 Codex 版本为准。

## 安装检查与撤销

```bash
python3 tools/petctl.py verify
python3 tools/petctl.py install --dry-run
python3 tools/petctl.py install --outfit winter
python3 tools/petctl.py uninstall --outfit winter
```

Windows 用 `py -3` 代替 `python3`。安装器不动账号、聊天、`config.toml` 或其他桌宠。原文件有变更时会停止；`--force` 表示备份后替换本包对应目录。卸载也会移入 `<CODEX_HOME>/pet-backups/`，可以恢复。

## 帧数和兼容性

每套原生图集为 1536×1872、8×9 格。Codex V1 的九种状态分别读取 4–8 帧，共 57 个有效格，其他格透明。原始 24 帧动作不能直接按 24 帧塞进这个固定合同；完整 648 帧另保存在完整工程包中，可以预览或导出。

向左行走为镜像，不对称配饰也会换边。工作 / 检查状态采用不同待机片段，不是新画的敲键盘动作。任务状态由 Codex 客户端驱动，本安装包不额外监听会话。

若资源校验通过却没有桌宠条目，请先检查实际 `CODEX_HOME`、是否完整重启、目录是否多套一层，以及客户端是否支持 V1 自定义桌宠。不要为此修改登录信息、清空配置或覆盖 Codex 安装文件。

轻量安装包不含源图集和发布工具。预览、全部 24 帧源素材、重建、测试及 GitHub 上传辅助脚本均在完整工程包中。

来源：OpenAI `openai/skills` 仓库的 `hatch-pet/references/codex-pet-contract.md` 与 `animation-rows.md`；核验日期 2026-10-18。本包非官方，真实客户端兼容性仍需本机确认。
