"""Public multimodal multiple-choice evaluation for native RLCD OmniJev.

Compares the decision head with the same frozen VLM used as a short-answer
decoder. Unparseable letters count as wrong. These sets are not training data.
"""
import argparse
import json
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnijev.paths import MODEL, V2
from omnijev.native import (  # noqa: E402
    LETTER_SUFFIX, NativeOmniJev, ParallelDecisionHead, expected_calibration_error,
    hidden_size, inject_lora, load_backbone, parse_letter)

DIRECT = LETTER_SUFFIX
REASON = "Reason from the visible evidence. End with a line 'Answer: X' where X is the candidate letter."
PAREN_SPLIT = re.compile(r'\(([A-H])\)\s*')
COLON_SPLIT = re.compile(r'(?<![A-Za-z0-9])([A-H]):\s+')
DOT_SPLIT = re.compile(r'(?:^|\n)\s*([A-H])\.\s+')
ANSWER_INSTRUCTION = re.compile(r'(?is)\s*please answer directly.*$')


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def clean_option(text):
    text = ANSWER_INSTRUCTION.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip(' \n,;')
    return text


def pieces_from(text, pattern):
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return None
    letters, options = [], []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        letter = match.group(1)
        option = clean_option(text[match.end():end])
        if option.lower() == 'nan':
            break
        if not option or letter in letters:
            return None
        letters.append(letter)
        options.append(option)
    if letters != [chr(65 + i) for i in range(len(letters))]:
        return None
    if not 2 <= len(options) <= 8 or len(set(options)) != len(options):
        return None
    stem = text[:matches[0].start()].strip()
    stem = re.sub(r'(?:Options|Choices)\s*:?\s*$', '', stem, flags=re.I).strip()
    return stem, options


def split_prompt(text):
    """Return question, options, and a hint that belongs in the state."""
    hint = ''
    body = text.strip()
    hint_match = re.match(r'(?is)hint\s*:\s*(.*?)\n\s*question\s*:\s*(.*)', body)
    if hint_match:
        hint = hint_match.group(1).strip()
        body = hint_match.group(2).strip()
    question_match = re.match(r'(?is)question\s*:\s*(.*)', body)
    if question_match:
        body = question_match.group(1).strip()
    if re.fullmatch(r'(?is)please answer the question.*', hint):
        hint = ''
    parsed = pieces_from(body, PAREN_SPLIT) or pieces_from(body, COLON_SPLIT) or pieces_from(body, DOT_SPLIT)
    if parsed is None:
        return None, [], hint
    question, options = parsed
    return question, options, hint


def normalize_gold(answer, count):
    text = str(answer).strip().upper()
    marked = re.findall(r'[A-H]', text)
    if len(text) == 1 and text in {chr(65 + i) for i in range(count)}:
        return text
    if marked and marked[0] in {chr(65 + i) for i in range(count)} and len(text) <= 3:
        return marked[0]
    return None


def take_stratified(rows, per_category, seed):
    if per_category <= 0:
        return rows
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['category']].append(row)
    chosen = []
    for category in sorted(grouped):
        bucket = grouped[category]
        rng = random.Random(f'{seed}:{category}')
        rng.shuffle(bucket)
        chosen.extend(bucket[:per_category])
    return chosen


def mmstar_cases(per_category, seed):
    from datasets import load_dataset
    dataset = load_dataset('Lin-Chen/MMStar', split='val')
    rows = []
    skipped = 0
    for index, row in enumerate(dataset):
        question, options, hint = split_prompt(row['question'])
        gold = normalize_gold(row['answer'], len(options))
        if not question or gold is None:
            skipped += 1
            continue
        rows.append({
            'benchmark': 'MMStar',
            'index': index,
            'category': row['category'],
            'question': question,
            'options': options,
            'gold': gold,
            'state': hint,
            'source': 'mmstar',
        })
    selected = take_stratified(rows, per_category, seed)
    return dataset, selected, {'parsed': len(rows), 'skipped': skipped, 'selected': len(selected)}


def present_choices(row):
    options = []
    for letter in 'ABCD':
        value = row.get(letter)
        if value is None or str(value).strip().lower() in {'', 'nan', 'none'}:
            break
        options.append(clean_option(str(value)))
    return options


def mmbench_cases(per_category, seed):
    from datasets import load_dataset
    dataset = load_dataset('lmms-lab/MMBench', 'en', split='dev')
    rows = []
    skipped = 0
    for index, row in enumerate(dataset):
        options = present_choices(row)
        gold = normalize_gold(row['answer'], len(options))
        question = clean_option(str(row['question']))
        if not question or not (2 <= len(options) <= 8) or gold is None or len(set(options)) != len(options):
            skipped += 1
            continue
        hint = row.get('hint')
        state = '' if hint is None or str(hint).strip().lower() in {'', 'nan', 'none'} else str(hint).strip()
        rows.append({
            'benchmark': 'MMBench',
            'index': index,
            'category': str(row.get('category') or 'unknown'),
            'question': question,
            'options': options,
            'gold': gold,
            'state': state,
            'source': str(row.get('source') or ''),
        })
    selected = take_stratified(rows, per_category, seed)
    return dataset, selected, {'parsed': len(rows), 'skipped': skipped, 'selected': len(selected)}


def realworldqa_cases(per_category, seed):
    from datasets import load_dataset
    dataset = load_dataset('xai-org/RealWorldQA', split='test')
    rows = []
    skipped = 0
    for index, row in enumerate(dataset):
        question, options, hint = split_prompt(row['question'])
        gold = normalize_gold(row['answer'], len(options))
        answer = str(row['answer']).strip().lower()
        if not options and answer in {'yes', 'no'}:
            question = ANSWER_INSTRUCTION.sub('', str(row['question'])).strip()
            options = ['no', 'yes']
            gold = 'B' if answer == 'yes' else 'A'
            hint = ''
        if not question or gold is None:
            skipped += 1
            continue
        rows.append({
            'benchmark': 'RealWorldQA',
            'index': index,
            'category': 'real-world',
            'question': question,
            'options': options,
            'gold': gold,
            'state': hint,
            'source': 'realworldqa',
        })
    selected = take_stratified(rows, per_category, seed)
    return dataset, selected, {'parsed': len(rows), 'skipped': skipped, 'selected': len(selected)}


LOADERS = {
    'mmstar': mmstar_cases,
    'mmbench': mmbench_cases,
    'realworldqa': realworldqa_cases,
}


def image_of(datasets, case):
    image = datasets[case['benchmark']][case['index']]['image']
    if image.mode != 'RGB':
        image = image.convert('RGB')
    return image.copy()


def letter_distribution(tokenizer, scores, count):
    labels = [chr(65 + i) for i in range(count)]
    ids = []
    for label in labels:
        pieces = tokenizer.encode(label, add_special_tokens=False)
        if len(pieces) != 1:
            return None
        ids.append(pieces[0])
    selected = scores.float()[ids]
    probabilities = torch.softmax(selected, dim=-1).tolist()
    return {label: value for label, value in zip(labels, probabilities)}


@torch.no_grad()
def generate_decision(backbone, processor, image, question, options, state, mode):
    holder = NativeOmniJev(backbone, processor, head=None)
    suffix = DIRECT if mode == 'direct' else REASON
    encoded = holder.encode_prompt(image, question, options, state, suffix=suffix)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    started = time.perf_counter()
    output = backbone.generate(
        **encoded, max_new_tokens=8 if mode == 'direct' else 128, do_sample=False,
        return_dict_in_generate=True, output_scores=True)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    new_tokens = output.sequences.shape[-1] - encoded['input_ids'].shape[-1]
    text = processor.tokenizer.decode(
        output.sequences[0, encoded['input_ids'].shape[-1]:], skip_special_tokens=True)
    letter = parse_letter(text, len(options))
    probabilities = None
    if mode == 'direct' and output.scores:
        probabilities = letter_distribution(processor.tokenizer, output.scores[0][0], len(options))
    confidence = None if not probabilities or letter not in probabilities else probabilities[letter]
    return {
        'choice': letter, 'valid': letter is not None, 'text': text[:240],
        'confidence': confidence, 'new_tokens': int(new_tokens), 'latency_seconds': elapsed,
    }


def record(case, method, decision):
    return {
        'benchmark': case['benchmark'],
        'index': case['index'],
        'category': case['category'],
        'source': case['source'],
        'method': method,
        'gold': case['gold'],
        'choice': decision.get('choice'),
        'valid': bool(decision.get('valid')),
        'correct': bool(decision.get('valid') and decision.get('choice') == case['gold']),
        'confidence': decision.get('confidence'),
        'new_tokens': decision.get('new_tokens', 0),
        'latency_seconds': decision.get('latency_seconds'),
    }


def summarize(rows):
    attempted = len(rows)
    correct_flags = [bool(row['correct']) for row in rows]
    scored = [(row['confidence'], bool(row['correct'])) for row in rows
              if row.get('valid') and row.get('confidence') is not None]
    calibration = expected_calibration_error([item[0] for item in scored], [item[1] for item in scored])
    if isinstance(calibration, dict):
        calibration = calibration['ece']
    latencies = [row['latency_seconds'] for row in rows if row.get('latency_seconds') is not None]
    by_category = {}
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['category']].append(bool(row['correct']))
    for category, flags in sorted(grouped.items()):
        by_category[category] = {'n': len(flags), 'accuracy': sum(flags) / len(flags)}
    return {
        'n': attempted,
        'accuracy': (sum(correct_flags) / attempted) if attempted else None,
        'valid_rate': (sum(bool(row.get('valid')) for row in rows) / attempted) if attempted else None,
        'ece': calibration,
        'latency_p50': percentile(latencies, 0.50),
        'latency_p95': percentile(latencies, 0.95),
        'mean_new_tokens': statistics.fmean(row['new_tokens'] for row in rows) if rows else None,
        'by_category': by_category,
    }


def pct(value):
    return '—' if value is None else f'{100 * value:.1f}%'


def num(value, digits):
    return '—' if value is None else f'{value:.{digits}f}'


def write_report(path, coverage, summaries, notes):
    lines = [
        '# 主流多模态决策评测',
        '',
        '主干是 Qwen3.5-9B。OmniJev 使用第二次 RLCD 权重（弃权与冲突恢复阶段），一次前向在候选字母上给出选择和置信度，不生成答案 token。',
        '对照是同一冻结主干的直接短答（最多 8 个 token）和预算推理（最多 128 个 token）。推理只在 MMStar 的分层子集上运行。',
        '这不是英伟达 Omni，也不是 TypeSafe Jev 的未公开采样器。',
        '',
        '## 数据',
        '',
        '| 基准 | 解析成功 | 解析跳过 | 本次评测 |',
        '|---|---:|---:|---:|',
    ]
    for name, stats in coverage.items():
        lines.append(f"| {name} | {stats['parsed']} | {stats['skipped']} | {stats['selected']} |")
    lines += [
        '',
        'MMStar 使用全部可解析题目。MMBench 英文 dev 按类别分层抽样。RealWorldQA 保留题干里的选项题，并把答案为 yes/no、题干没有选项的题收成请求时的二选一。',
        '这些公开题没有进入 RLCD 训练。MMBench 里有一批来源标记为 ScienceQA 的题，和训练分布接近，表中单独列出。',
        '',
        '## 总结果',
        '',
        '| 基准 | 方法 | 题数 | 准确率 | 合法输出 | ECE | 延迟 P50 秒 | 延迟 P95 秒 | 平均生成 token |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for benchmark, methods in summaries.items():
        for method, row in methods.items():
            lines.append(
                f"| {benchmark} | {method} | {row['n']} | {pct(row['accuracy'])} | {pct(row['valid_rate'])} | "
                f"{num(row['ece'], 3)} | {num(row['latency_p50'], 3)} | {num(row['latency_p95'], 3)} | "
                f"{num(row['mean_new_tokens'], 1)} |")
    mmstar = summaries.get('MMStar', {})
    if 'omnijev' in mmstar:
        lines += ['', '## MMStar 分类', '', '| 类别 | 题数 | OmniJev | 直接短答 |', '|---|---:|---:|---:|']
        categories = mmstar['omnijev']['by_category']
        direct = mmstar.get('direct', {}).get('by_category', {})
        for category, row in categories.items():
            other = direct.get(category, {})
            lines.append(
                f"| {category} | {row['n']} | {pct(row['accuracy'])} | {pct(other.get('accuracy'))} |")
    lines += ['', '## 读数边界', '']
    lines.extend(f'- {note}' for note in notes)
    path.write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=None)
    parser.add_argument('--checkpoint', default=None)
    parser.add_argument('--output', default='results/qwen35-public')
    parser.add_argument('--benchmarks', default='mmstar,mmbench,realworldqa')
    parser.add_argument('--per-category', type=int, default=0,
                        help='0 keeps every parsed item. Positive values sample per category.')
    parser.add_argument('--mmbench-per-category', type=int, default=40)
    parser.add_argument('--reasoning-per-category', type=int, default=12)
    parser.add_argument('--seed', type=int, default=20260924)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    if args.model is None:
        args.model = str(MODEL)
    if args.checkpoint is None:
        args.checkpoint = str(V2)
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    datasets = {}
    cases = []
    coverage = {}
    for name in args.benchmarks.split(','):
        per_category = args.per_category
        if name == 'mmbench' and args.per_category == 0:
            per_category = args.mmbench_per_category
        dataset, rows, stats = LOADERS[name](per_category, args.seed)
        if args.limit:
            rows = rows[:args.limit]
            stats = dict(stats, selected=len(rows))
        datasets[rows[0]['benchmark'] if rows else name] = dataset
        cases.extend(rows)
        coverage[rows[0]['benchmark'] if rows else name] = stats
        print(json.dumps({'benchmark': name, **stats}, ensure_ascii=False), flush=True)
    manifest = [{key: value for key, value in case.items()} for case in cases]
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False))
    (output / 'coverage.json').write_text(json.dumps(coverage, indent=2))
    if args.prepare_only:
        return

    print('loading backbone', flush=True)
    backbone, processor = load_backbone(args.model, 'cuda')
    backbone.eval()
    jsonl = output / 'decisions.jsonl'
    done = set()
    if jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                done.add((row['benchmark'], row['index'], row['method']))

    def append(row):
        with jsonl.open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')

    reasoning_ids = {
        (case['benchmark'], case['index'])
        for case in take_stratified(
            [case for case in cases if case['benchmark'] == 'MMStar'],
            args.reasoning_per_category, args.seed + 1)
    }
    for offset, case in enumerate(cases):
        image = image_of(datasets, case)
        key = (case['benchmark'], case['index'])
        if (*key, 'direct') not in done:
            decision = generate_decision(backbone, processor, image, case['question'], case['options'], case['state'], 'direct')
            append(record(case, 'direct', decision))
        if key in reasoning_ids and (*key, 'reasoning') not in done:
            decision = generate_decision(backbone, processor, image, case['question'], case['options'], case['state'], 'reasoning')
            append(record(case, 'reasoning', decision))
        if (offset + 1) % 25 == 0:
            print(f'decoder {offset + 1}/{len(cases)}', flush=True)
    print('decoder pass done', flush=True)

    checkpoint = Path(args.checkpoint)
    config = json.loads((checkpoint / 'config.json').read_text())
    inject_lora(backbone, rank=config['rank'], alpha=config.get('alpha', config['rank'] * 2))
    backbone.load_state_dict(torch.load(checkpoint / 'lora.pt', map_location='cuda'), strict=False)
    head = ParallelDecisionHead(hidden_size(backbone)).to(device='cuda', dtype=torch.bfloat16)
    head.load_state_dict(torch.load(checkpoint / 'head.pt', map_location='cuda'))
    model = NativeOmniJev(backbone, processor, head)
    model.eval()
    for offset, case in enumerate(cases):
        if (case['benchmark'], case['index'], 'omnijev') in done:
            continue
        image = image_of(datasets, case)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        decision = model.decide(image, case['question'], case['options'], case['state'])
        append(record(case, 'omnijev', decision))
        if (offset + 1) % 25 == 0:
            print(f'omnijev {offset + 1}/{len(cases)}', flush=True)
    print('omnijev pass done', flush=True)

    rows = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row['benchmark']][row['method']].append(row)
    summaries = {
        benchmark: {method: summarize(items) for method, items in methods.items()}
        for benchmark, methods in grouped.items()
    }
    mmbench_rows = [row for row in rows if row['benchmark'] == 'MMBench']
    science_source = defaultdict(list)
    other_source = defaultdict(list)
    for row in mmbench_rows:
        bucket = science_source if 'scienceqa' in row['source'].lower() else other_source
        bucket[row['method']].append(bool(row['correct']))
    source_split = {
        'scienceqa_source': {method: {'n': len(flags), 'accuracy': sum(flags) / len(flags)} for method, flags in science_source.items()},
        'other_source': {method: {'n': len(flags), 'accuracy': sum(flags) / len(flags)} for method, flags in other_source.items()},
    }
    notes = [
        '准确率的分母是全部请求。解析不出候选字母算错。',
        'ECE 只统计给出了置信度的合法输出。直接短答的置信度来自首个生成步上候选字母的归一化概率。预算推理不报告 ECE。',
        'OmniJev 的置信度来自候选字母分布，训练目标是对数分数加 Brier 分数，不是逐题校准证书。',
        'MMBench 分层抽样和推理子集使用固定种子，没有按模型结果挑选。',
        '训练只用了 ScienceQA 官方 train 的图像题和桌面放置环境。公开基准的 test/dev/val 没有参与权重更新。',
    ]
    payload = {'coverage': coverage, 'summary': summaries, 'mmbench_source_split': source_split, 'notes': notes}
    (output / 'summary.json').write_text(json.dumps(payload, indent=2))
    write_report(output / 'REPORT.md', coverage, summaries, notes)
    print(json.dumps({'coverage': coverage, 'accuracy': {
        bench: {method: row['accuracy'] for method, row in methods.items()}
        for bench, methods in summaries.items()
    }}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
