# 兼容性与适配记录

## 实际交付目标

本包只声明适配 **legacy-v1-8x9**：透明 PNG / WebP 图集 1536×1872，8 列 9 行，每格 192×208。实际安装使用 WebP。`pet.json` 只放四个字段：`id`、`displayName`、`description`、`spritesheetPath`，不把本工程预览用的 fps、映射或自定义动画名添加为客户端字段。

核验来源：

- [OpenAI Codex pet contract](https://github.com/openai/skills/blob/main/skills/.curated/hatch-pet/references/codex-pet-contract.md)，Git blob `6dc57cc14bbcb9a5c8455e0a3161e0eb76fded3d`。
- [OpenAI animation rows](https://github.com/openai/skills/blob/main/skills/.curated/hatch-pet/references/animation-rows.md)，Git blob `79b63b20d71205fae13f89b60dc2f6d71b00a172`。
- [Codex settings](https://developers.openai.com/codex/app/settings/)，用于核对 Pets 设置页与 `/pet` 控制入口。

核验日期：2026-10-18。Git blob 固定的是核验文档内容，不等于已对该日每个客户端发行版完成运行验证。**不能把旧版文档仍在仓库中理解成所有新版客户端都承诺向后兼容。**

## 每行读多少格

| 行（从 0 开始） | 状态 | 有效格 | 每格时长，毫秒 |
|---:|---|---:|---|
| 0 | idle | 6 | 280, 110, 110, 140, 140, 320 |
| 1 | running-right | 8 | 120 × 7，最后 220 |
| 2 | running-left | 8 | 120 × 7，最后 220 |
| 3 | waving | 4 | 140 × 3，最后 280 |
| 4 | jumping | 5 | 140 × 4，最后 280 |
| 5 | failed | 8 | 140 × 7，最后 240 |
| 6 | waiting | 6 | 150 × 5，最后 260 |
| 7 | running | 6 | 120 × 5，最后 220 |
| 8 | review | 6 | 150 × 5，最后 280 |

有效格后必须透明。本工程没有把原始 24 帧图集缩小后直接用作客户端图集，而是逐格重排。具体源帧编号和镜像标记在 `config.json` 和 `docs/animation-map.json`。

## 保真与已知局限

原始 27 组 ×24 帧都保存在无损源图集中。完全透明像素的 RGB 做了归零清理，但可见颜色与 Alpha 不变。源 PNG 的压缩字节不保证与导出文件相同；逐帧归一化 RGBA 哈希是可复核的保真标准。

原生版每套采用一个统一缩放比例和固定地面锚点，保留源帧已存在的跳跃高度。原始图像生成导致的局部配饰纹样、脸部和轮廓轻微变化不会因重排图集而自动消失。

左移由右移镜像得到：帽饰、包带、鲸鱼图案也会镜像。`running` 和 `review` 分别复用不同待机片段，没有新增真正敲键盘、读代码的画面。`failed` 对应惊讶捂脸，并非悲伤哭泣；`waiting` 对应坐着晃脚，并非专门绘制的审批手势。这些是已有素材到状态语义的适配取舍。

源动画中的小跑、困倦、摇摆保留在完整预览与导出中，不宣称原生客户端具有任意自定义状态或24帧拓展接口。本包也不包含额外方向视线图，不自称 V2 图集。

## 验证范围

已执行：Python 单元测试；三套四字段清单、WebP 内容、尺寸、透明空格、边界和源帧哈希校验；在临时隔离目录中的安装、重复安装、备份、回滚和卸载；JavaScript / Bash 语法检查；预览逻辑的模拟环境测试；从实际输出图集中提取图像进行视觉检查。

未执行：真实 Codex Desktop 的资源发现、原生动作事件触发、动画播放或尺寸效果；真实 macOS / Windows 安装运行；真实浏览器页面渲染。离线页面与测试工具不会连接 Codex 会话。`qa/asset-validation.json` 的 `codex_desktop_runtime_tested` 为 `false`，不能删除这个限制来表示产品验收。

## 本机最小验收

1. 安装后重启 Codex，检查设置中出现三套装扮并能切换。
2. 用 `/pet` 显示桌宠，确认透明区域没有实底，帽子和尾巴未截断。
3. 检查待机与移动是否连续，运行任务后观察客户端触发的状态。
4. 出现空白、错行或布局不对时，先记录客户端版本、系统、`CODEX_HOME` 与实际文件路径；不要盲目覆盖应用资源。

以上是本机待验收项，不是本次聊天中已经完成的测试。
