# OmniJev 推文文案

所有数字都来自仓库内的实验结果，出处见每条文案末尾。发之前请先读最后一节「数字与边界」。

---

## 中文 · 主推文（微博 / X / 即刻）

> Jev 的短板不是模型不够强，是它只能读文本。
>
> OmniJev 把同一套「状态 → 有限候选决策」接口接上了眼睛：外部相机 + 腕部相机的 640×480 RGB，作为原生图像块，和本体感知一起进同一次请求。
>
> 为什么这件事重要：具身智能的决策信号本来就是视觉的。少了图像通道，再好的决策接口也进不了这个领域。
>
> 我们把它做成了能跑的闭环：
> · 双相机采集 → MuJoCo 执行 → 安全预演 → 轨迹回放
> · 逐请求证据链：输入哈希、延迟、token 用量；每张模型输入图像单独归档 SHA-256
> · 技能模式下 3/3 任务（搬运 / 堆叠 / 越障），单次决策 P50 0.70 s，输出 token 117（预算式推理 30 573）
>
> 也得说清边界：这一轮四种策略都是 3/3，所以这是延迟和成本的结果，不是成功率的结果。真正端到端的视觉测试——原始 RGB、不给物体与目标的真值坐标——任务没有完成，60 步预算耗尽，0/1。相机链路是通的，图像确实到了模型；冻结主干还跟不上的是决策质量。这正是 Vision-Jev 原生 RLCD 训练要补的部分。
>
> 仓库：github.com/Iron-LYK/OmniJev
> 任何保存的 episode 都能离线重渲染成上面那段视频，不需要推理后端。

配图：`omnijev-transfer.gif`（首图）+ `omnijev-vs-jev-zh.png`

---

## 中文 · 短版（单条，适合先试水）

> Jev 只能读文本，OmniJev 能读机器人看到的东西。
>
> 同一套「状态 → 有限候选决策」接口，把外部相机 + 腕部相机的 640×480 RGB 作为原生图像块接进同一次请求。具身决策的信号本来就是视觉的，缺了图像通道就进不了这个领域。
>
> 技能模式 3/3 任务，单次决策 P50 0.70 s，输出 token 117。端到端视觉还没解决——0/1，60 步预算耗尽——这正是 Vision-Jev 要补的。
>
> github.com/Iron-LYK/OmniJev

配图：`omnijev-vs-jev-zh.png`

---

## English · main post

> Jev's limitation isn't the model. It's that Jev can only read text.
>
> OmniJev wires the same state → finite-choice interface to the robot's eyes: 640×480 RGB from an external camera and a wrist camera, sent as native image blocks alongside proprioception in one request.
>
> Why it matters: embodied decision-making runs on visual signals. Without an image channel, a decision interface cannot enter that domain at all.
>
> What we built:
> · dual-camera capture → MuJoCo execution → safety preview → trajectory replay
> · a per-request evidence trail — input hash, latency, token usage, and a SHA-256 for every image the model actually received
> · skill mode 3/3 tasks, P50 0.70 s per decision, 117 output tokens (budgeted reasoning: 30,573)
>
> And the honest part: all four strategies in that pilot solved 3/3, so these are latency and cost numbers, not success-rate numbers. Where vision was tested end to end — raw RGB, no ground-truth object coordinates — the task was not solved: 0/1, 60-step budget exhausted. The camera path works and the images reach the model; the decision quality from a frozen backbone does not yet follow. That is what native RLCD training on Vision-Jev is for.
>
> Repo: github.com/Iron-LYK/OmniJev
> Any saved episode re-renders to video offline, no inference backend required.

Image: `omnijev-transfer.gif` first, then `omnijev-vs-jev.png`

---

## English · short version

> Jev reads text. OmniJev reads what the robot sees.
>
> Same state → finite-choice interface, now with 640×480 RGB from an external and a wrist camera arriving as native image blocks in the same request. Embodied decisions run on visual signals — without an image channel you cannot enter the domain.
>
> 3/3 tasks in skill mode, P50 0.70 s per decision, 117 output tokens. End-to-end vision is not solved yet — 0/1, budget exhausted. That is what Vision-Jev is for.
>
> github.com/Iron-LYK/OmniJev

---

## 可选的追问式开头（互动更好，风险略高）

> 如果 Jev 只能读文本，它到底能不能用在机器人上？
>
> 我们的答案是：接口可以留下，模态必须补上。OmniJev 把外部相机和腕部相机的原始 RGB 接进了同一套有限候选决策流程——图像以原生图像块进入同一次请求，和本体感知、接触反馈并列。
>
> 结果一半是好消息：闭环跑通了，证据链是完整的。一半是诚实的坏消息：端到端视觉还没成。

---

## 数字与边界（发之前必读）

引用时可以放心使用的数字，全部出自 `results/EMBODIED_BENCHMARK_REPORT.md`（2026-09-21，Mac M5 Pro 48 GB，Nemotron 3 Nano Omni Q4_K_M，本地推理）：

| 数字 | 含义 | 出处 |
| --- | --- | --- |
| 3/3 | 技能模式、seed 0、privileged 状态下完成搬运 / 堆叠 / 越障 | `results/embodied/skills-seed0/summary.json` |
| P50 0.699 s / P95 1.390 s | OmniJev 快速通路的单次请求延迟 | 同上（`request_latency_ms_p50/p95`） |
| 19.0× | 相对预算式推理（P50 13.283 s）的单次请求提速 | 报告原文写 19.37×，按 P50 比值算约 19.0× |
| 117 vs 30,573 | 三个 episode 的输出 token 总量对比预算式推理 | `summary.json`（`output_tokens_known`） |
| 26,476 / 117 | OmniJev 技能模式三个 episode 的输入 / 输出 token | 同上 |
| 0/1 | 端到端视觉（双相机、原始 RGB、无真值坐标）60 步预算耗尽 | `results/embodied/vision-seed0/` |
| 640×480 × 2 | 每个决策周期采集的外部 + 腕部图像 | `transfer-0-omnijev.cameras.zip` 的 manifest |

**必须同时说清的边界：**

1. **四种策略都是 3/3。** 规则基线、OmniJev、直接短答、预算式推理全部成功，所以可测出的差异是延迟与 token 成本，不是成功率。报告明确写了：不能据此宣称对直接短答有独立优势，三轮也不足以推断稳定倍数。
2. **技能模式 ≠ 视觉规划。** 技能模式下模型读的是特权仿真状态，选预设技能后由程序执行 IK；图像并没有进入这条链路。视觉能力来自另一条模式（`--observation vision --control incremental`）。
3. **视觉模式是负面结果。** 端到端跑下来是 0/1，两个策略都把 60 步预算耗尽了。可以说「相机链路与证据链已通」，不能说「视觉决策可用」。
4. **仿真，不是真机。** 等待模型响应时物理仿真会暂停，因此本轮没有测「推理等待期间机器人继续运动」的风险；500 Hz 是物理步频，不是模型决策频率。
5. **没有音频与连续视频。** 图像是逐帧采集（决策边界各采一次），不是连续视频流。

把 3 和 4 说出来不会削弱传播，反而让「多模态闭环 + 可审计证据链」这个真正的主张更难被反驳。
