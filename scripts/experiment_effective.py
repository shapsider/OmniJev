"""Measure abstention, conflicts, and unseen control, then continue RLCD from a checkpoint."""
import argparse
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnijev.native import NativeOmniJev, ParallelDecisionHead, expected_calibration_error, hidden_size, inject_lora, load_backbone
from omnijev.paths import BASE_MODEL_ID, MODEL, RUNS, V2
from omnijev.rlcd import proper_score_loss
from omnijev.scenarios import hard_cases, held_out_cases
from omnijev.tasks import embodied_state, rollout, select_scienceqa
from scripts.train_native_rlcd import contract_example, lora_tensors, trainable


def load_native(model_path, checkpoint, device='cuda'):
    config = json.loads((checkpoint / 'config.json').read_text())
    backbone, processor = load_backbone(model_path, device)
    for parameter in backbone.parameters():
        parameter.requires_grad_(False)
    inject_lora(backbone, rank=config['rank'], alpha=config.get('alpha', config['rank'] * 2))
    backbone.load_state_dict(torch.load(checkpoint / 'lora.pt', map_location=device), strict=False)
    head = ParallelDecisionHead(hidden_size(backbone)).to(device=device, dtype=torch.bfloat16)
    head.load_state_dict(torch.load(checkpoint / 'head.pt', map_location=device))
    model = NativeOmniJev(backbone, processor, head).to(device)
    model.eval()
    return model, backbone, head


@torch.no_grad()
def score_cases(model, cases):
    hits, confidences, correct = [], [], []
    by_family = {}
    for case in cases:
        state = case.get('state', '')
        if case.get('kind') == 'noul':
            decision = model.noul(case['image'], case['statement'], state)
            hit = (decision['probability'] >= 0.5) == bool(case['gold'])
        else:
            options = case.get('levels', case['options'])
            decision = model.decide(case['image'], case['question'], options, state)
            hit = decision['index'] == case['gold']
        hits.append(hit)
        confidences.append(decision['confidence'])
        correct.append(hit)
        family = case.get('family', case.get('kind', 'all'))
        by_family.setdefault(family, []).append(hit)
    return {
        'accuracy': sum(hits) / len(hits),
        'ece': expected_calibration_error(confidences, correct),
        'by_family': {key: sum(value) / len(value) for key, value in by_family.items()},
        'n': len(cases),
    }


@torch.no_grad()
def score_control(model, seeds):
    results = [rollout(lambda obs: obs['options'][model.decide(
        obs['image'], obs['question'], obs['options'], obs['state'])['index']], seed) for seed in seeds]
    placed = [item for item in results if not item['blank']]
    return {
        'success': sum(item['success'] for item in results) / len(results),
        'placement_success': sum(item['success'] for item in placed) / len(placed) if placed else None,
        'n': len(results),
    }


def evaluate(model):
    report = {
        'easy': score_cases(model, held_out_cases(24, 20260923 + 9)),
        'hard': score_cases(model, hard_cases(40, 77)),
        'science': score_cases(model, select_scienceqa('test', 40, 20260923 + 2)),
        'control': score_control(model, list(range(50_000, 50_016))),
    }
    print(json.dumps(report), flush=True)
    return report


def continue_training(model, backbone, head, steps, output):
    """Second stage: abstention and conflicts, small step size, plus more control states."""
    device = next(head.parameters()).device
    optimizer = torch.optim.AdamW([
        {'params': trainable(head), 'lr': 1e-4},
        {'params': trainable(backbone), 'lr': 2e-5},
    ], weight_decay=0.0)
    hard = hard_cases(80, 11)
    model.train()
    running = 0.0
    for step in range(steps):
        if step % 5 == 0:
            example = hard[step % len(hard)]
        else:
            env, obs = embodied_state(step, 16_000)
            if not env.blank and not env.done:
                wrong = [action for action in obs['options'] if action != obs['oracle']]
                obs, _, _, _ = env.step(wrong[step % len(wrong)])
            example = obs
        with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
            logits = model.decision_logits(example['image'], example['question'], example['options'], example.get('state', ''))
        mask = torch.ones(1, logits.shape[0], dtype=torch.bool, device=device)
        target = torch.tensor([example['gold']], device=device)
        loss, _ = proper_score_loss(logits.float()[None, :], target, mask)
        loss.backward()
        if (step + 1) % 4 == 0:
            torch.nn.utils.clip_grad_norm_(trainable(head) + trainable(backbone), 1.0)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
        running += float(loss.detach())
        if step % 20 == 0 or step + 1 == steps:
            print(f'stage2 {step} loss {running / (step + 1):.4f}', flush=True)
    output.mkdir(parents=True, exist_ok=True)
    torch.save(lora_tensors(backbone), output / 'lora.pt')
    torch.save(head.state_dict(), output / 'head.pt')
    (output / 'config.json').write_text(json.dumps({
        'model': BASE_MODEL_ID,
        'rank': 16, 'alpha': 32, 'stage': 'abstention-conflict'}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=str(MODEL))
    parser.add_argument('--checkpoint', default=str(RUNS / 'qwen35-rlcd'))
    parser.add_argument('--output', default=str(V2))
    parser.add_argument('--steps', type=int, default=0)
    args = parser.parse_args()
    model, backbone, head = load_native(args.model, Path(args.checkpoint))
    print('before', flush=True)
    before = evaluate(model)
    if args.steps:
        continue_training(model, backbone, head, args.steps, Path(args.output))
        model.eval()
        print('after', flush=True)
        after = evaluate(model)
        Path(args.output).joinpath('compare.json').write_text(json.dumps({'before': before, 'after': after}, indent=2))


if __name__ == '__main__':
    main()
