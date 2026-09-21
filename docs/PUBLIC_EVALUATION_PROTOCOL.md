# 本机公开评测协议

日期：2026-09-20。模型保持冻结，不训练，不改权重。当前运行仅使用本机 Nemotron 3 Nano Omni Q4_K_M。

## 固定子集

| 数据 | 样本 | 抽样与限制 |
|---|---:|---|
| MMStar | 300 | 六类各 50 题，300 张独立图像 |
| MMBench DEV EN | 60 | 20 类各 3 个原始问题，只测一种选项顺序，不是 circular score |
| MMAD DS-MVTec | 45 | 九种标注类型各 5 题，独立图像，零参考图、零领域知识 |
| StreamingBench 实时视觉部分 | 20 | 十类各 2 题，独立视频；仅选择压缩大小不超过 100 MB 的视频 |

共 425 个问题，四种方法共 1,700 次正式请求。均在推理前按 seed=20260920 固定；抽样清单与输入文件哈希保存在各结果目录的 manifest.json。小子集用于先导评估，不能用于官方榜单或广泛等效声明。

视频使用跨度最多 60 秒的八张有序帧，采样窗在问题时间前 0.1 秒结束（最早目标帧可在问题前 60.1 秒），最长边不超过 512 像素。FFmpeg 实际帧时间戳逐一核对不晚于问题时间；不会提供未来帧。每个视频只选一个问题，避免相关问题被误作独立样本。这里评测的是预抽帧后的因果问答，不是持续视频输入、动作执行或音视频联合理解。最终审计精确化了此前“前 60 秒”的文字描述，未改变抽帧、问题或模型输入。

## 四组方法

1. OmniJev：现有 core.decide 的短标签模式，关闭思考，max_tokens=4，返回 top-10 logprobs。
2. Direct：与 OmniJev 完全相同的消息、温度、seed 与 4-token 预算，不请求 logprobs。
3. JSON：现有 core.decide 的受 JSON schema 约束输出，关闭思考，max_tokens=32。
4. Reasoning：与短标签模式相同消息，开启原生思考，temperature=0.6、top_p=0.95、max_tokens=20480。最终仍要求一个选项字母。采样与输出上限采用 NVIDIA 模型卡建议；Bionic 的 vLLM reasoning_budget/grace_period 支持未验证，因此不声称完全复现 NVIDIA 的服务配置。

非推理组温度为 0；推理组采用推荐温度 0.6。生成 seed=20260919。模型加载状态另存 backend.json；模型加载不计入每题推理耗时。每个数据集内的 case × method 请求全局随机排序，串行执行。

2,048-token 初始校准出现截断，后尝试温度 0、8,192-token 的贪心对照。核对 NVIDIA 模型卡后，主推理对照修正为温度 0.6、top_p=0.95、20,480-token 上限。旧记录完整保留在 calibration 和 greedy8192-ablation 目录；参数未变的 152 条短答案记录继续使用，推理记录重新生成。此过程属于先导协议开发，不是预注册验证性试验。仍截断的请求计入失败，不能代表无限预算表现。

## 指标

- 主正确率允许从最终输出末行明确解析选项；严格返回格式的正确率另外统计。无法明确解析、超时和未输出最终答案均计入失败，不从隐藏思考中取答案。原始记录保留严格判分，报告另行归一化。
- 端到端客户端响应时间 P50/P95/均值，包含图片编码、HTTP 和解析；不含模型加载及预先完成的视频下载、解码、抽帧。
- 后端报告的输入、生成和总 token。生成 token 已包含思考，不重复累加。
- 在 0.5/1/2/5/10/30 秒内正确完成的请求比例；这只是已准备好输入之后的响应期限分析。
- 同题配对准确率差、胜/负题数、答案一致率。非劣界限为 2 个百分点。
- 图像聚类 bootstrap 95% 区间，以及对独立输入的 win/loss 概率使用 Bonferroni + Clopper-Pearson 的保守区间；先导推断不构成正式等效结论。

## 混杂因素与结论边界

- 服务自然缓存开启，没有强制清空 KV 或图像缓存。随机顺序可缓解顺序偏置，但不能将结果称作冷启动性能。首批请求还可能复用技术校准缓存。
- 数据准备与首段 MMStar 推理有时间重叠，可能增加该段延迟噪声；下载、解码结束后其余推理继续串行。未控制系统其他应用负载或热状态。
- 当前 OmniJev 与 Direct 的主要差异是是否请求候选 token 分数。若结果相近，应解释为通用骨干的短答案能力，不能据此宣称新模型范式。
- 公开数据可能存在训练集污染；这里测试同一骨干上的推理方式，不宣称排除污染。
- MMBench 与 MMStar 存在来源重叠，不能将两个数据集的分数视为完全独立证据。
- 推理组单种子、单次采样；没有重复采样来估计解码随机性。
- 本轮不验证原生音频、闭环任务成功率、跨模型泛化或生产可靠性。

## 文件与复现

本机安装绘图和视频解码依赖：`python3 -m venv .venv-eval`，然后 `.venv-eval/bin/pip install matplotlib==3.9.4 imageio-ffmpeg==0.6.0`。

下载并校验公开数据表：`python3 scripts/download_public_data.py`。

数据准备：`scripts/public_benchmark.py --prepare-only` 和 `scripts/prepare_extra_benchmarks.py`。

运行：`python3 scripts/public_benchmark.py --out results/<dataset>-public`。务必事先生成相应 manifest。

汇总：`python3 scripts/report_public_benchmark.py --out results/<dataset>-public`。

图表：`.venv-eval/bin/python scripts/plot_public_benchmark.py --out results/<dataset>-public`；未完成全部请求时拒绝生成比较图。

四个 manifest 均准备好后，可以用 `python3 scripts/complete_public_suite.py` 串行执行并汇总全部子集。

逐题记录保存在 records.jsonl，包含最终答案、正确性、耗时、后端用量、完整响应、请求配置、提示词哈希和时间。脚本与核心逻辑的快照及哈希保留在结果目录。

推荐采样来源：https://huggingface.co/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16

后端预算核对：主对照 reasoning_effort=medium。实际响应显示部分请求在约 8,192 个思考 token 后插入 `I have to answer now.` 并返回最终选项，即使 finish_reason=stop 也已触发预算。报告单独统计此事件；20,480 是请求总输出上限，不是已验证的内部思考预算。本轮不代表无限预算或完整的 NVIDIA vLLM 推荐配置。

评分修正：观察到推理输出先解释、最后明确给出选项的情况后，主答案准确率增加通用的末行选项归一化，同时保留严格格式正确率及原始记录。归一化不使用 gold，不更改模型输出，不从内部思考内容搜索答案。
