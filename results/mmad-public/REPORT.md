# MMAD DS-MVTec zero-shot pilot 本机公开数据评测

完成 180/180 次请求；固定分层样本 45 题。

模型：Nemotron 3 Nano Omni Q4_K_M；无训练；seed=20260920。
抽样协议：5 questions per annotation type, distinct images, DS-MVTec partition only; no reference images or domain knowledge; no previous QA answers.
所有方法使用相同图像与题目。OmniJev 调用现有 core.decide；direct 使用相同提示词和 4-token 上限，但不请求 logprobs。
reasoning 使用相同提示词，reasoning_effort=medium，temperature=0.6、top_p=0.95，总输出上限 20480 tokens。实测 Bionic 约在 8192 个思考 token 后可插入强制回答提示；这不是无限预算或完整 NVIDIA vLLM 配置。JSON 使用现有受约束输出实现，上限 32 tokens。
主正确率允许从最终输出末行明确解析选项；严格正确率要求完全遵守返回格式。原始记录的 correct 保持严格口径，未改写。

| 方法 | 题数 | 答案正确率 | 严格正确率 | P50 秒 | P95 秒 | 平均生成 tokens | 平均总 tokens | 严格无效 / 截断 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| omnijev | 45 | 86.67% | 86.67% | 0.659 | 1.088 | 3.0 | 357.9 | 0 / 0 |
| direct | 45 | 86.67% | 86.67% | 0.587 | 1.134 | 3.0 | 357.9 | 0 / 0 |
| json | 45 | 84.44% | 84.44% | 0.828 | 1.220 | 11.0 | 372.9 | 0 / 0 |
| reasoning | 45 | 86.67% | 86.67% | 5.745 | 47.057 | 914.3 | 1269.2 | 0 / 0 |

## 配对准确率差：OmniJev − 基线

| 基线 | 配对题数 | 差值百分点 | 保守 95% 区间 | 非劣检验 |
|---|---:|---:|---|---|
| direct | 45 | 0.00 | [-9.28, 9.28] | 未证实 2pp 非劣 |
| json | 45 | 2.22 | [-9.25, 13.36] | 未证实 2pp 非劣 |
| reasoning | 45 | 0.00 | [-19.01, 19.01] | 未证实 2pp 非劣 |

## 各类别正确题数

| 类别 | OmniJev | Direct | JSON | Reasoning |
|---|---:|---:|---:|---:|
| Anomaly Detection | 4/5 | 4/5 | 4/5 | 4/5 |
| Defect Analysis | 5/5 | 5/5 | 5/5 | 5/5 |
| Defect Classification | 4/5 | 4/5 | 4/5 | 4/5 |
| Defect Description | 5/5 | 5/5 | 5/5 | 5/5 |
| Defect Localization | 5/5 | 5/5 | 4/5 | 4/5 |
| Object Analysis | 4/5 | 4/5 | 4/5 | 4/5 |
| Object Classification | 5/5 | 5/5 | 5/5 | 5/5 |
| Object Details | 3/5 | 3/5 | 3/5 | 4/5 |
| Object Structure | 4/5 | 4/5 | 4/5 | 4/5 |

## 解释范围

- 这是公开数据的固定先导子集，不是官方全量榜单成绩。
- 准确率分母包含所有请求；无法明确解析、超时和无最终答案的截断均不会被剔除。严格格式不合规与答案错误分开报告。
- 完成耗时从客户端开始编码媒体到解析回答；包含 HTTP，排除模型加载；不是 TTFT。
- 服务自然缓存开启，请求全局随机排序。没有清空缓存，因此不能把结果称作冷启动延迟。
- completion_tokens 包含服务报告的思考 token；不得再把 reasoning_tokens 相加。
- token 统计采用后端口径；不能据此断言视觉编码计算量或能耗按相同比例下降。
- summary.json 的 usage_coverage 记录用量报告覆盖数。接口错误未报告的 token 成本未知，不会虚构为零。
- reasoning_budget_forced 单独统计后端插入强制回答提示的次数；它与 finish_reason=length 的截断不同，即使 finish_reason=stop 也可能已触发内部思考预算。
- 图像选择题和因果视频回放均不证明音视频联合能力、持续流式执行或闭环任务完成率。
- 非劣界限预设为 2 个百分点；bootstrap 结果为先导分析，不能把无显著差异等同于等效。
- 主区间对配对 win/loss 概率采用 Bonferroni + Clopper-Pearson 保守界，避免零差异时 bootstrap 区间退化为零；仅用于独立图像。分层抽样推断仅面向该均衡类别混合。
- 推理组采用推荐温度 0.6、单种子单次采样；没有重复采样来估计解码随机性的影响。
- 模型可能接触过公开数据；这里主要比较同一骨干的推理策略，不声称排除预训练污染。
- 原始逐题记录、原始响应、用量、哈希与抽样清单都保存在本目录。

数据来源：https://huggingface.co/datasets/jiang-cc/MMAD
复现：python3 scripts/public_benchmark.py --out /Users/lukatang/Desktop/paper/OmniJev/results/mmad-public；汇总：python3 scripts/report_public_benchmark.py --out /Users/lukatang/Desktop/paper/OmniJev/results/mmad-public
