# MMStar 本机公开数据评测

完成 74/1200 次请求；固定分层样本 300 题。

模型：Nemotron 3 Nano Omni Q4_K_M；无训练；seed=20260920。
抽样协议：uniform within six top-level categories; fixed before inference
所有方法使用相同图像与题目。OmniJev 调用现有 core.decide；direct 使用相同提示词和 4-token 上限，但不请求 logprobs。
reasoning 使用相同提示词，开启原生思考，上限 8192 tokens；JSON 使用现有受约束输出实现，上限 32 tokens。

| 方法 | 题数 | 正确率 | P50 秒 | P95 秒 | 平均生成 tokens | 平均总 tokens | 无效 / 截断 |
|---|---:|---:|---:|---:|---:|---:|---:|
| omnijev | 16 | 75.00% | 0.866 | 1.531 | 3.0 | 400.6 | 0 / 0 |
| direct | 16 | 87.50% | 0.842 | 1.460 | 3.0 | 393.9 | 0 / 0 |
| json | 14 | 57.14% | 1.373 | 1.973 | 10.4 | 418.6 | 0 / 0 |
| reasoning | 28 | 78.57% | 12.895 | 133.478 | 1339.3 | 1734.0 | 2 / 2 |

## 配对准确率差：OmniJev − 基线

| 基线 | 配对题数 | 差值百分点 | 保守 95% 区间 | 非劣检验 |
|---|---:|---:|---|---|
| reasoning | 1 | 0.00 | [-98.75, 98.75] | 未证实 2pp 非劣 |

## 各类别正确题数

| 类别 | OmniJev | Direct | JSON | Reasoning |
|---|---:|---:|---:|---:|
| coarse perception | 0/0 | 0/0 | 1/3 | 4/4 |
| fine-grained perception | 3/3 | 3/3 | 1/3 | 4/5 |
| instance reasoning | 2/2 | 3/4 | 1/2 | 5/6 |
| logical reasoning | 0/1 | 3/3 | 1/1 | 4/5 |
| math | 5/6 | 2/2 | 2/3 | 3/4 |
| science & technology | 2/4 | 3/4 | 2/2 | 2/4 |

## 解释范围

- 这是公开数据的固定先导子集，不是官方全量榜单成绩。
- 准确率分母包含所有请求；无效、超时、截断失败均不会被剔除。
- 完成耗时从客户端开始编码媒体到解析回答；包含 HTTP，排除模型加载；不是 TTFT。
- 服务自然缓存开启，请求全局随机排序。没有清空缓存，因此不能把结果称作冷启动延迟。
- completion_tokens 包含服务报告的思考 token；不得再把 reasoning_tokens 相加。
- token 统计采用后端口径；不能据此断言视觉编码计算量或能耗按相同比例下降。
- 图像选择题和因果视频回放均不证明音视频联合能力、持续流式执行或闭环任务完成率。
- 非劣界限预设为 2 个百分点；bootstrap 结果为先导分析，不能把无显著差异等同于等效。
- 主区间对配对 win/loss 概率采用 Bonferroni + Clopper-Pearson 保守界，避免零差异时 bootstrap 区间退化为零；仅用于独立图像。分层抽样推断仅面向该均衡类别混合。
- 模型可能接触过公开数据；这里主要比较同一骨干的推理策略，不声称排除预训练污染。
- 原始逐题记录、原始响应、用量、哈希与抽样清单都保存在本目录。

数据来源：https://huggingface.co/datasets/Lin-Chen/MMStar
复现：python3 scripts/public_benchmark.py --out results/mmstar-public；汇总：python3 scripts/report_public_benchmark.py --out results/mmstar-public
