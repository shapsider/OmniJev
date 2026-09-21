"""Produce the final suite report only after every fixed request completes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAMES=['mmstar-public','mmbench-public','mmad-public','streaming-public']


def main():
    summaries={}
    for name in NAMES:
        s=json.loads((ROOT/'results'/name/'summary.json').read_text())
        if s['completed_requests']!=s['expected_requests']:
            raise SystemExit('Incomplete: '+name)
        summaries[name]=s
    lines=['# OmniJev 本机公开 Benchmark 评测','',
        '完成四个固定先导子集：425 个问题、1,700 次正式请求。模型为本机 Nemotron 3 Nano Omni Q4_K_M，权重冻结。',
        '这些是局部先导实验，不是四个官方 benchmark 的全量成绩。主正确率允许从最终输出明确解析选项；严格格式通过情况单独报告，不从隐藏思考过程挑选答案。',
        '本轮研究判断与课题调整建议见 [评测结论](PUBLIC_EVALUATION_FINDINGS.md)。',
        '', '## 正确率', '', '| 数据集 | 题数 | OmniJev | 普通短答案 | JSON | 原生推理 |', '|---|---:|---:|---:|---:|---:|']
    for name,s in summaries.items():
        m=s['methods']
        lines.append('| '+s['dataset']+f' | {s["expected_cases"]} | '+' | '.join(f'{m[x]["accuracy"]:.2f}%' for x in ('omnijev','direct','json','reasoning'))+' |')
    lines+=['', '## 响应耗时与 token', '', '| 数据集 | OmniJev P50/P95 秒 | 推理 P50/P95 秒 | OmniJev / 推理平均生成 tokens | 总 token 节省 |', '|---|---:|---:|---:|---:|']
    for name,s in summaries.items():
        o=s['methods']['omnijev'];r=s['methods']['reasoning']
        saved=100*(1-o['total_tokens_mean']/r['total_tokens_mean'])
        lines.append(f'| {s["dataset"]} | {o["latency_p50"]:.3f} / {o["latency_p95"]:.3f} | {r["latency_p50"]:.3f} / {r["latency_p95"]:.3f} | {o["completion_tokens_mean"]:.1f} / {r["completion_tokens_mean"]:.1f} | {saved:.2f}% |')
    lines+=['', '## 准确率保持检验', '', '差值定义为 OmniJev − 原生推理；负数表示 OmniJev 较低。非劣界限预设为最多下降 2 个百分点。答案一致率另外计算，不能代替对标准答案的正确率。', '', '| 数据集 | 差值百分点 | 保守 95% 区间 | 答案一致率 | 结论 |', '|---|---:|---:|---:|---|']
    for name,s in summaries.items():
        d=s['comparisons']['reasoning']
        ci=d['conservative_95_ci_pp']
        interval=f'[{ci[0]:.2f}, {ci[1]:.2f}]' if ci else '见聚类 bootstrap'
        lines.append(f'| {s["dataset"]} | {d["accuracy_difference_pp"]:.2f} | {interval} | {d["agreement"]:.2f}% | '+('达到先导非劣标准' if d['noninferior_at_2pp'] else '未证实准确率非劣')+' |')
    lines+=['', '## 5 秒响应期限内的正确率', '', '分母为全部请求；答错、无法明确解析、超时、或答对但超过 5 秒均不计成功。更完整的时间预算曲线见各数据集 deadline.png。', '', '| 数据集 | OmniJev | 普通短答案 | JSON | 原生推理 |', '|---|---:|---:|---:|---:|']
    for name,s in summaries.items():
        lines.append('| '+s['dataset']+' | '+' | '.join(f'{s["methods"][m]["timely_accuracy"]["5"]:.2f}%' for m in ('omnijev','direct','json','reasoning'))+' |')
    lines+=['', '## 普通短答案强基线', '', '| 数据集 | OmniJev / Direct P50 秒 | OmniJev / Direct 平均生成 tokens | 答案一致率 | 准确率差百分点 |', '|---|---:|---:|---:|---:|']
    for name,s in summaries.items():
        d=s['comparisons']['direct']
        o=s['methods']['omnijev'];b=s['methods']['direct']
        lines.append(f'| {s["dataset"]} | {o["latency_p50"]:.3f} / {b["latency_p50"]:.3f} | {o["completion_tokens_mean"]:.1f} / {b["completion_tokens_mean"]:.1f} | {d["agreement"]:.2f}% | {d["accuracy_difference_pp"]:.2f} |')
    lines+=['', '当前实现的短标签路径与普通短答案使用相同模型、提示词和生成预算，主要差异是是否返回 logprobs。相近的结果应归因于通用模型的短答案能力，不能解释为新模型范式的独立优势。',
        '', '## 严格格式不合规与截断', '', '格式不合规不一定意味着无法解析最终答案；主正确率采用前述语义答案口径。后两列统计推理组。', '', '| 数据集 | OmniJev 格式不合规 | 普通短答案格式不合规 | JSON 格式不合规 | 推理格式不合规 | 输出截断 | 思考预算强制回答 |', '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in summaries.items():
        m=s['methods']
        lines.append('| '+s['dataset']+' | '+' | '.join(str(m[x]['invalid']) for x in ('omnijev','direct','json','reasoning'))+f' | {m["reasoning"]["truncated"]} | {m["reasoning"]["reasoning_budget_forced"]} |')
    lines+=['', '## 解释边界', '',
        '- 推理组使用 Bionic medium：请求总输出上限 20,480，但实测内部思考预算约 8,192 tokens，达到预算时可插入强制回答提示。这不是无限预算或完全复现 NVIDIA 官方 vLLM 服务的结果。',
        '- 使用服务自然缓存；首批请求可能复用技术校准缓存。数据准备与首段推理重叠，绝对延迟存在系统负载噪声。',
        '- 延迟从客户端编码输入到解析完整回答，不含模型加载和预先完成的视频下载、解码、抽帧。',
        '- 生成 token 包含思考 token；总 token 同时包含多模态输入。API 用量不等于 FLOPs、能耗或实际账单。',
        '- MMStar 为六类各 50 题；MMBench 只测一种选项顺序；MMAD 仅 DS-MVTec、零参考图；StreamingBench 只测资源受限的因果八帧子集。',
        '- 动态子集验证的是时间因果约束下的视觉问答，不是持续流式推理、真实操作任务成功率或原生音视频联合能力。',
        '- 小样本不能据“差异不显著”宣称等效；两种方法共同答错，也不构成准确性保证。',
        '', '## 可复现材料', '',
        '- [完整实验协议](../docs/PUBLIC_EVALUATION_PROTOCOL.md)',
        '- [环境记录](public-evaluation-environment.json)',
        '- 数据集目录包含 manifest.json、records.jsonl、summary.json、REPORT.md、模型配置、源码快照、输入哈希和图表。', '']
    for name in NAMES:
        lines.append(f'- [{name} 详细报告]({name}/REPORT.md)')
    (ROOT/'results/PUBLIC_BENCHMARK_REPORT.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'results/public-suite-summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
    print('Wrote results/PUBLIC_BENCHMARK_REPORT.md')


if __name__=='__main__':main()
