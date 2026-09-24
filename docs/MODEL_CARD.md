---
library_name: pytorch
license: apache-2.0
base_model: Qwen/Qwen3.5-9B
tags:
  - omnijev
  - lora
  - image-text-to-text
---

# OmniJev Qwen3.5-9B v4

一次前向的有限选项决策头。输入是图像、问题和请求时给出的选项。输出是字母分布、领先幅度，以及 `act` 或 `hold`。它不生成答案 token。

这个仓库只包含 LoRA（`lora.pt`）和残差决策头（`head.pt`）。底座是 [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)，Apache-2.0，需要单独下载。LoRA 只包语言层注意力，秩 16，alpha 32。视觉层没有训练。

代码和评测记录在 [shapsider/OmniJev](https://github.com/shapsider/OmniJev)。技术报告是仓库里的 `docs/TECHNICAL_REPORT.md`。

## 训练

从 v3 继续，用 `corrective_loss`：对数分数加 Brier；当前最高项不是正确答案时加大该样本权重，并惩罚错误选项相对正确答案的领先幅度。训练题是 AI2D 去掉留出 160 题之后的题，加上 ScienceQA 官方 train 的 400 道图像题。MMStar、MMMU、RealWorldQA、ScienceQA test 和那 160 道 AI2D 没有进入 v4。

## 评测

923 道留出图像选择题，三个官方决策接口，接口错误为 0。逐题记录在 GitHub 的 `results/qwen35-suite/vs-full/`。

| 基准 | 题数 | v4 | NeoHorse-Jev-4B | tinnel OmniJev-4B |
|---|---:|---:|---:|---:|
| MMStar | 240 | 70.0% | 63.3% | 62.5% |
| RealWorldQA | 160 | 73.8% | 71.9% | 70.6% |
| AI2D | 160 | 84.4% | 84.4% | 84.4% |
| MMMU | 203 | 64.5% | 56.7% | 52.7% |
| ScienceQA test | 160 | 96.2% | 93.8% | 80.6% |
| 合计 | 923 | 76.5% | 72.3% | 68.7% |

## 不能拿来做的事

- 不能写成已经超过 NeoHorse 或 tinnel 公布的总榜。文本六项、Image-NLI、LIBERO、Mind2Web 都没有在这个检查点上跑。
- 不能把差距归因于决策头。未训练的 Qwen3.5-9B 还没有在这 923 题上对照。对方是 4B。
- 不能写成已经达到同一主干写完思考之后的准确率。写完的思考仍然更高，而且那张表测的是 v3。
- 0.8 的 `act` 门槛测的是 v3。错题领先幅度中位数是 0.90，门槛挡不住大部分错题。76.5% 是 argmax，不是条件准确率。
- 桌面闭环是 v3 的 8/12，v4 没有再跑。

## 加载

把底座放在 `models/Qwen3.5-9B`，把本仓库的 `lora.pt`、`head.pt`、`config.json` 放在 `models/runs/qwen35-rlcd-v4`。

```python
from omnijev.paths import CHECKPOINT, MODEL
from scripts.experiment_effective import load_native

model, _, _ = load_native(str(MODEL), CHECKPOINT)
decision = model.decide(image, question, options, state)
```
