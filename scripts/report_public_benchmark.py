"""Summarize paired public benchmark records without dropping failures."""
import collections
import argparse
import json
import math
import random
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/mmstar-public'
METHODS = ['omnijev', 'direct', 'json', 'reasoning']


def semantic_choice(record, labels):
    """Normalize explicit final answers only; never inspect hidden reasoning."""
    if record.get('choice') in labels:return record['choice']
    raw=record.get('raw_text') or ''
    if record.get('method')=='json':
        try:
            obj=json.loads(raw)
            if isinstance(obj,dict) and obj.get('choice') in labels:return obj['choice']
        except (ValueError,TypeError):pass
    lines=[line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:return None
    last=lines[-1].replace('**','').replace('`','').strip()
    patterns=[r'\(?([A-Z])\)?[.]?',
        r'(?:Final\s+answer|Answer|The\s+correct\s+(?:answer|option)|Option)(?:\s+is)?\s*[:=]?\s*\(?([A-Z])\)?[.]?',
        r'\$?\\boxed\{([A-Z])\}\$?']
    for pattern in patterns:
        match=re.fullmatch(pattern,last,flags=re.IGNORECASE)
        if match and match[1].upper() in labels:return match[1].upper()
    return None


def budget_forced(record):
    response=record.get('response') or {}
    choices=response.get('choices') or []
    reasoning=(choices[0].get('message',{}).get('reasoning_content') or '') if choices else ''
    tokens=(record.get('usage') or {}).get('completion_tokens_details',{}).get('reasoning_tokens',0) or 0
    return tokens>=8000 and 'I have to answer now.' in reasoning


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values)-1)*q
    lo = int(pos)
    return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(pos-lo)


def paired_interval(pairs):
    clusters = collections.defaultdict(list)
    for a, b in pairs:
        clusters[a['image_sha256']].append(int(a['correct'])-int(b['correct']))
    groups = list(clusters.values())
    if not groups:
        return None
    rng = random.Random(20260920)
    means = []
    for _ in range(10000):
        sample = [groups[rng.randrange(len(groups))] for _ in groups]
        means.append(100*sum(map(sum,sample))/sum(map(len,sample)))
    return [quantile(means,.025), quantile(means,.975)]


def conservative_paired_interval(pairs):
    """Bonferroni Clopper-Pearson bounds on win/loss probabilities.

    Valid for independent images; avoids degenerate bootstrap intervals when
    all observed paired outcomes agree. Four tails each use alpha/4.
    """
    n = len(pairs)
    if len({a['image_sha256'] for a,b in pairs}) != n:
        return None
    def solve(k, target):
        lo, hi = 0., 1.
        for _ in range(60):
            p = (lo+hi)/2
            cdf = sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k+1))
            if cdf > target:
                lo = p
            else:
                hi = p
        return (lo+hi)/2
    def bounds(k):
        return (0. if k==0 else solve(k-1, .9875),
                1. if k==n else solve(k, .0125))
    wl,wu = bounds(sum(a['correct'] and not b['correct'] for a,b in pairs))
    ll,lu = bounds(sum(b['correct'] and not a['correct'] for a,b in pairs))
    return [100*(wl-lu),100*(wu-ll)]


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='results/mmstar-public')
    args=parser.parse_args()
    OUT=ROOT/args.out
    manifest = json.loads((OUT/'manifest.json').read_text())
    rows = [json.loads(s) for s in (OUT/'records.jsonl').read_text().splitlines()]
    case_map={c['id']:c for c in manifest['cases']}
    for r in rows:
        labels=[chr(65+i) for i in range(len(case_map[r['case_id']]['options']))]
        r['contract_correct']=r['correct']
        r['choice']=semantic_choice(r,labels)
        r['correct']=r['choice']==r['gold']
    keys = [(r['case_id'],r['method']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate case/method record')
    summary = dict(dataset=manifest['dataset'], expected_cases=len(manifest['cases']), expected_requests=len(manifest['cases'])*4,
                   completed_requests=len(rows), methods={}, comparisons={})
    for method in METHODS:
        rs = [r for r in rows if r['method']==method]
        if not rs:
            continue
        usage = [r['usage'] for r in rs if r.get('usage')]
        d = dict(n=len(rs), accuracy=100*sum(r['correct'] for r in rs)/len(rs),
            strict_accuracy=100*sum(r['contract_correct'] for r in rs)/len(rs),
            invalid=sum(not r['valid'] for r in rs), errors=sum('error' in r for r in rs),
            truncated=sum(r.get('finish_reason')=='length' for r in rs),
            reasoning_budget_forced=sum(budget_forced(r) for r in rs),
            reasoning_detected=sum(r.get('reasoning_detected',False) for r in rs),
            latency_p50=quantile([r['wall_seconds'] for r in rs],.5),
            latency_p95=quantile([r['wall_seconds'] for r in rs],.95),
            latency_mean=statistics.mean(r['wall_seconds'] for r in rs),
            usage_coverage=len(usage), categories={}, timely_accuracy={})
        for key in ('prompt_tokens','completion_tokens','total_tokens'):
            vals=[u[key] for u in usage if key in u]
            d[key+'_mean']=statistics.mean(vals) if vals else None
        for category in sorted(set(r['category'] for r in rs)):
            subset=[r for r in rs if r['category']==category]
            d['categories'][category]=dict(n=len(subset),correct=sum(r['correct'] for r in subset))
        for deadline in (.5,1,2,5,10,30):
            d['timely_accuracy'][str(deadline)]=100*sum(r['correct'] and r['wall_seconds']<=deadline for r in rs)/len(rs)
        summary['methods'][method]=d
    indexed={(r['case_id'],r['method']):r for r in rows}
    for baseline in METHODS[1:]:
        pairs=[(indexed[c['id'],'omnijev'], indexed[c['id'],baseline]) for c in manifest['cases']
               if (c['id'],'omnijev') in indexed and (c['id'],baseline) in indexed]
        if not pairs:
            continue
        ci=paired_interval(pairs)
        exact_ci=conservative_paired_interval(pairs)
        summary['comparisons'][baseline]=dict(n=len(pairs),
            accuracy_difference_pp=100*statistics.mean(int(a['correct'])-int(b['correct']) for a,b in pairs),
            cluster_bootstrap_95_ci_pp=ci,
            conservative_95_ci_pp=exact_ci,
            noninferior_at_2pp=exact_ci is not None and exact_ci[0]>-2,
            agreement=100*sum(a.get('choice') is not None and a.get('choice')==b.get('choice') for a,b in pairs)/len(pairs),
            wins=sum(a['correct'] and not b['correct'] for a,b in pairs),
            losses=sum(b['correct'] and not a['correct'] for a,b in pairs))
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    lines=['# '+manifest['dataset']+' 本机公开数据评测','',f'完成 {len(rows)}/{summary["expected_requests"]} 次请求；固定分层样本 {len(manifest["cases"])} 题。',
        '', '模型：Nemotron 3 Nano Omni Q4_K_M；无训练；seed=20260920。',
        '抽样协议：'+manifest['protocol']['sampling'],
        '所有方法使用相同图像与题目。OmniJev 调用现有 core.decide；direct 使用相同提示词和 4-token 上限，但不请求 logprobs。',
        'reasoning 使用相同提示词，reasoning_effort=medium，temperature=0.6、top_p=0.95，总输出上限 20480 tokens。实测 Bionic 约在 8192 个思考 token 后可插入强制回答提示；这不是无限预算或完整 NVIDIA vLLM 配置。JSON 使用现有受约束输出实现，上限 32 tokens。',
        '主正确率允许从最终输出末行明确解析选项；严格正确率要求完全遵守返回格式。原始记录的 correct 保持严格口径，未改写。',
        '', '| 方法 | 题数 | 答案正确率 | 严格正确率 | P50 秒 | P95 秒 | 平均生成 tokens | 平均总 tokens | 严格无效 / 截断 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m,d in summary['methods'].items():
        lines.append(f'| {m} | {d["n"]} | {d["accuracy"]:.2f}% | {d["strict_accuracy"]:.2f}% | {d["latency_p50"]:.3f} | {d["latency_p95"]:.3f} | {d["completion_tokens_mean"]:.1f} | {d["total_tokens_mean"]:.1f} | {d["invalid"]} / {d["truncated"]} |')
    lines += ['', '## 配对准确率差：OmniJev − 基线', '', '| 基线 | 配对题数 | 差值百分点 | 保守 95% 区间 | 非劣检验 |', '|---|---:|---:|---|---|']
    for m,d in summary['comparisons'].items():
        lo,hi=d['conservative_95_ci_pp'] or d['cluster_bootstrap_95_ci_pp']
        lines.append(f'| {m} | {d["n"]} | {d["accuracy_difference_pp"]:.2f} | [{lo:.2f}, {hi:.2f}] | '+('满足预设 2pp 非劣界限' if d['noninferior_at_2pp'] else '未证实 2pp 非劣')+' |')
    lines += ['', '## 各类别正确题数', '', '| 类别 | OmniJev | Direct | JSON | Reasoning |', '|---|---:|---:|---:|---:|']
    for category in sorted(set(c['category'] for c in manifest['cases'])):
        cells=[]
        for m in METHODS:
            d=summary['methods'].get(m,{}).get('categories',{}).get(category,{'correct':0,'n':0})
            cells.append(f'{d["correct"]}/{d["n"]}')
        lines.append('| '+category+' | '+' | '.join(cells)+' |')
    lines += ['', '## 解释范围', '',
        '- 这是公开数据的固定先导子集，不是官方全量榜单成绩。',
        '- 准确率分母包含所有请求；无法明确解析、超时和无最终答案的截断均不会被剔除。严格格式不合规与答案错误分开报告。',
        '- 完成耗时从客户端开始编码媒体到解析回答；包含 HTTP，排除模型加载；不是 TTFT。',
        '- 服务自然缓存开启，请求全局随机排序。没有清空缓存，因此不能把结果称作冷启动延迟。',
        '- completion_tokens 包含服务报告的思考 token；不得再把 reasoning_tokens 相加。',
        '- token 统计采用后端口径；不能据此断言视觉编码计算量或能耗按相同比例下降。',
        '- summary.json 的 usage_coverage 记录用量报告覆盖数。接口错误未报告的 token 成本未知，不会虚构为零。',
        '- reasoning_budget_forced 单独统计后端插入强制回答提示的次数；它与 finish_reason=length 的截断不同，即使 finish_reason=stop 也可能已触发内部思考预算。',
        '- 图像选择题和因果视频回放均不证明音视频联合能力、持续流式执行或闭环任务完成率。',
        '- 非劣界限预设为 2 个百分点；bootstrap 结果为先导分析，不能把无显著差异等同于等效。',
        '- 主区间对配对 win/loss 概率采用 Bonferroni + Clopper-Pearson 保守界，避免零差异时 bootstrap 区间退化为零；仅用于独立图像。分层抽样推断仅面向该均衡类别混合。',
        '- 推理组采用推荐温度 0.6、单种子单次采样；没有重复采样来估计解码随机性的影响。',
        '- 模型可能接触过公开数据；这里主要比较同一骨干的推理策略，不声称排除预训练污染。',
        '- 原始逐题记录、原始响应、用量、哈希与抽样清单都保存在本目录。',
        '', '数据来源：'+manifest['source'],
        '复现：python3 scripts/public_benchmark.py --out '+args.out+'；汇总：python3 scripts/report_public_benchmark.py --out '+args.out, '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
