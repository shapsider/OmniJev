# OmniJev Vision Preview

OmniJev 是一个面向机器人决策的多模态实验项目。

Jev 的核心思路是：给模型一段非结构化状态和一组预先定义的候选问题，再得到可以直接交给程序处理的结构化决策。这个方向非常适合路由、分类、评分和有限动作选择，但机器人通常还需要理解相机画面、腕部视角和连续变化的场景。

因此，我们基于 Nemotron 3 Nano Omni Q4_K_M 做了第一版多模态尝试，把文字状态、RGB 图像和有序多图接入有限候选决策接口，并将它连接到本地 MuJoCo 机械臂实验台。当前版本是研究预览：它使用兼容的本地生成 API 来实现 OmniJev 的决策流程，不声称复制 TypeSafe Jev 的内部架构、并行采样或 RLCD 训练。

我们的原生 RLCD 训练 Vision-Jev 正在开发中，coming soon。欢迎关注并保持期待。

## 先看清楚当前版本

- 项目名称：**OmniJev Vision Preview**。
- 当前视觉骨干的权重名称可能仍显示为 `omnijev-nemotron`，这是兼容已有本地运行环境的内部模型 ID，不是项目对外名称。
- 当前决策分数是候选 token 的相对分数，不是经过任务验证的正确率或安全概率。
- 当前版本可以运行文本、RGB 图像和有序多图；音频能力取决于后端配置，默认实验不把音频结果计入多模态结论。
- 具身工作台只在 MuJoCo 仿真中执行动作，不连接真实机器人，也不提供真实机器人安全保证。

## 从零开始运行

### A. 只运行核心 SDK 和本地 HTTP 服务

核心 SDK 不需要 MuJoCo：

```bash
git clone <your-repository-url> OmniJev-release
cd OmniJev-release
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

启动一个 OpenAI-compatible 本地后端后，运行：

```bash
./run_local.sh
```

浏览器打开 `http://127.0.0.1:8765`。如果使用 macOS 的 Bionic，可直接使用脚本启动本机服务；其他系统请先启动自己的兼容后端，再执行 `python3 -m omnijev.server --model <model-id> --base-url <base-url>`。

### B. 运行具身实验台

具身实验台需要 Python 3.12+、MuJoCo 和前端已构建资源：

```bash
./setup_embodied.sh
./run_embodied.sh
```

打开：

- 实验台：`http://127.0.0.1:8766`
- 结果面板：`http://127.0.0.1:8766/benchmarks`

第一次运行建议先选择规则基线，运行搬运入盘、方块堆叠和越障搬运三个任务，确认仿真、浏览器和导出功能都正常。规则基线不调用模型。

### C. 下载并放置模型权重

项目不把模型权重放进 Git，也不会在安装时偷偷下载。请从你使用的本地推理后端的官方模型页面下载 **Nemotron 3 Nano Omni Q4_K_M** GGUF 及其配套投影文件，并让后端完成加载。权重建议放在后端自己的模型目录，例如：

```text
~/Models/nemotron-3-nano-omni/
```

OmniJev 只通过兼容 API 访问已经运行的后端；它不会读取权重文件，也不要求固定的权重目录。启动后端后，用下面的环境变量指向它：

```bash
export OMNIJEV_MODEL=omnijev-nemotron
export OMNIJEV_BASE_URL=http://127.0.0.1:1234
export OMNIJEV_REASONING_TOKENS=4096
./run_embodied.sh
```

如果你的后端使用其他模型 ID，只需修改 `OMNIJEV_MODEL`。模型是否真的支持图片，要以 `/v1/models` 和一次实际图片请求为准。

## 具身实验和结果展示

实验台包含三个任务、规则基线、快速决策、普通短答案、有限推理、Adaptive 策略、单步控制、双相机输入、扰动、暂停、单步执行、轨迹回放、模型对比、JSON 导出和 benchmark 面板。已有结果保存在 `results/`，启动服务后可从 `/benchmarks` 查看；新的实验建议写入新的输出目录，不覆盖已有记录。

预设技能模式用于比较有限候选决策；直接视觉模式才把相机 RGB 送入模型。两者的结果必须分开展示，技能模式不能当成端到端视觉规划成绩。

运行一个小型具身 benchmark：

```bash
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers baseline omnijev omni_direct omni_reasoning \
  --tasks transfer stack barrier \
  --seeds 0 1 2 \
  --max-cycles 20 \
  --output results/embodied/my-run
```

运行直接视觉和扰动实验：

```bash
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers omnijev omni_direct \
  --tasks transfer --seeds 0 \
  --observation vision --control incremental --max-cycles 60 \
  --intervention '{"kind":"target_shift","after_cycle":10,"delta_xy":[0.04,0]}' \
  --output results/embodied/my-vision-shift
```

## 实验记录和复现

每个 benchmark 输出目录会保存：

- `manifest.json`：协议、项目 revision、Python/平台信息、模型端点和适配器哈希。
- `*.config.json`：每个回合的完整配置。
- `episodes.jsonl`：所有回合的汇总行，包含失败回合。
- `*.json`：动作、观测、轨迹、终态、相机元数据和模型调用记录。
- `*.requests.jsonl`：每次请求的配置、输入哈希、延迟、token 用量和错误。
- `*.cameras.zip`：视觉实验的 PNG 帧和帧哈希。
- `summary.json`：按 provider 汇总的成功数、调用数、延迟、token、物理接触和失败类型。

协议固定后才能续跑；不同配置必须使用新的输出目录。模型错误不会切换到规则策略，失败会保留在分母中。仿真在等待模型时暂停，因此当前 benchmark 不测量真实机器人在推理等待期间继续运动的风险。

更多协议说明见 [具身复现协议](docs/REPRODUCIBILITY.md) 和 [公开评测协议](docs/PUBLIC_EVALUATION_PROTOCOL.md)。

## Python SDK 示例

```python
from omnijev import OmniJev, Policy

client = OmniJev(model="omnijev-nemotron")
result = client.decide(
    question="画面中的工件应放入哪个分区？",
    images=["data/assets/red.png"],
    state="当前只开放红色和蓝色分区。",
    options=[
        {"id": "red_bin", "description": "放入红色分区"},
        {"id": "blue_bin", "description": "放入蓝色分区"},
        {"id": "unknown", "description": "证据不足", "abstain": True},
    ],
    policy=Policy(max_latency_ms=3000),
)
print(result["status"], result["action"])
```

## 测试和开发

```bash
python3 -m unittest discover -s tests -v
.venv-embodied/bin/python -m pytest embodied/tests -q
```

修改前端后，在 `embodied/` 中运行 `npm ci && npm run build`，再重新启动具身服务。

项目的历史实验结果、数据说明、模型卡和第三方许可仍保存在 `results/`、`data/` 和 `THIRD_PARTY_NOTICES.md`，便于审计和复现。
