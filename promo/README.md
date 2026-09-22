# OmniJev 宣传素材包

本目录是可直接发布的文案与海报。所有内容由仓库内的真实实验记录生成，出处见每项说明。

视频与轨迹动图不重复存放在这里，统一放在 [`../docs/media/`](../docs/media/)（README 直接引用同一份文件）。

## 文件清单

**本目录**

| 文件 | 用途 | 尺寸 / 大小 |
| --- | --- | --- |
| `wechat-article.md` | **公众号推文草稿**（含配图位、摘要、标题备选、朋友圈短版） | — |
| `tweets.md` | 中英文推文文案 + 数字与边界清单 | — |
| `omnijev-vs-jev-zh.png` | **中文对比海报**，微博 / 小红书 / 微信 | 1600×1067，630 KB |
| `omnijev-vs-jev.png` | 英文对比海报，X / LinkedIn | 1600×1313，616 KB |
| `omnijev-camera-input.png` | 双相机真实输入证据（模型实际收到的 PNG） | 1020×1348，791 KB |
| `omnijev-transfer-poster.png` | 视频封面帧 | 1280×720，186 KB |
| `cams/` | 22 张相机原图（11 次采集 × 2 视角） | 640×480 each |

**`../docs/media/`（README 使用的同一份）**

| 文件 | 用途 | 尺寸 / 大小 |
| --- | --- | --- |
| `omnijev-intro-60s.mp4` | **60 秒介绍视频**，公众号 / 视频号 / B 站开场 | 1920×1080，30 fps，60 s，6.9 MB |
| `omnijev-intro-60s-preview.webp` | 同一视频的动图版，README 内联播放用（GitHub 会过滤掉 `<video>` 标签） | 800×450，8 fps，4.4 MB |
| `omnijev-decision-probes.png` | 十二族决策探测画廊（含弃权与音频边界） | 1500×1740，695 KB |
| `omnijev-benchmarks.png` | 四公开基准 × 四策略对比面板 | 1600×1240，351 KB |
| `omnijev-transfer.gif` | 主视觉动图，README 首图 | 1000×563，11.4 s，3.2 MB |
| `omnijev-transfer.mp4` | 高清版，可暂停逐帧看决策 | 1280×720，25 fps，506 KB |
| `omnijev-stack.gif` / `omnijev-barrier.gif` | 另外两个具身任务轨迹 | 800×450，2.3 / 2.4 MB |
| `omnijev-stack.mp4` / `omnijev-barrier.mp4` | 上述任务的高清版 | 1280×720，487 / 520 KB |

## 推荐发布组合

**公众号（本文）**：正文用 `wechat-article.md`，按文中七个「配图」标注依次插图；封面用 `omnijev-vs-jev-zh.png`，摘要用文末 54 字版。视频单独发一条视频号，用 `../docs/media/omnijev-intro-60s.mp4`。

**X / 微博（图文）**：`omnijev-transfer.gif` 作首图 + `omnijev-vs-jev-zh.png` 作第二张，正文用「中文·主推文」。

**小红书**：`omnijev-vs-jev-zh.png` 作封面（信息密度高、缩略图可读），第二张放 `omnijev-camera-input.png`（真实像素最有说服力）。

**GitHub / 开发者渠道**：直接转发仓库 README，顶部 60 秒视频 + 轨迹动图 + 基准面板已经齐了；配图文案用 `tweets.md` 的「English · main post」。

**只有一张图的位置**：用 `omnijev-vs-jev-zh.png`。它把「模态差异 + 实测数字 + 能力边界」压缩在一屏里。

## 素材是怎么做出来的

视频与 GIF 不是录屏，而是**离线重渲染**：从已保存的 episode 里读取 `qpos` 序列，用仓库自带的 `RobotWorld` 重算 MuJoCo 前向运动学，再用与浏览器同一套 Three.js 场景参数（背景、光照、材质、home 相机）逐帧绘制后编码。所以不需要推理后端、不需要重跑策略，画面与工作台里看到的一致。

三段式管线（已随仓库提交，命令见 [`../embodied/tools/trajectory-media/README.md`](../embodied/tools/trajectory-media/README.md)）：

1. `scripts/export_trajectory_frames.py` —— 校验 `scene_hash`，导出 `scene.json` / `frames.json` / `meta.json`
2. `embodied/tools/trajectory-media/` —— vite 页面 + `shoot.mjs`，用无头 Chrome 逐帧截图
3. `ffmpeg` —— 合成 MP4 / GIF / WebP，GIF 走两遍调色板量化控制在 3 MB

60 秒视频用同一批轨迹片段与探针图排版成时间轴场景（`seek(t)` 驱动、逐帧截图后编码），无音轨，发布时自行配 BGM。

宣传海报（对比图、相机图）是 HTML/CSS 排版后用 Playwright 以 2 倍像素比截图。

## 一句话总结这次传播的主线

> 接口没变，模态变了。Jev 的状态是文本，OmniJev 的状态里加入了机器人真正看到的东西——而具身决策的信号本来就是视觉的。
