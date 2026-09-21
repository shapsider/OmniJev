# OmniJev Vision Preview：具身工作台与 benchmark

## 项目范围

本目录提供可以从零安装、运行、记录和复现的 MuJoCo 机械臂实验台。它把有限候选决策、RGB 观测、模拟本体状态、物理执行和终态验证放在同一个本地工作流中。实验结果面板读取本地 `results/`，不会把没有实际运行的模型结果显示成成功。

| 模块 | 当前实现 |
|---|---|
| `physics.py`、Panda 资产 | MuJoCo 物理、IK、接触、抓持、支撑与终态判断；资产许可见 `embodied/src/embodied_jev/assets/panda/LICENSE` |
| `planning.py`、`incremental.py` | 技能菜单与固定 21 个 XYZ / 夹爪动作；技能和增量控制独立记录 |
| `perception.py` | 外部 / 腕部 RGB、RGB-D 估计、时间戳与观测归档 |
| `runtime.py`、`comparison.py` | 暂停、停止、动作预演、回放、独立同种子仿真、模型对比和导出 |
| 浏览器工作台 | 轨迹渲染、视觉输入检查、扰动、比较、导出和 benchmark 导航 |
| `omnijev/embodied_policy.py` | 四种本地策略、提示构造、候选分数解析、稳定动作 ID 映射；模型错误不自动代答 |
| `scripts/benchmark_embodied.py` | 独立进程、固定随机顺序、失败留存、协议校验续跑、token / 物理指标和运行环境记录 |
| `omnijev/embodied_web.py` 与 `web/benchmarks.html` | 本地模型状态与结果面板，分开展示公开问答和具身回合 |

项目许可证和第三方依赖说明见 `embodied/LICENSE` 与 `embodied/THIRD_PARTY_NOTICES.md`。本项目使用本地兼容 API 调用视觉骨干，不实现 TypeSafe Jev 的内部架构、原生决策协议或 RLCD 训练。

## 从零安装、启动与浏览器用法

```sh
# 仅首次；Python 3.12+。不会下载模型权重。
./setup_embodied.sh
# 本机已有环境时直接运行
./run_embodied.sh
```

访问 `http://127.0.0.1:8766`，结果面板为 `/benchmarks`。服务仅监听回环地址，默认内存模式。前端构建资源已包含，运行不需要 Node；改前端时才需要重新构建。模型权重必须由用户从所用推理后端的官方页面下载并放入后端模型目录，OmniJev 只访问后端 API。

1. 保持“规则基线”，选搬运入盘 / 堆叠 / 越障，再点运行，检查安装和物理环境。规则调用数为零。
2. Bionic 加载现有 Nemotron 后选择“OmniJev · 快速决策”，可单步、暂停、停止、重置、回放与导出。这才是真实本机模型决策。
3. “预设技能选择 + 仿真真值”用于技能决策验收，程序执行技能内部轨迹，模型看不到相机图像。
4. 视觉实验选择“逐步 XYZ + 直接图像 + 外部或双相机”。模型获得 RGB 与本体反馈，不获得对象 / 目标真值坐标；安全预演与终态评估仍使用仿真真值。用“视觉”页查看实际输入，下载相机归档核对。
5. 在“模型对比”选择 2–3 路策略，默认串行避免本地资源竞争。每路独立世界；回放按仿真时间对齐，不代表真实推理耗时。
6. 在执行设置启用目标 / 物体位移扰动，观察后续调整。扰动不是模型动作，是否恢复必须由实际轨迹判断。

模型参数通过启动环境设置：

```sh
OMNIJEV_MODEL=omnijev-nemotron \
OMNIJEV_BASE_URL=http://127.0.0.1:1234 \
OMNIJEV_REASONING_TOKENS=4096 \
./run_embodied.sh
```

`OMNIJEV_REQUEST_TIMEOUT` 默认 180 秒；`OMNIJEV_PORT` 默认 8766。模型离线时界面明确显示未就绪，规则演示仍可用；模型请求错误会终止回合，不会自动切换规则策略。

## 四种本地策略

| 策略 | 实际调用 | 注意事项 |
|---|---|---|
| OmniJev | 单字母生成，4-token 上限，关闭思考，top-10 logprobs | 沿用现有生成 API，非零解码新架构 |
| Direct | 同样输入、采样与 4-token 上限，不索取 logprobs | 必须保留的强基线 |
| Reasoning | medium，T=0.6 / top_p=0.95，默认总输出上限 4096 | 与之前公开问答的 20480 上限不同，分别报告 |
| Adaptive | 先快速请求；分数缺失或 margin < 0.2 时再真实请求推理 | 启发式实验功能，未校准或证明优于基线；两次成本都记账 |

21 个动作通常超过 top-10 的覆盖范围，因此分数可能不可用；不能凭空补齐概率。Adaptive 在缺失分数时升级推理，可能比固定推理更贵。输出无效、截断或快速路径意外产生思考时均记错误，保留已知 token 成本，不代选动作。

浏览器切换到本地策略时，额外候选分数门槛默认为零，因为 token softmax 不是校准后的任务成功率；仿真动作预演保持开启。用户仍可选择非零门槛进行拒答实验。benchmark 固定门槛为零，避免仅对有分数的策略额外施加筛选。

## 可复现 benchmark

公开问答：既有 425 题 × 4 方法的记录、统计与图表继续保留。见 [公开协议](PUBLIC_EVALUATION_PROTOCOL.md)，不是具身成功率。

具身技能先导：

```sh
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers baseline omnijev omni_direct omni_reasoning \
  --tasks transfer stack barrier --seeds 0 1 2 \
  --max-cycles 20 --reasoning-tokens 4096 \
  --output results/embodied/my-skills-run
```

直接视觉与扰动实验应另开目录：

```sh
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers omnijev omni_direct --tasks transfer --seeds 0 \
  --observation vision --control incremental --max-cycles 60 \
  --intervention '{"kind":"target_shift","after_cycle":10,"delta_xy":[0.04,0]}' \
  --output results/embodied/my-vision-shift
```

每个回合由独立进程执行，保存原始场景哈希、策略版本、动作 / 观测 / 轨迹、逐请求配置、输入哈希、实际用量、失败与相机归档。`manifest.json` 还记录项目 git revision、Python 版本、平台、模型端点和适配器哈希。固定排序种子 20260921，生成种子 20260919。完整协议写入 manifest；已有输出只能用同样协议续跑，不能覆盖失败。汇总分母包含全部回合。

报告任务成功率、回合墙钟时间、API 调用次数、输入与输出 tokens、禁止接触次数、预算耗尽 / 停滞 / 拒答 / 错误。零模型调用的规则策略不能以推理准确率来解释；技能基线成功也不证明端到端视觉规划。

物理仿真在等待模型时暂停，因而该 benchmark 尚不能测量环境在推理期间继续演化的控制风险。小样本不能证实非劣、泛化或真实机器人的可靠性。上游未公开的 Jev 分层 XYZ 开发模式没有被声称已复现。

## 开发与验证

```sh
.venv-embodied/bin/python -m pytest embodied/tests -q
python3 -m unittest discover -s tests
# 前端源码修改后
cd embodied
pnpm install --frozen-lockfile
pnpm run build
```

本地核心 SDK 仍可不安装 MuJoCo 单独使用；具身工作台依赖放在 `.venv-embodied`。上游测试、OmniJev 适配契约、真实物理回合与浏览器验收分别记录，不把 stub 测试冒充真实模型评测。

## 重新评测公开子集（保留旧成绩）

源码包包含成绩与脚本，不分发第三方原始媒体。先运行 `python3 scripts/download_public_data.py`；图表依赖 `matplotlib`，视频准备依赖 `imageio-ffmpeg`（按需安装）。准备和评测应使用新目录，例如：

```sh
python3 scripts/public_benchmark.py --prepare-only --out results/mmstar-new
python3 scripts/prepare_extra_benchmarks.py mmbench --out results/mmbench-new
python3 scripts/public_benchmark.py --out results/mmbench-new
python3 scripts/report_public_benchmark.py --out results/mmbench-new
python3 scripts/audit_public_results.py --out results/mmbench-new
```

MMAD 和 StreamingBench 分别将准备命令的名称改为 `mmad`、`streaming`。公开问答脚本目前固定调用本地 `omnijev-nemotron`；更换骨干需同时修改协议与调用配置并另存结果。旧 manifest 中的绝对媒体路径是原实验来源记录，新机器需重新准备媒体，不能直接据此推理。
