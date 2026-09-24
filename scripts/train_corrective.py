"""Retrain on mistakes. Extra weight and a lead penalty when the top option is wrong.

AI2D items reserved for the suite stay out. MMStar, MMMU, RealWorldQA and ScienceQA test stay out.
"""
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import BASE_MODEL_ID, CHECKPOINT, MODEL, V3
from omnijev.rlcd import corrective_loss
from omnijev.tasks import select_scienceqa
from scripts.benchmark_public import image_of
from scripts.benchmark_suite import ai2d_cases, case_image, suite
from scripts.experiment_effective import load_native
from scripts.train_native_rlcd import lora_tensors, trainable


def main():
    output = CHECKPOINT
    model, backbone, head = load_native(str(MODEL), V3)
    dataset, held, _ = ai2d_cases(160, 20260924)
    held_ids = {row['index'] for row in held}
    _, all_rows, stats = ai2d_cases(0, 20260924)
    train_rows = [row for row in all_rows if row['index'] not in held_ids]
    random.Random(20260926).shuffle(train_rows)
    val_rows = train_rows[:64]
    train_rows = train_rows[64:]
    science = select_scienceqa('train', 400, 20260926)
    print(json.dumps({'ai2d_train': len(train_rows), 'held_out_ai2d': len(held_ids),
                      'science': len(science), 'parsed': stats['parsed']}), flush=True)
    order = [('ai2d', i) for i in range(len(train_rows))] + [('science', i) for i in range(len(science))]
    random.Random(20260927).shuffle(order)
    optimizer = torch.optim.AdamW([
        {'params': trainable(head), 'lr': 5e-5},
        {'params': trainable(backbone), 'lr': 1e-5},
    ], weight_decay=0.0)
    model.train()
    running = 0.0
    started = time.time()
    optimizer.zero_grad(set_to_none=True)
    for step, (kind, index) in enumerate(order, start=1):
        if kind == 'ai2d':
            row = train_rows[index]
            example = dict(image=image_of({'AI2D': dataset}, row), question=row['question'],
                           options=row['options'], state=row['state'], gold=ord(row['gold']) - 65)
        else:
            row = science[index]
            example = dict(image=row['image'], question=row['question'], options=row['options'],
                           state=row.get('state', ''), gold=row['gold'])
        with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
            logits = model.decision_logits(example['image'], example['question'], example['options'], example['state'])
        mask = torch.ones(1, logits.shape[0], dtype=torch.bool, device=logits.device)
        loss, parts = corrective_loss(logits.float()[None, :], torch.tensor([example['gold']], device=logits.device), mask)
        (loss / 4).backward()
        running += float(loss.detach())
        if step % 4 == 0 or step == len(order):
            torch.nn.utils.clip_grad_norm_(trainable(head) + trainable(backbone), 1.0)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
        if step % 100 == 0 or step == len(order):
            print(f'step {step}/{len(order)} loss {running / step:.4f} wrong {parts["wrong_rate"]:.3f} '
                  f'elapsed {time.time() - started:.0f}s', flush=True)
    model.eval()

    def accuracy(rows, loader):
        hits = 0
        for row in rows:
            image = loader(row)
            decision = model.decide(image, row['question'], row['options'], row.get('state', ''))
            hits += decision['choice'] == row['gold']
        return hits / len(rows)

    ai2d_val = accuracy(val_rows, lambda row: image_of({'AI2D': dataset}, row))
    print(json.dumps({'ai2d_val_not_in_suite': ai2d_val, 'n': len(val_rows)}), flush=True)
    datasets, cases = {}, []
    for name, builder in suite(40, 20260924).items():
        data, rows, _ = builder()
        if name == 'MMMU':
            datasets['MMMU'] = data
        elif data is not None:
            datasets[name] = data
        cases.extend(rows)
    by = {}
    for case in cases:
        decision = model.decide(case_image(datasets, case), case['question'], case['options'], case.get('state', ''))
        by.setdefault(case['benchmark'], []).append(decision['choice'] == case['gold'])
    summary = {name: sum(flags) / len(flags) for name, flags in by.items()}
    summary['n'] = sum(len(flags) for flags in by.values())
    summary['all'] = sum(sum(flags) for flags in by.values()) / summary['n']
    print(json.dumps(summary), flush=True)
    output.mkdir(parents=True, exist_ok=True)
    torch.save(lora_tensors(backbone), output / 'lora.pt')
    torch.save(head.state_dict(), output / 'head.pt')
    (output / 'config.json').write_text(json.dumps({
        'model': BASE_MODEL_ID,
        'rank': 16, 'alpha': 32, 'stage': 'corrective-lead',
        'held_out': 'suite indices for MMStar, MMMU, RealWorldQA, ScienceQA test, and 160 AI2D',
    }))
    (output / 'suite.json').write_text(json.dumps(summary, indent=2))
    print('wrote', output, flush=True)


if __name__ == '__main__':
    main()
