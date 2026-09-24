"""Compare native RLCD OmniJev with the same VLM used as a text decoder."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnijev.paths import MODEL, RUNS
from omnijev.native import (
    LETTER_SUFFIX, NativeOmniJev, ParallelDecisionHead, expected_calibration_error, hidden_size,
    inject_lora, load_backbone, parse_letter)
from omnijev.tasks import rollout, select_scienceqa
from omnijev.vision_env import VisualTableEnv


DIRECT = LETTER_SUFFIX
REASON = "Reason from the visible evidence. End with a line 'Answer: X' where X is the candidate letter."


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


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
    text = processor.tokenizer.decode(output.sequences[0, encoded['input_ids'].shape[-1]:], skip_special_tokens=True)
    letter = parse_letter(text, len(options))
    probabilities = None
    if mode == 'direct' and output.scores:
        probabilities = letter_distribution(processor.tokenizer, output.scores[0][0], len(options))
    confidence = None if not probabilities or letter not in probabilities else probabilities[letter]
    return {
        'choice': letter, 'valid': letter is not None, 'text': text,
        'probabilities': probabilities, 'confidence': confidence,
        'new_tokens': int(new_tokens), 'latency_seconds': elapsed,
    }


def summarize(rows, task):
    attempted = len(rows)
    # Unparseable text is a wrong decision. It stays in the denominator.
    correct_flags = [bool(row.get('valid') and row.get('correct')) for row in rows]
    scored = [(row['confidence'], bool(row['correct'])) for row in rows
              if row.get('valid') and row.get('confidence') is not None]
    latencies = [row['latency_seconds'] for row in rows]
    return {
        'task': task,
        'n': attempted,
        'accuracy': (sum(correct_flags) / attempted) if attempted else None,
        'valid_rate': (sum(bool(row.get('valid')) for row in rows) / attempted) if attempted else None,
        'ece': expected_calibration_error([item[0] for item in scored], [item[1] for item in scored]),
        'latency_p50': percentile(latencies, 0.50),
        'latency_p95': percentile(latencies, 0.95),
        'mean_new_tokens': statistics.fmean(row['new_tokens'] for row in rows) if rows else None,
    }


def science_rows(method, rows, predict):
    records = []
    for row in rows:
        decision = predict(row['image'], row['question'], row['options'], row.get('state', ''))
        decision['correct'] = decision.get('choice') == chr(65 + row['gold'])
        decision['id'] = row['question'][:80]
        records.append(decision)
    return records


def embodied_rows(predict, seeds):
    records = []
    for seed in seeds:
        env = VisualTableEnv()
        obs = env.reset(seed)
        steps = []
        started = time.perf_counter()
        info = {'success': False, 'reason': 'not_started'}
        while not env.done and len(steps) < 24:
            decision = predict(obs['image'], obs['question'], obs['options'], obs['state'])
            if not decision['valid']:
                action = obs['options'][0]
            else:
                action = obs['options'][ord(decision['choice']) - 65]
            steps.append(decision)
            obs, _, done, info = env.step(action)
            if done:
                break
        elapsed = time.perf_counter() - started
        records.append({
            'seed': seed, 'blank': env.blank, 'success': bool(info.get('success')),
            'reason': info.get('reason'), 'steps': len(steps), 'latency_seconds': elapsed,
            'new_tokens': sum(step['new_tokens'] for step in steps),
            'valid': all(step['valid'] for step in steps) if steps else False,
        })
    return records


def embodied_summary(rows, task):
    def rate(items):
        return sum(item['success'] for item in items) / len(items) if items else None
    blank = [row for row in rows if row['blank']]
    placed = [row for row in rows if not row['blank']]
    latencies = [row['latency_seconds'] / max(1, row['steps']) for row in rows]
    return {
        'task': task, 'n': len(rows), 'success': rate(rows), 'blank_success': rate(blank),
        'placement_success': rate(placed), 'valid_rate': sum(row['valid'] for row in rows) / len(rows),
        'latency_p50_per_decision': percentile(latencies, 0.50),
        'mean_new_tokens_per_episode': statistics.fmean(row['new_tokens'] for row in rows),
        'mean_steps': statistics.fmean(row['steps'] for row in rows),
    }


def write_report(path, science, embodied, notes):
    def pct(value):
        return '—' if value is None else f'{100 * value:.1f}%'

    def num(value, digits=2):
        return '—' if value is None else f'{value:.{digits}f}'

    def ece(summary):
        measured = summary.get('ece') or {}
        return '—' if measured.get('ece') is None else f'{measured["ece"]:.3f}'

    lines = [
        '# 多模态 OmniJev 与同一视觉语言模型的比较',
        '',
        '比较方式对齐 Jev 对通用语言模型的公开对照：同一道有限选择决策，一侧是一次前向的结构化概率，另一侧是把视觉语言模型约束成文本解码器。',
        '这里的视觉语言模型是 Qwen3.5-9B。OmniJev 在它上面做 RLCD；直接短答最多生成 8 个 token，预算推理最多生成 128 个 token。两条文本路径都使用未训练的同一主干。',
        '训练目标是已公开的 RLCD 方向：决策分布用对数分数和 Brier 分数对准观测结果，闭环控制再用组内相对优势更新。这不是 TypeSafe 未公开的采样器或数据集。',
        '',
        '## ScienceQA 图像题（官方 test，未参与训练）',
        '',
        '| 方法 | 题数 | 准确率 | ECE | 合法输出 | 延迟 P50 秒 | 延迟 P95 秒 | 平均生成 token |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    names = {'omnijev': 'OmniJev RLCD', 'direct': '直接短答', 'reasoning': '预算推理'}
    for key in ('omnijev', 'direct', 'reasoning'):
        row = science[key]
        lines.append(
            f"| {names[key]} | {row['n']} | {pct(row['accuracy'])} | {ece(row)} | {pct(row['valid_rate'])} | "
            f"{num(row['latency_p50'], 3)} | {num(row['latency_p95'], 3)} | {num(row['mean_new_tokens'], 1)} |")
    base = science['reasoning']['latency_p50']
    fast = science['omnijev']['latency_p50']
    if base and fast:
        lines += ['', f"ScienceQA 上，OmniJev 相对预算推理的中位延迟比是 {base / fast:.2f} 倍。生成 token 从推理解码变为 0。"]
    lines += [
        '',
        '## 闭环视觉放置（保留种子，未参与训练）',
        '',
        '画面里有红色方块、绿色目标和夹爪。模型看不到坐标。空白帧的正确行为是弃权。放置成功指方块被放到目标里并松开。',
        '',
        '| 方法 | 回合 | 总成功率 | 放置成功率 | 空白帧弃权 | 每步延迟 P50 秒 | 每回合平均生成 token | 平均步数 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for key in ('omnijev', 'direct', 'reasoning'):
        row = embodied[key]
        lines.append(
            f"| {names[key]} | {row['n']} | {pct(row['success'])} | {pct(row['placement_success'])} | "
            f"{pct(row['blank_success'])} | {num(row['latency_p50_per_decision'], 3)} | "
            f"{num(row['mean_new_tokens_per_episode'], 1)} | {num(row['mean_steps'], 1)} |")
    lines += ['', '## 训练之后保留的改动', '']
    lines.extend(f'- {note}' for note in notes)
    lines += [
        '',
        '## 读数边界',
        '',
        '- 准确率的分母是全部请求。解析不出候选字母算错，不会从分母里去掉。',
        '- ECE 只统计给出了置信度的合法输出。直接短答的置信度来自首个生成步上候选字母的归一化对数概率。预算推理不报告置信度。',
        '- 温度是在 ScienceQA 验证集上拟合的标量，测试集没有参与拟合，也不改变 argmax。',
        '- 这组数字描述这次固定划分和这个 3B 主干，不能外推成对 Jev 或更大全模态模型的复现。',
        '',
    ]
    path.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=str(MODEL))
    parser.add_argument('--checkpoint', default=str(RUNS / 'rlcd'))
    parser.add_argument('--output', default='results/native-rlcd')
    parser.add_argument('--science', type=int, default=120)
    parser.add_argument('--episodes', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20260923)
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = Path(args.checkpoint)
    config = json.loads((checkpoint / 'config.json').read_text())
    print('loading backbone', flush=True)
    backbone, processor = load_backbone(args.model, 'cuda')
    backbone.eval()
    science = select_scienceqa('test', args.science, args.seed + 2)
    embodied_seeds = list(range(50_000, 50_000 + args.episodes))
    print(f'science {len(science)} episodes {len(embodied_seeds)}', flush=True)

    def direct(image, question, options, state):
        return generate_decision(backbone, processor, image, question, options, state, 'direct')

    def reasoning(image, question, options, state):
        return generate_decision(backbone, processor, image, question, options, state, 'reasoning')

    science_direct = science_rows('direct', science, direct)
    print('direct science done', flush=True)
    science_reason = science_rows('reasoning', science, reasoning)
    print('reasoning science done', flush=True)
    embodied_direct = embodied_rows(direct, embodied_seeds)
    print('direct embodied done', flush=True)
    embodied_reason = embodied_rows(reasoning, embodied_seeds)
    print('reasoning embodied done', flush=True)

    inject_lora(backbone, rank=config['rank'], alpha=config.get('alpha', config['rank'] * 2))
    backbone.load_state_dict(torch.load(checkpoint / 'lora.pt', map_location='cuda'), strict=False)
    head = ParallelDecisionHead(hidden_size(backbone)).to(device='cuda', dtype=torch.bfloat16)
    head.load_state_dict(torch.load(checkpoint / 'head.pt', map_location='cuda'))
    model = NativeOmniJev(backbone, processor, head)
    model.eval()

    def native(image, question, options, state):
        return model.decide(image, question, options, state)

    science_native = science_rows('omnijev', science, native)
    print('native science done', flush=True)
    embodied_native = embodied_rows(native, embodied_seeds)
    print('native embodied done', flush=True)
    # One held-out frame so the report has the observation the policy saw.
    sample = VisualTableEnv()
    sample_obs = sample.reset(50_000, blank=False, lie=False)
    sample_obs['image'].save(output / 'embodied-observation.png')

    science_summary = {
        'omnijev': summarize(science_native, 'scienceqa'),
        'direct': summarize(science_direct, 'scienceqa'),
        'reasoning': summarize(science_reason, 'scienceqa'),
    }
    embodied_summary_map = {
        'omnijev': embodied_summary(embodied_native, 'embodied'),
        'direct': embodied_summary(embodied_direct, 'embodied'),
        'reasoning': embodied_summary(embodied_reason, 'embodied'),
    }
    history_path = checkpoint / 'history.json'
    notes = ['监督阶段最小化对数分数和 Brier 分数。']
    if history_path.exists():
        history = json.loads(history_path.read_text())
        for event in history:
            if event.get('stage') == 'grpo':
                notes.append('组相对结果更新已保留。' if event.get('kept') else
                             '组相对结果更新降低了验证成功率或 ScienceQA 准确率，已退回监督权重。')
            if event.get('stage') == 'temperature':
                notes.append('在验证集上拟合了决策温度，测试集未参与。')
    payload = {'scienceqa': science_summary, 'embodied': embodied_summary_map, 'config': config, 'notes': notes}
    (output / 'summary.json').write_text(json.dumps(payload, indent=2))
    (output / 'scienceqa.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in science_native + science_direct + science_reason))
    write_report(output / 'REPORT.md', science_summary, embodied_summary_map, notes)
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == '__main__':
    main()
