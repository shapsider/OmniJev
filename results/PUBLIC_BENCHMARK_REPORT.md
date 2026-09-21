# OmniJev 本机公开 Benchmark 评测

完成四个固定先导子集：425 个问题、1,700 次正式请求。模型为本机 Nemotron 3 Nano Omni Q4_K_M，权重冻结。
这些是局部先导实验，不是四个官方 benchmark 的全量成绩。主正确率允许从最终输出明确解析选项；严格格式通过情况单独报告，不从隐藏思考过程挑选答案。
本轮研究判断与课题调整建议见 [评测结论](PUBLIC_EVALUATION_FINDINGS.md)。

## 正确率

| 数据集 | 题数 | OmniJev | 普通短答案 | JSON | 原生推理 |
|---|---:|---:|---:|---:|---:|
| MMStar | 300 | 66.67% | 66.67% | 65.33% | 72.33% |
| MMBench DEV EN pilot | 60 | 90.00% | 90.00% | 90.00% | 90.00% |
| MMAD DS-MVTec zero-shot pilot | 45 | 86.67% | 86.67% | 84.44% | 86.67% |
| StreamingBench causal 8-frame pilot | 20 | 85.00% | 85.00% | 85.00% | 85.00% |

## 响应耗时与 token

| 数据集 | OmniJev P50/P95 秒 | 推理 P50/P95 秒 | OmniJev / 推理平均生成 tokens | 总 token 节省 |
|---|---:|---:|---:|---:|
| MMStar | 1.166 / 1.515 | 15.899 / 120.990 | 3.0 / 2419.4 | 85.79% |
| MMBench DEV EN pilot | 0.611 / 1.186 | 6.109 / 36.923 | 3.0 / 719.5 | 66.16% |
| MMAD DS-MVTec zero-shot pilot | 0.659 / 1.088 | 5.745 / 47.057 | 3.0 / 914.3 | 71.80% |
| StreamingBench causal 8-frame pilot | 2.979 / 3.583 | 20.192 / 124.272 | 3.0 / 2379.1 | 51.26% |

## 准确率保持检验

差值定义为 OmniJev − 原生推理；负数表示 OmniJev 较低。非劣界限预设为最多下降 2 个百分点。答案一致率另外计算，不能代替对标准答案的正确率。

| 数据集 | 差值百分点 | 保守 95% 区间 | 答案一致率 | 结论 |
|---|---:|---:|---:|---|
| MMStar | -5.67 | [-13.87, 2.69] | 75.00% | 未证实准确率非劣 |
| MMBench DEV EN pilot | 0.00 | [-12.58, 12.58] | 93.33% | 未证实准确率非劣 |
| MMAD DS-MVTec zero-shot pilot | 0.00 | [-19.01, 19.01] | 86.67% | 未证实准确率非劣 |
| StreamingBench causal 8-frame pilot | 0.00 | [-27.87, 27.87] | 85.00% | 未证实准确率非劣 |

## 5 秒响应期限内的正确率

分母为全部请求；答错、无法明确解析、超时、或答对但超过 5 秒均不计成功。更完整的时间预算曲线见各数据集 deadline.png。

| 数据集 | OmniJev | 普通短答案 | JSON | 原生推理 |
|---|---:|---:|---:|---:|
| MMStar | 66.67% | 66.67% | 65.33% | 9.00% |
| MMBench DEV EN pilot | 90.00% | 90.00% | 90.00% | 36.67% |
| MMAD DS-MVTec zero-shot pilot | 86.67% | 86.67% | 84.44% | 35.56% |
| StreamingBench causal 8-frame pilot | 85.00% | 85.00% | 85.00% | 5.00% |

## 普通短答案强基线

| 数据集 | OmniJev / Direct P50 秒 | OmniJev / Direct 平均生成 tokens | 答案一致率 | 准确率差百分点 |
|---|---:|---:|---:|---:|
| MMStar | 1.166 / 1.170 | 3.0 / 3.0 | 99.67% | 0.00 |
| MMBench DEV EN pilot | 0.611 / 0.580 | 3.0 / 3.0 | 100.00% | 0.00 |
| MMAD DS-MVTec zero-shot pilot | 0.659 / 0.587 | 3.0 / 3.0 | 100.00% | 0.00 |
| StreamingBench causal 8-frame pilot | 2.979 / 2.986 | 3.0 / 3.0 | 100.00% | 0.00 |

当前实现的短标签路径与普通短答案使用相同模型、提示词和生成预算，主要差异是是否返回 logprobs。相近的结果应归因于通用模型的短答案能力，不能解释为新模型范式的独立优势。

## 严格格式不合规与截断

格式不合规不一定意味着无法解析最终答案；主正确率采用前述语义答案口径。后两列统计推理组。

| 数据集 | OmniJev 格式不合规 | 普通短答案格式不合规 | JSON 格式不合规 | 推理格式不合规 | 输出截断 | 思考预算强制回答 |
|---|---:|---:|---:|---:|---:|---:|
| MMStar | 1 | 1 | 0 | 4 | 1 | 43 |
| MMBench DEV EN pilot | 0 | 0 | 0 | 0 | 0 | 0 |
| MMAD DS-MVTec zero-shot pilot | 0 | 0 | 0 | 0 | 0 | 1 |
| StreamingBench causal 8-frame pilot | 0 | 0 | 0 | 0 | 0 | 3 |

## 解释边界

- 推理组使用 Bionic medium：请求总输出上限 20,480，但实测内部思考预算约 8,192 tokens，达到预算时可插入强制回答提示。这不是无限预算或完全复现 NVIDIA 官方 vLLM 服务的结果。
- 使用服务自然缓存；首批请求可能复用技术校准缓存。数据准备与首段推理重叠，绝对延迟存在系统负载噪声。
- 延迟从客户端编码输入到解析完整回答，不含模型加载和预先完成的视频下载、解码、抽帧。
- 生成 token 包含思考 token；总 token 同时包含多模态输入。API 用量不等于 FLOPs、能耗或实际账单。
- MMStar 为六类各 50 题；MMBench 只测一种选项顺序；MMAD 仅 DS-MVTec、零参考图；StreamingBench 只测资源受限的因果八帧子集。
- 动态子集验证的是时间因果约束下的视觉问答，不是持续流式推理、真实操作任务成功率或原生音视频联合能力。
- 小样本不能据“差异不显著”宣称等效；两种方法共同答错，也不构成准确性保证。

## 可复现材料

- [完整实验协议](../docs/PUBLIC_EVALUATION_PROTOCOL.md)
- [环境记录](public-evaluation-environment.json)
- 数据集目录包含 manifest.json、records.jsonl、summary.json、REPORT.md、模型配置、源码快照、输入哈希和图表。

- [mmstar-public 详细报告](mmstar-public/REPORT.md)
- [mmbench-public 详细报告](mmbench-public/REPORT.md)
- [mmad-public 详细报告](mmad-public/REPORT.md)
- [streaming-public 详细报告](streaming-public/REPORT.md)
