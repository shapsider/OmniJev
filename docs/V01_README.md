# OmniJev v0.1

本机、不训练、有限选项决策原型。已在 Apple M5 Pro / 48 GB 上实测 Nemotron 3 Nano Omni Q4_K_M 和 Qwen3.8-27B MLX 4-bit。

**当前验证范围是文本、图像与有序图像帧。现有 Nemotron GGUF/投影/运行时组合明确报告音频不可用，因此本版本不是已完成的全模态模型。** 提供音频请求接口和失败诊断，不会把 ASR 转录伪装成原生音频理解。

## 快速体验

在项目根目录运行，使用系统 Python 3.9+，无需 pip 安装。Bionic 应已打开。

```sh
sh scripts/start_bionic.sh nemotron
python3 -m omnijev --case data/example.json
```

自定义问题：

```sh
python3 -m omnijev \
  --image data/assets/spatial0.png \
  --question 'Is the red circle to the left of the blue square?' \
  --options yes no 'insufficient evidence'
```

受限 JSON 对照：

```sh
python3 -m omnijev --case data/example.json --mode json
```

Qwen：先用 `lms unload omnijev-nemotron` 卸载实验模型，再运行 `sh scripts/start_bionic.sh qwen`；调用时加 `--model omnijev-qwen`。不要同时加载两个大模型。CLI 的 `lms` 如不在 PATH，完整路径为 `/Applications/Bionic.app/Contents/Resources/app/.webpack-bionic/lms`。

## 输出含义

- `choice` / `value`：选项字母及原始选项内容。
- `valid`：输出属于候选集合，不代表语义正确。
- `scores.probabilities`：首个返回答案位置上，规范单字母 token 的候选内归一化分数，**不是校准后的正确概率**。
- `candidate_mass`：这些规范候选在返回 token 分布中的质量；不包含空格变体。
- `incomplete_top_k`：有候选未出现在 API 返回的 top-k 中；此时整个概率字段返回 null，绝不补零或编造。
- `latency_seconds`：API 请求往返耗时，包括服务端计算；不包含模型加载、客户端读文件和 base64 编码。不能直接称为完整端到端延迟。
- `response`：保存到文件时包含完整原始模型响应，方便审计。

`letter` 方法实际上会生成短标签并读取 logprobs；不是内部零解码 forward。Nemotron 的隐藏结构 token 使 `max_tokens=1` 无法得到答案，因此预算为 4。JSON 预算为 32，两者关闭思考、temperature=0。

## 重现实验

```sh
python3 scripts/build_fixture.py
python3 scripts/build_stress.py
python3 -m unittest discover -s tests -v
python3 scripts/run_benchmark.py --model omnijev-nemotron --output results/new-run.jsonl --repeats 2
python3 scripts/run_benchmark.py --model omnijev-nemotron --fixture data/stress.json --output results/new-stress.jsonl --repeats 2
python3 scripts/summarize.py results/new-run.jsonl results/new-stress.jsonl
```

结果文件不可覆盖。`summarize.py` 会重新计算规范字母分数，并更新 `results/summary.json` 和 `results/scored-records.jsonl`；原始 run 文件保持不变。当前汇总同时保留 API 错误数和总请求数，错误不会作为快速推理混入耗时统计。

## 实验范围与局限

基础 fixture 为 19 个程序生成样本：17 个文本/视觉诊断、2 个音频能力探针。stress 为另外 9 个诊断，包含相同媒体的不同问题/候选置换。两轮重复不等于独立样本，衍生问题也不独立。

请求顺序按固定种子打乱，先进行未计分热身。使用服务默认缓存，未隔离冷/热前缀；因此只报告描述性耗时，不作统计显著性或方法加速结论。没有训练、校准或测试集阈值选择。没有大规模真实数据、长视频、复杂音视频推理、共享前缀并行引擎或风险控制保证。

原始数据很简单，准确率饱和不能证明研究创新。本项目是进一步研究的可运行起点。

## 已定位的后端差异

1. Bionic 兼容接口需要 `reasoning_effort=none`；仅传 `chat_template_kwargs.enable_thinking=false` 未能关闭 Nemotron 思考。
2. MLX 的 `top_logprobs` 最大为 10。Nemotron 初轮为 20，当前代码统一为 10。
3. Bionic `/v1/chat/completions` 拒绝 `input_audio`（HTTP 400）。直接调用附带 llama.cpp，同一模型与投影仍拒绝音频（HTTP 500），`results/native-props.json` 中 `audio=false`。
4. 多帧图像诊断只是按顺序输入图片，不等同于原生连续视频或音视频同步测试。

## 主要文件

- `omnijev/core.py`：有限选项接口、严格解析、候选分数提取。
- `omnijev/__main__.py`：命令行入口，支持自定义图像、音频、文字和选项。
- `scripts/`：启动、生成诊断数据、运行和汇总。
- `tests/test_core.py`：防止概率误报的完整性测试。
- `results/EXPERIMENT_REPORT.md`：本机实验结论。
- `results/environment.json`：模型文件、量化及环境记录，不包含凭据。

本项目不复现 TypeSafe 未公开的 Jev 架构或 RLCD。它使用通用冻结模型执行相似的有限选项接口。
