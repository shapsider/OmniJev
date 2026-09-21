# 具身实验复现协议

本文档定义 OmniJev Vision Preview 的具身实验输出格式和复现边界。

## 环境

实验需要 Python 3.12+、MuJoCo 3.13.0 和 `embodied/requirements.lock` 中的依赖。先执行：

```bash
./setup_embodied.sh
```

模型权重不随仓库分发。请从所用本地推理后端的官方模型页面下载 Nemotron 3 Nano Omni Q4_K_M GGUF 及配套投影文件，放入后端模型目录，由后端加载后再设置：

```bash
export OMNIJEV_MODEL=omnijev-nemotron
export OMNIJEV_BASE_URL=http://127.0.0.1:1234
```

规则基线不需要权重，可以先用它验证仿真安装。

## 协议

每个实验固定任务、seed、provider、观测模式、控制模式、最大循环数、超时、扰动、候选打乱方式和推理 token 预算。每一个回合在独立进程中执行，模型错误、超时和缺失结果都会保留在分母中。

`manifest.json` 记录：

- 项目 git revision、Python 版本和平台。
- 模型 ID、API endpoint、策略适配器 SHA-256。
- provider、任务、seed、观测/控制模式、扰动和预算。
- 计时范围、排序 seed 和候选打乱规则。

## 输出文件

- `episodes.jsonl`：每回合一行摘要，包含状态、成功标志、循环数、物理接触、延迟和 token。
- `*.config.json`：该回合完整配置。
- `*.json`：完整动作、观测、物理轨迹、事件、终态和模型请求记录。
- `*.requests.jsonl`：请求 payload 配置、输入哈希、响应元数据、延迟和错误。
- `*.cameras.zip`：视觉回合的 PNG 帧、时间戳和帧 SHA-256。
- `summary.json`：按 provider 分组的汇总。

## 如何重跑

使用新的输出目录运行同一协议：

```bash
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers baseline omnijev omni_direct omni_reasoning \
  --tasks transfer stack barrier --seeds 0 1 2 \
  --max-cycles 20 --output results/embodied/reproduction-run
```

若输出目录已有 `manifest.json`，脚本只接受完全相同的协议。中断后可继续运行；失败记录不会被删除或伪装成成功。

## 结果解释

技能模式里的动作由预设技能执行，适合比较有限候选决策。直接视觉模式才使用 RGB 观测做增量控制。两种模式必须分别报告。成功率、模型调用成功率、物理接触和 token 用量也必须分开报告。

仿真在模型等待期间暂停，因而结果不能外推为真实机器人在网络延迟或推理等待期间的控制安全性。单个 seed 或小样本结果只能作为演示或先导实验，不能作为泛化成功率。
