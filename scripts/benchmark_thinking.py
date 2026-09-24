"""Deep-thinking baseline. enable_thinking and a long token budget, not an 8-token answer."""
import argparse
import json
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.native import NativeOmniJev, load_backbone, parse_letter
from omnijev.paths import MODEL
from scripts.benchmark_public import image_of, mmstar_cases, record, take_stratified

THINK = (
    'Think through the image and the candidates. '
    'After the reasoning, the last line must be exactly "Answer: X".'
)


@torch.no_grad()
def think(backbone, processor, image, question, options, state, max_new_tokens):
    holder = NativeOmniJev(backbone, processor, head=None)
    encoded = holder.encode_prompt(image, question, options, state, suffix=THINK, thinking=True)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    started = time.perf_counter()
    output = backbone.generate(**encoded, max_new_tokens=max_new_tokens, do_sample=False)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    new_tokens = output.shape[-1] - encoded['input_ids'].shape[-1]
    text = processor.tokenizer.decode(output[0, encoded['input_ids'].shape[-1]:], skip_special_tokens=False)
    visible = text.split('</think>')[-1]
    letter = parse_letter(visible, len(options))
    return {
        'choice': letter, 'valid': letter is not None, 'text': visible[-400:],
        'confidence': None, 'new_tokens': int(new_tokens), 'latency_seconds': elapsed,
        'truncated': int(new_tokens) >= max_new_tokens and letter is None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=str(MODEL))
    parser.add_argument('--output', default='results/qwen35-thinking')
    parser.add_argument('--per-category', type=int, default=20)
    parser.add_argument('--seed', type=int, default=20260924)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--max-new-tokens', type=int, default=3072)
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    dataset, rows, stats = mmstar_cases(args.per_category, args.seed)
    rows = [row for index, row in enumerate(rows) if index % args.shards == args.shard]
    print(json.dumps({'shard': args.shard, 'n': len(rows), **stats}), flush=True)
    backbone, processor = load_backbone(args.model, 'cuda')
    backbone.eval()
    path = output / f'shard-{args.shard}.jsonl'
    done = set()
    if path.exists():
        done = {json.loads(line)['index'] for line in path.read_text().splitlines() if line.strip()}
    datasets = {'MMStar': dataset}
    for offset, case in enumerate(rows):
        if case['index'] in done:
            continue
        decision = think(
            backbone, processor, image_of(datasets, case), case['question'], case['options'],
            case['state'], args.max_new_tokens)
        row = record(case, 'thinking', decision)
        row['truncated'] = decision['truncated']
        with path.open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(f'shard {args.shard} {offset + 1}/{len(rows)} correct {row["correct"]} tokens {row["new_tokens"]} '
              f'{row["latency_seconds"]:.1f}s', flush=True)


if __name__ == '__main__':
    main()
