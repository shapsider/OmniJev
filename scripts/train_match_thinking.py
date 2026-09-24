"""Continue RLCD on mainstream multiple-choice gold so the decision matches reasoned answers.

MMStar is held out. The MMBench items already used in the public sample are held out too.
"""
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnijev.paths import BASE_MODEL_ID, MODEL, V2, V3
from omnijev.rlcd import proper_score_loss
from omnijev.tasks import select_scienceqa
from scripts.benchmark_public import mmbench_cases
from scripts.experiment_effective import load_native
from scripts.train_native_rlcd import lora_tensors, trainable


def examples():
    manifest = json.loads((ROOT / 'results/qwen35-public/manifest.json').read_text())
    held = {row['index'] for row in manifest if row['benchmark'] == 'MMBench'}
    _, rows, stats = mmbench_cases(0, 20260924)
    train = [row for row in rows if row['index'] not in held]
    for row in train:
        row['gold_index'] = ord(row['gold']) - 65
    science = select_scienceqa('train', 600, 20260925)
    for row in science:
        row['benchmark'] = 'ScienceQA'
        row['gold_index'] = row['gold']
    print(json.dumps({'mmbench_train': len(train), 'held_out_mmbench': len(held),
                      'science': len(science), 'mmbench_parsed': stats['parsed']}), flush=True)
    return train, science


def main():
    output = V3
    model, backbone, head = load_native(str(MODEL), V2)
    public, science = examples()
    # Images for MMBench are loaded lazily inside the training loop via the dataset
    # already consumed by mmbench_cases. Re-read rows carry no image; attach below.
    from datasets import load_dataset
    dataset = load_dataset('lmms-lab/MMBench', 'en', split='dev')
    order = [('bench', index) for index in range(len(public))]
    order += [('science', index) for index in range(len(science))]
    random.Random(20260925).shuffle(order)
    optimizer = torch.optim.AdamW([
        {'params': trainable(head), 'lr': 1e-4},
        {'params': trainable(backbone), 'lr': 2e-5},
    ], weight_decay=0.0)
    model.train()
    running = 0.0
    started = time.time()
    optimizer.zero_grad(set_to_none=True)
    for step, (kind, index) in enumerate(order, start=1):
        if kind == 'bench':
            row = public[index]
            image = dataset[row['index']]['image']
            if image.mode != 'RGB':
                image = image.convert('RGB')
            example = dict(image=image.copy(), question=row['question'], options=row['options'],
                           state=row['state'], gold=row['gold_index'])
        else:
            example = science[index]
            example = dict(example, gold=example['gold_index'])
        with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
            logits = model.decision_logits(example['image'], example['question'], example['options'], example.get('state', ''))
        mask = torch.ones(1, logits.shape[0], dtype=torch.bool, device=logits.device)
        target = torch.tensor([example['gold']], device=logits.device)
        loss, _ = proper_score_loss(logits.float()[None, :], target, mask)
        (loss / 4).backward()
        running += float(loss.detach())
        if step % 4 == 0 or step == len(order):
            torch.nn.utils.clip_grad_norm_(trainable(head) + trainable(backbone), 1.0)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
        if step % 50 == 0 or step == len(order):
            print(f'step {step}/{len(order)} loss {running / step:.4f} elapsed {time.time() - started:.0f}s', flush=True)
    output.mkdir(parents=True, exist_ok=True)
    torch.save(lora_tensors(backbone), output / 'lora.pt')
    torch.save(head.state_dict(), output / 'head.pt')
    (output / 'config.json').write_text(json.dumps({
        'model': BASE_MODEL_ID,
        'rank': 16, 'alpha': 32, 'stage': 'mmbench-science-gold',
        'held_out': 'MMStar and the public MMBench sample'}))
    print('wrote', output, flush=True)


if __name__ == '__main__':
    main()
