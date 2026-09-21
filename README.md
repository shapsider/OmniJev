# OmniJev

**把冻结的本地视觉语言模型变成可接入业务的动态决策接口。**

输入图片/文字、问题和随场景变化的候选，输出稳定动作 ID、拒答状态、候选相对分数与耗时。无需训练、无需云端推理；核心 SDK 使用 Python 标准库，具身工作台另有 MuJoCo 等依赖。

当前 v0.3 提供：**浏览器具身工作台 + Benchmark 面板 + Python SDK + HTTP API**。支持文本、图片、有序多图；音频尚未接通，不宣称已实现完整全模态推理。

## 具身实验台与 Benchmark

深度集成 [FBddcz/embodied-jev](https://github.com/FBddcz/embodied-jev) 的 MIT 开源工作台：真实 MuJoCo + Franka Panda 物理、搬运 / 堆叠 / 越障、双相机、逐步 XYZ、扰动、暂停 / 单步 / 回放 / 导出。新增 OmniJev、Direct、Reasoning 和实验性 Adaptive 本地策略。来源与修改边界见 [集成说明](docs/EMBODIED_INTEGRATION.md)。

```sh
# 本机已安装环境，直接启动
./run_embodied.sh
# 新机器首次安装：Python 3.12+
# ./setup_embodied.sh
```

- **具身 demo：http://127.0.0.1:8766**。默认规则演示无需模型；选择 OmniJev 后实际调用 Bionic 中已加载的 Nemotron。
- **评测面板：http://127.0.0.1:8766/benchmarks**。读取真实结果，分开展示公开问答与物理闭环实验，支持下载报告。
- **正式闭环评测：** `.venv-embodied/bin/python scripts/benchmark_embodied.py --seeds 0 --output results/embodied/new-run`

技能选择模式有程序轨迹，不能当作端到端视觉规划。直接图像模式把 RGB 送给模型，成功率另测；没有使用上游模型成绩作为本项目成绩。候选分数缺失时明确显示不可用，模型错误不会切回规则控制。

实测详情见 [具身评测报告](results/EMBODIED_BENCHMARK_REPORT.md)，包含技能对照与独立的直接视觉记录。可运行 `python3 scripts/report_embodied.py` 从原始记录重建报告，`python3 scripts/build_release.py` 生成完整源码包。

## 通用决策交互台（原入口）

已在这台 Mac 的 Bionic / Nemotron GGUF 上验证。已有权重无需重复下载。

```sh
cd /Users/lukatang/Desktop/paper/OmniJev
sh run_local.sh
```

打开 **http://127.0.0.1:8765**。脚本启动 Bionic 的 loopback API；需要时加载已下载的 Nemotron，然后启动交互台。不会训练，也不会自动下载模型。停止交互台用 Ctrl-C；Bionic 模型仍由 Bionic 管理，可在应用中卸载释放内存。

交互台可选择视觉分拣、质检、界面状态、文本路由或自定义场景：

1. 写问题，定义 `动作 ID | 描述`；以 `?` 开头的 ID 表示拒答选项。
2. 上传图片，或由你点击开启相机，也可关闭画面输入只用文字。
3. 单次决策或连续采样；随时修改候选与问题。
4. 查看动作、耗时、候选分数，导出本次结果。

相机需要浏览器授权。连续模式最多一个请求在途，完成后才采集下一帧；配置更新时丢弃旧配置的返回结果。停止连续模式不取消已在后端执行的请求。相机采样代码已实现，尚未使用用户摄像头验收；已验收内置样例连续决策。

## 在你的程序里使用

在仓库根目录直接 import；也可 `python3 -m pip install -e .` 安装为包。

```python
from omnijev import OmniJev, Policy

engine = OmniJev(model="omnijev-nemotron")
result = engine.decide(
    question="画面中的工件应分配到哪个颜色分区？",
    images=["data/assets/red.png"],
    state="允许动作会随生产线状态改变。当前只开放红、蓝两个分区。",
    options=[
        {"id": "red_bin", "description": "红色工件进入红色分区"},
        {"id": "blue_bin", "description": "蓝色工件进入蓝色分区"},
        {"id": "unknown", "description": "颜色不在候选中或证据不足", "abstain": True},
    ],
    policy=Policy(max_latency_ms=3000),
    request_id="frame-42",
)

if result["status"] == "decided":
    print(result["action"])  # 稳定 ID，不是模型输出的 A/B/C
else:
    print(result["status"], result["reason"])
```

`engine.decide_many(requests)` 顺序执行一组独立问题；当前没有实现共享前缀并行引擎。你可以在每一帧更新问题、候选和状态，无需新训练。完整示例：`python3 examples/sdk_demo.py`。

## HTTP 接入

```sh
curl http://127.0.0.1:8765/decide \
  -H 'Content-Type: application/json' \
  --data-binary @examples/request.json
```

- `GET /health`：模型配置、后端可达性、是否忙碌。模型列出不等于推理必然成功。
- `POST /decide`：字段与 SDK 基本相同；`policy` 用 JSON 对象。
- HTTP 图片使用 `data:image/png;base64,...` / JPEG / WebP；最多 8 张，请求体不超过 12 MiB。为避免服务读取任意本地文件，不接受 HTTP 传入文件路径。SDK 可以读取调用者自己的文件。
- `429`：已有推理在执行；实时应用应丢弃旧帧，稍后提交新帧。
- `400`：请求不合法；`502`：后端失败。不会静默返回一个虚构动作。

只监听 `127.0.0.1`，无外部 CDN，不允许跨站浏览器调用；用于本机实验，不是带鉴权的公网生产服务。

## 决策语义

| 字段/状态 | 含义 |
|---|---|
| `status=decided` | 输出属于动作列表，并通过启用的策略检查 |
| `status=abstained` | 选择了明确的拒答选项，或未通过分数检查 |
| `status=invalid` | 未输出合法候选，或检测到意外思考输出 |
| `status=stale` | 实际返回时间超出配置时效预算 |
| `action` | 只有 decided 才包含可供调用者处理的动作 ID |
| `selected` | 模型原始选择，便于审计，包括拒答选项 |
| `scores` | 候选内归一化分数，**不是答对概率** |

`Policy(min_margin=..., min_candidate_mass=...)` 是可选的未校准启发式门槛。分数不全而调用者要求门槛时，返回拒答；不会填零。没有经过验证集校准，不提供风险保证。`max_latency_ms` 是结果过期检查，不是取消计算或硬实时保证。SDK/API 的 elapsed_ms 从 SDK 收到请求算起；浏览器显示耗时另外包含本机 HTTP 往返。

当前支持 2–26 个不同选项，但后端只返回 top-10。候选不全时仍可返回有效选择，`scores=null`。短标签模式通过生成 API 读取首个答案位置的 logprobs，**不是新的模型架构或零解码 forward**。JSON 模式是受限输出对照。

## 已验证范围

- 公开基准先导评测（2026-09-21）：Nemotron 上 425 题 × 4 方法，共 1,700 次正式请求，四组完整性审计通过。见 [总报告](results/PUBLIC_BENCHMARK_REPORT.md) 与 [研究判断](results/PUBLIC_EVALUATION_FINDINGS.md)。当前结果支持相对长链推理的速度和 token 收益，未证明普遍准确率非劣，也未显示超过普通短答案的独立优势。
- v0.1：两个本地模型，26 个文本/视觉条件、两种输出方式、各两轮，208 次有效决策。详见 `results/EXPERIMENT_REPORT.md`。
- v0.2：通过 `scripts/verify_local.py` 检查 SDK 的稳定 ID、明确拒答与跨场景请求，结果保存在 `results/acceptance-v02.jsonl` 及同名 summary。
- v0.1/v0.2 主要是合成诊断，另有手写文本路由案例；这些诊断不代表真实质检、自然图像、复杂 GUI 或开放环境的准确率。公开基准先导结果的适用范围另见总报告。
- 延迟取决于图片尺寸、模型、缓存和后台负载。小图结果不能替代相机帧实测；模型加载时间另计。
- 音频：现有 Nemotron GGUF+投影+运行时报告 `audio=false`。保留 v0.1 音频失败记录，不做转录替代。

## 更换模型与后端

```sh
# 使用已运行的 Qwen/Bionic 或其他兼容服务
python3 -m omnijev.server --model omnijev-qwen --base-url http://127.0.0.1:1234
```

后端必须支持多模态 Chat Completions、`reasoning_effort=none`；分数需要 logprobs，JSON 对照需要 JSON Schema。并非所有“兼容”服务都支持全部字段，当前不会静默降级。Bionic 的 Qwen 启动参考 `scripts/start_bionic.sh qwen`，请先卸载不用的大模型。

非 Mac 用户可以连接自己启动的兼容后端，Python 层与 Web 层不依赖 macOS；此路径未在其他系统实测。

## 测试与研究

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify_local.py --output results/my-acceptance.jsonl
python3 scripts/run_benchmark.py --model omnijev-nemotron --output results/my-run.jsonl
```

单元/HTTP 测试使用 stub 验证契约；`verify_local.py` 和 benchmark 调用真实模型。已有结果不覆盖，重跑请用新文件名。

目录：

```text
omnijev/client.py       稳定动作 ID、拒答与时效策略
omnijev/core.py         模型 API、媒体适配、候选分数
omnijev/server.py       本地 HTTP 服务、忙碌拒绝
omnijev/web/index.html  场景配置、图片/相机、连续决策
examples/              SDK 与 HTTP 接入示例
scripts/               启动、数据生成、真实模型验收与评估
tests/                 输出完整性和服务契约测试
results/               原始实验与报告
docs/                  架构说明、原版说明
```

公开基准评测模块见 [实验协议](docs/PUBLIC_EVALUATION_PROTOCOL.md)：包含 MMStar、MMBench、MMAD 与 StreamingBench 的固定先导子集，比较当前 OmniJev、普通短答案、JSON 和推荐采样配置下的原生推理。原始数据、逐题请求结果、准确率差、延迟及 token 统计分别保存在 `results/*-public/`。

```bash
python3 scripts/download_public_data.py
python3 scripts/public_benchmark.py --prepare-only
python3 scripts/prepare_extra_benchmarks.py mmbench
python3 scripts/prepare_extra_benchmarks.py mmad
.venv-eval/bin/python scripts/prepare_extra_benchmarks.py streaming
python3 scripts/complete_public_suite.py
```

视频解码和绘图依赖的安装方式、子集规模与协议修正均见上述文档。完整运行后生成 `results/PUBLIC_BENCHMARK_REPORT.md`，不可将先导子集的结果当作官方全量成绩。

下一研究步骤是接通音频、实现按需感知/推理并做等风险比较。目前不宣称复制了 TypeSafe Jev 未公开架构或 RLCD。
