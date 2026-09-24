# OmniJev 技术报告

日期：2026-09-24。这是一份技术报告，记录当前决策头在固定留出题上的同题对照。它不是顶会论文，也不把对方公布的总榜写成已经被超越。

数字来自仓库里的结果文件。合计准确率与分项来自 `results/qwen35-suite/vs-full/summary.json`。错开对子由 `ours.jsonl`、`neohorse.jsonl`、`tinnel.jsonl` 按 `(benchmark, category, index)` 对齐后清点。思考对照来自 `results/qwen35-suite/REPORT.md`，那一份用的是 v3。停手门槛来自 `results/qwen35-suite/delivery.json`，同样是 v3。级联来自 `results/qwen35-suite/cascade.json`，一次前向一侧是 v4。桌面闭环来自 `results/qwen35-suite/EMBODIED.md`，用的是 v3。

## 可以写进标题的结果

当前模型是 Qwen3.5-9B 加 v4 纠错决策头。请求时传入选项，一次前向读候选字母上的分布，不生成答案 token。对照是 NeoHorse-Jev-4B 和 tinnel OmniJev-4B 的官方决策接口。923 题全部返回，三边接口错误都是 0。

| 基准 | 题数 | v4 | NeoHorse-Jev-4B | tinnel OmniJev-4B |
|---|---:|---:|---:|---:|
| MMStar | 240 | 70.0% | 63.3% | 62.5% |
| RealWorldQA | 160 | 73.8% | 71.9% | 70.6% |
| AI2D | 160 | 84.4% | 84.4% | 84.4% |
| MMMU | 203 | 64.5% | 56.7% | 52.7% |
| ScienceQA test | 160 | 96.2% | 93.8% | 80.6% |
| 合计 | 923 | 76.5% | 72.3% | 68.7% |

精确合计是 706/923 = 0.7649，NeoHorse 667/923 = 0.7226，tinnel 634/923 = 0.6869。

同一题上只有一方正确的题数：

| 对照 | 只有 v4 正确 | 只有对方正确 | 连续性校正后的 McNemar 近似 p |
|---|---:|---:|---:|
| NeoHorse-Jev-4B | 96 | 57 | 0.002 |
| tinnel OmniJev-4B | 129 | 57 | <0.001 |

分项错开（只有 v4 正确 / 只有对方正确）：

| 基准 | 对 NeoHorse | 对 tinnel |
|---|---|---|
| MMStar | 33 / 17 | 36 / 18 |
| RealWorldQA | 17 / 14 | 15 / 10 |
| AI2D | 9 / 9 | 11 / 11 |
| MMMU | 31 / 15 | 41 / 17 |
| ScienceQA test | 6 / 2 | 26 / 1 |

AI2D 三方准确率相同，错开对子也打平。RealWorldQA 对 NeoHorse 的净差是 3 题，这一项单独看不稳定。MMMU 和 ScienceQA 的优势更清楚。ScienceQA 的训练集里用过 400 道图像题，test 没有进入训练，但模型见过同一任务的训练分布。

## 方法

底座是 [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)。LoRA 只加在语言层注意力上，秩 16，alpha 32，视觉层没有训练。决策分布从预训练字母 logits 出发，残差头从零开始。发布的权重是 `lora.pt` 与 `head.pt`，不包含底座。

v4 的损失是 `omnijev/rlcd.py` 里的 `corrective_loss`：对数分数加 Brier；当前最高项不是正确答案时，这条样本的对数损失权重变为 3，并加上错误领先幅度。正确且已经领先的样本不吃这项惩罚。训练脚本是 `scripts/train_corrective.py`。优化器是 AdamW，决策头学习率 5e-5，LoRA 学习率 1e-5，权重衰减 0，梯度每 4 步累积，裁剪范数 1.0。它从 v3 接着训。

v4 的训练题是：AI2D 去掉评测那 160 题之后的题，再加 ScienceQA 官方 train 的 400 道图像题。划出评测用的种子是 `suite(40, 20260924)`。MMStar、MMMU、RealWorldQA、ScienceQA test，以及 AI2D 那 160 题，没有进入 v4。更早的 v3 用过 MMBench 英文 dev 里没有进入当时抽样的部分，损失是对数分数加 Brier，没有纠错加权。

同一主干上的组相对策略更新已经退回。它把合成桌面闭环从 8/8 打到 6/8，v4 没有再打开这条损失。

调用时，领先幅度默认要达到 0.8 才把决定标成 `act`，否则是 `hold`。下面的 76.5% 是 argmax 准确率，不是只统计 `act` 之后的条件准确率。

## 协议

五个基准在评测前划定，种子 20260924。MMStar 按类各 40 题，共 240。RealWorldQA 160。AI2D 160。MMMU 是八个学科的单图验证题，共 203。ScienceQA 用官方 test 的 160 道图像题。三个系统收到同一组选项。v4 读一次前向的字母分布。NeoHorse 把选项写进 `criteria`。tinnel 的 `system_one` 接收图像路径，底座是 Qwen3.5-4B。MMMU 的题号在每个学科里从 0 重新计，对齐键必须带上学科。

重跑：

```bash
export CUDA_VISIBLE_DEVICES=0 MSO_FLA=0
python scripts/compare_full.py
```

脚本会接着已有 jsonl 写，不重算已经完成的题。权重路径在 `omnijev/paths.py`。`models/` 不进 git。

## 没有支持的说法

**同尺寸对照没有做。** 未训练的 Qwen3.5-9B 字母对数概率还没有在这 923 题上跑过。现在的差距同时包含「9B 比 4B 大」和「决策头」两件事，报告不能把它们拆开。

**对方公布的总榜没有复现。** NeoHorse 的文本六项、Image-NLI，以及 tinnel 的 LIBERO 和 Mind2Web，这次都没有跑。76.5% 只描述这 923 道图像选择题。

**写完的深度思考仍然更高，而且那张表是 v3。** `results/qwen35-suite/REPORT.md` 里，v3 一次前向合计 75.7%。把写满 3072 token 仍未收束的 233 题算进思考的错误后，思考合计是 71.6%。只保留已经写出答案的题时，思考更高，差距如下。

| 基准 | 写完的题数 | v3 一次前向 | 深度思考 | 差值 |
|---|---:|---:|---:|---:|
| MMStar | 185 | 73.5% | 80.0% | +6.5 |
| MMMU | 110 | 80.0% | 86.4% | +6.4 |
| AI2D | 124 | 93.5% | 96.0% | +2.5 |
| RealWorldQA | 127 | 77.9% | 81.1% | +3.2 |
| ScienceQA | 144 | 96.5% | 100.0% | +3.5 |

v4 的级联记录在 `cascade.json`。一次前向是 76.5%。把储存的思考答案在领先幅度低于 0.5 时换上去，准确率是 76.8%，平均延迟 9.5 秒。门槛 0.3、0.7、0.9 的准确率是 76.1%、76.6%、76.8%。这没有补上写完思考之后的差距。

**0.8 的停手门槛挡不住大部分错题，而且测的是 v3。** `delivery.json` 的无门槛准确率是 75.7%（v3）。领先幅度至少 0.8 时，保留 82.9% 的调用（765/923），这些调用上的条件准确率是 82.2%。错题领先幅度的中位数是 0.90。条件准确率上升，是因为丢掉了一部分调用，不是因为 argmax 从 75.7% 变成了 82.2%。v4 没有重测这张门槛表。

**桌面闭环是 v3，而且完成度不高。** 合成画面、无空白帧、无虚假说明、种子 60000–60011：12 回合完成 8 回合，每步 0.072 秒。同一主干的逐步思考在两个已成功种子上都没有放下。v4 没有再跑闭环。这不能和公开的 LIBERO 成绩比较。

**纠错训练的合计提升很小。** 同一套 923 题上，v3 是 75.7%，v4 是 76.5%。

## 权重与代码

| 路径 | 含义 |
|---|---|
| `models/Qwen3.5-9B` | 底座。自行从 Qwen/Qwen3.5-9B 取得，本仓库不提交这 19GB |
| `models/runs/qwen35-rlcd-v4` | 当前决策头。Hugging Face：`tzcfly/OmniJev-Qwen3.5-9B-v4` |
| `models/compare/` | 同题对照用的 NeoHorse-Jev-4B、Qwen3.5-4B 和 tinnel adapter，留在本地 |

Qwen3.5 没有安装 `causal_conv1d` 和 `flash-linear-attention`。线性注意力走 PyTorch 核，结果可用，不要为了加速去改现有 torch。

`results/native-rlcd/` 是 Qwen2.5-VL-3B，不能和上面的数字放在一起。`results/qwen35-public/` 是 v2 对直接短答。`results/qwen35-thinking/` 是后来被 923 题覆盖的思考子集。

## 下一件要做的测量

在同一套 923 题上，比较未训练 Qwen3.5-9B 的字母对数概率和 v4。做完之前，文本六项、LIBERO 和 Mind2Web 都还不能用来写「已经超过对方公布成绩」。
