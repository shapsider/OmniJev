# OmniJev 本机具身评测报告

日期：2026-09-21。Mac M5 Pro / 48GB，Bionic 已加载 Nemotron 3 Nano Omni Q4_K_M，API 别名 `omnijev-nemotron`。不训练、无云端推理。模型状态见 `embodied/backend.json`。

工作台基于 [FBddcz/embodied-jev](https://github.com/FBddcz/embodied-jev)，固定 commit `59a00c60e0f80fa32d14df1a365166267505980c`。本报告全部是本机运行记录，不是上游成绩。

## 协议

- 技能模式：仿真真值状态 → 模型选择技能 → 程序控制 IK 轨迹。三种任务为搬运、堆叠、越障；每种 seed=0，四策略共 12 回合。
- 直接视觉：双相机 RGB + 本体反馈 → 21 个固定增量动作；模型输入没有对象/目标真值坐标。安全预演、接触与终态评估使用物理仿真真值。搬运 seed=0，OmniJev / Direct 各一回合，60 步预算。
- 同骨干、相同决策提示与证据格式；OmniJev 与 Direct 均关闭思考、T=0、4-token 上限。OmniJev 额外读取 top-10 logprobs；不是零解码隐藏状态投影。候选不足覆盖时不伪造分数。
- 推理组 medium、T=0.6、top_p=0.95、总输出上限 4096。不同于已有公开问答的 20480 上限。没有截短后代答，失败保留。
- 固定候选重排、任务顺序随机种子 20260921；逐回合串行独立进程，自然缓存，模型预加载，分数门槛为零，物理安全预演开启。
- 成功由真实物理终态判断；墙钟包含策略、预演、执行，不含模型加载/初始建场。输入和输出 token 均来自后端 usage；输出包含思考 token。
- 请求 P50/P95 对实际 API 调用汇总，非独立任务样本；回合时间与 token 汇总按实际执行轨迹，推理策略可能调用更多次。


## rules-smoke

3/3 回合，状态 `complete`；观测 `privileged`，控制 `skills`。

| 策略 | 成功/总数 | 平均回合秒 | 请求 P50/P95 秒 | API 次数 | 输入 tokens | 输出 tokens | 不完整用量回合 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 规则基线 | 3/3 | 1.11 | — | 0 | 0 | 0 | 0 |

| 任务 | 策略 | 成功 | 状态 | 回合秒 | 步数 |
|---|---|---|---|---:|---:|
| stack | 规则基线 | 是 | completed | 1.11 | 8 |
| barrier | 规则基线 | 是 | completed | 1.10 | 8 |
| transfer | 规则基线 | 是 | completed | 1.12 | 8 |

[原始逐回合数据](embodied/rules-smoke/episodes.jsonl) · [完整协议](embodied/rules-smoke/manifest.json) · [统计](embodied/rules-smoke/summary.json)。同目录保存逐请求、轨迹和视觉相机归档；所有失败都在分母中。

## skills-seed0

12/12 回合，状态 `complete`；观测 `privileged`，控制 `skills`。

| 策略 | 成功/总数 | 平均回合秒 | 请求 P50/P95 秒 | API 次数 | 输入 tokens | 输出 tokens | 不完整用量回合 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 规则基线 | 3/3 | 1.10 | — | 0 | 0 | 0 | 0 |
| OmniJev | 3/3 | 10.58 | 0.699 / 1.390 | 39 | 26,476 | 117 | 0 |
| 普通短答案 | 3/3 | 6.84 | 0.442 / 0.539 | 39 | 26,476 | 117 | 0 |
| 有限预算推理 | 3/3 | 204.86 | 13.283 / 28.914 | 43 | 29,218 | 30,573 | 0 |

| 任务 | 策略 | 成功 | 状态 | 回合秒 | 步数 |
|---|---|---|---|---:|---:|
| transfer | 普通短答案 | 是 | completed | 7.87 | 8 |
| stack | 有限预算推理 | 是 | completed | 155.56 | 8 |
| stack | 规则基线 | 是 | completed | 1.11 | 8 |
| barrier | OmniJev | 是 | completed | 14.39 | 8 |
| barrier | 规则基线 | 是 | completed | 1.10 | 8 |
| stack | OmniJev | 是 | completed | 10.90 | 8 |
| stack | 普通短答案 | 是 | completed | 6.21 | 8 |
| barrier | 普通短答案 | 是 | completed | 6.44 | 8 |
| transfer | OmniJev | 是 | completed | 6.44 | 8 |
| barrier | 有限预算推理 | 是 | completed | 268.21 | 10 |
| transfer | 规则基线 | 是 | completed | 1.08 | 8 |
| transfer | 有限预算推理 | 是 | completed | 190.82 | 8 |

[原始逐回合数据](embodied/skills-seed0/episodes.jsonl) · [完整协议](embodied/skills-seed0/manifest.json) · [统计](embodied/skills-seed0/summary.json)。同目录保存逐请求、轨迹和视觉相机归档；所有失败都在分母中。

技能先导中，OmniJev 相对推理的平均回合加速 19.37×，输入＋输出总 token 减少 55.52%。普通短答案也为 3/3 成功，平均 6.84 秒，且与 OmniJev 用量一致；没有观察到候选分数带来额外任务收益。自然缓存、执行顺序和本地负载均会影响速度，不能从三个回合推断稳定倍率。

## vision-seed0

2/2 回合，状态 `complete`；观测 `vision`，控制 `incremental`。

| 策略 | 成功/总数 | 平均回合秒 | 请求 P50/P95 秒 | API 次数 | 输入 tokens | 输出 tokens | 不完整用量回合 |
|---|---:|---:|---:|---:|---:|---:|---:|
| OmniJev | 0/1 | 286.00 | 4.765 / 4.960 | 60 | 228,408 | 180 | 0 |
| 普通短答案 | 0/1 | 285.55 | 4.622 / 4.866 | 60 | 228,408 | 180 | 0 |

| 任务 | 策略 | 成功 | 状态 | 回合秒 | 步数 |
|---|---|---|---|---:|---:|
| transfer | 普通短答案 | 否 | exhausted | 285.55 | 60 |
| transfer | OmniJev | 否 | exhausted | 286.00 | 60 |

[原始逐回合数据](embodied/vision-seed0/episodes.jsonl) · [完整协议](embodied/vision-seed0/manifest.json) · [统计](embodied/vision-seed0/summary.json)。同目录保存逐请求、轨迹和视觉相机归档；所有失败都在分母中。

视觉失败：普通短答案 在 60 步结束，状态 `exhausted`，运行时原因：已达到动作预算。不会用技能模式成绩替代。

视觉失败：OmniJev 在 60 步结束，状态 `exhausted`，运行时原因：已达到动作预算。不会用技能模式成绩替代。

## 研究判断与限制

这次交付验证了一个无需训练的本地决策运行时、具身实验台和可审计评测链路。技能任务的小样本证明系统可工作，但不证明开放场景规划能力、统计非劣或相对普通短答案的独立优势。公开 425 题的证据见 [公开报告](PUBLIC_BENCHMARK_REPORT.md)，与具身结果不合并算准确率。

建议将课题定义为“冻结多模态模型的低延迟闭环决策接口与自适应计算”，保留 Direct 强基线。下一阶段独立验证更多种子、视觉感知/控制误差、扰动恢复、决策期限下的成功率，以及什么时候应升级推理。Adaptive 目前只有契约测试，不能宣称已经提升效果。

物理仿真在模型等待时暂停，本实验尚未验证持续运动环境中的实时风险；500Hz 是物理步进频率，不是模型决策频率。图像模式已经实际发送 PNG 并执行动作，但音频和持续视频编码尚未接通。所有结果只覆盖此冻结骨干、量化与本机运行时。

## 复现与验证

详见 [项目集成说明](../docs/EMBODIED_INTEGRATION.md)。请为新实验指定新的输出目录；已有完整结果只会校验并跳过，不会自动重跑或覆盖失败。新机器的源码包不包含第三方公开 benchmark 图片/视频或模型权重，重新评测公开数据需按原协议下载与准备，既有成绩仍可离线查看。具身 Panda 资产、Web 构建产物和全部源码已包含。

验证证据见 [validation.json](embodied/validation.json)。规则 smoke 与浏览器手工验收属于安装/功能检查，不并入正式 12 回合。浏览器初次非零分数门槛触发过暂停，其记录单独保留；正式评测固定零门槛。

