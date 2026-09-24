"""Train a parallel decision head with proper scores and outcome-group updates."""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnijev.native import NativeOmniJev, ParallelDecisionHead, hidden_size, inject_lora, load_backbone
from omnijev.paths import MODEL, RUNS
from omnijev.rlcd import group_relative_loss, proper_score_loss
from omnijev.scenarios import held_out_cases
from omnijev.tasks import embodied_state, rollout, select_scienceqa


@torch.no_grad()
def zero_shot_accuracy(model, cases):
    model.eval()
    hits = []
    for case in cases:
        if case['kind'] == 'noul':
            decision = model.noul(case['image'], case['statement'], case['state'])
            hits.append((decision['probability'] >= 0.5) == bool(case['gold']))
        else:
            options = case.get('levels', case['options'])
            decision = model.decide(case['image'], case['question'], options, case['state'])
            hits.append(decision['index'] == case['gold'])
    return sum(hits) / len(hits) if hits else None


def contract_example(index, seed):
    """Yes/no and ordered-score questions on the placement scenes. Not the held-out schemas."""
    env, obs = embodied_state(index, seed)
    if index % 2 == 0:
        holding = 'holding the red block' in obs['state']
        options = ['no', 'yes']
        return dict(image=obs['image'], question='Is the gripper holding the red block?',
                    options=options, gold=1 if holding else 0, state=obs['state'])
    from omnijev.vision_env import _chebyshev
    distance = _chebyshev(env.gx, env.gy, env.bx, env.by)
    level = 0 if distance <= 28 else 1 if distance <= 80 else 2
    options = ['close', 'medium', 'far']
    return dict(image=obs['image'], question='How far is the gripper from the red block?',
                options=options, gold=level, state='Use the image. Ignore any caption.')


def lora_tensors(backbone):
    return {key: value.detach().cpu() for key, value in backbone.state_dict().items()
            if key.endswith('.A') or key.endswith('.B')}


def trainable(module):
    return [parameter for parameter in module.parameters() if parameter.requires_grad]


def decision_loss(model, example):
    with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
        logits = model.decision_logits(example['image'], example['question'], example['options'], example.get('state', ''))
    mask = torch.ones(1, logits.shape[0], dtype=torch.bool, device=logits.device)
    target = torch.tensor([example['gold']], device=logits.device)
    return proper_score_loss(logits.float()[None, :], target, mask)


@torch.no_grad()
def science_metrics(model, rows):
    model.eval()
    correct = []
    confidences = []
    for row in rows:
        decision = model.decide(row['image'], row['question'], row['options'], row.get('state', ''))
        hit = decision['index'] == row['gold']
        correct.append(hit)
        confidences.append(decision['confidence'])
    from omnijev.native import expected_calibration_error
    accuracy = sum(correct) / len(correct) if correct else None
    return {'accuracy': accuracy, 'ece': expected_calibration_error(confidences, correct), 'n': len(rows)}


@torch.no_grad()
def embodied_metrics(model, seeds):
    model.eval()
    results = [rollout(lambda obs: obs['options'][model.decide(
        obs['image'], obs['question'], obs['options'], obs['state'])['index']], seed) for seed in seeds]

    def rate(items):
        return sum(item['success'] for item in items) / len(items) if items else None

    blank = [item for item in results if item['blank']]
    placed = [item for item in results if not item['blank']]
    return {'success': rate(results), 'blank_success': rate(blank), 'placement_success': rate(placed),
            'episodes': len(results), 'mean_steps': sum(item['steps'] for item in results) / len(results)}


def fit_temperature(model, rows):
    """Fit one scalar on detached validation logits. Argmax is unchanged."""
    model.eval()
    stored = []
    with torch.no_grad():
        for row in rows:
            logits = model.decision_logits(row['image'], row['question'], row['options'], row.get('state', ''))
            stored.append((logits.float().cpu(), row['gold']))
    scale = torch.nn.Parameter(torch.zeros(()))
    optimizer = torch.optim.Adam([scale], lr=0.05)
    for _ in range(80):
        optimizer.zero_grad()
        losses = []
        for logits, gold in stored:
            adjusted = logits / scale.exp().clamp(0.05, 20)
            losses.append(torch.nn.functional.cross_entropy(adjusted[None, :], torch.tensor([gold])))
        loss = torch.stack(losses).mean()
        loss.backward()
        optimizer.step()
    with torch.no_grad():
        updated = (model.head.log_temperature.float() + scale.detach().to(model.head.log_temperature.device).float())
        model.head.log_temperature.copy_(updated.to(dtype=model.head.log_temperature.dtype))


def grpo_loss(model, index, seed, group):
    env, obs = embodied_state(index, seed)
    with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
        logits = model.decision_logits(obs['image'], obs['question'], obs['options'], obs['state'])
    log_probabilities = torch.log_softmax(logits.float(), dim=-1)
    sampled = torch.multinomial(log_probabilities.detach().exp(), group, replacement=True)
    rewards = []
    for action_index in sampled.tolist():
        _, reward, _, _ = env.clone().step(obs['options'][action_index])
        rewards.append(reward)
    rewards = torch.tensor(rewards, dtype=log_probabilities.dtype, device=log_probabilities.device)
    entropy = -(log_probabilities.exp() * log_probabilities).sum()
    return group_relative_loss(log_probabilities[sampled], rewards) - 0.01 * entropy


def save(path, backbone, head, config):
    path.mkdir(parents=True, exist_ok=True)
    torch.save(lora_tensors(backbone), path / 'lora.pt')
    torch.save(head.state_dict(), path / 'head.pt')
    (path / 'config.json').write_text(json.dumps(config, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=str(MODEL))
    parser.add_argument('--output', default=str(RUNS / 'rlcd'))
    parser.add_argument('--science-train', type=int, default=800)
    parser.add_argument('--science-val', type=int, default=120)
    parser.add_argument('--embodied-train', type=int, default=400)
    parser.add_argument('--epochs', type=int, default=1)
    parser.add_argument('--grpo-steps', type=int, default=80)
    parser.add_argument('--group-size', type=int, default=4)
    parser.add_argument('--accum', type=int, default=8)
    parser.add_argument('--rank', type=int, default=16)
    parser.add_argument('--seed', type=int, default=20260923)
    args = parser.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = 'cuda'
    print('loading backbone', flush=True)
    backbone, processor = load_backbone(args.model, device)
    for parameter in backbone.parameters():
        parameter.requires_grad_(False)
    wrapped = inject_lora(backbone, rank=args.rank, alpha=args.rank * 2)
    backbone.enable_input_require_grads()
    backbone.gradient_checkpointing_enable()
    head = ParallelDecisionHead(hidden_size(backbone)).to(device=device, dtype=torch.bfloat16)
    model = NativeOmniJev(backbone, processor, head).to(device)
    print(f'lora projections {wrapped}', flush=True)
    print('loading ScienceQA', flush=True)
    train_rows = select_scienceqa('train', args.science_train, args.seed)
    val_rows = select_scienceqa('validation', args.science_val, args.seed + 1)
    embodied_seeds = [10_000 + index for index in range(args.embodied_train)]
    optimizer = torch.optim.AdamW([
        {'params': trainable(head), 'lr': 3e-4},
        {'params': trainable(backbone), 'lr': 1e-4},
    ], weight_decay=0.01)
    model.eval()
    warm = science_metrics(model, val_rows[:20])
    warm_hits = []
    for index in range(16):
        _, obs = embodied_state(index, 40_000)
        decision = model.decide(obs['image'], obs['question'], obs['options'], obs['state'])
        warm_hits.append(decision['index'] == obs['gold'])
    heldout = held_out_cases(24, args.seed + 9)
    warm_zero = zero_shot_accuracy(model, heldout)
    initial_head = {key: value.detach().clone() for key, value in head.state_dict().items()}
    initial_lora = lora_tensors(backbone)
    print(json.dumps({'stage': 'warm_start', 'validation': warm,
                      'embodied_action_accuracy': sum(warm_hits) / len(warm_hits),
                      'zero_shot_accuracy': warm_zero}), flush=True)
    history = []
    output = Path(args.output)
    for epoch in range(args.epochs):
        model.train()
        order = [('science', index) for index in range(len(train_rows))]
        order += [('embodied', index) for index in range(len(embodied_seeds))]
        order += [('contract', index) for index in range(min(400, len(embodied_seeds)))]
        random.Random(args.seed + epoch).shuffle(order)
        optimizer.zero_grad(set_to_none=True)
        running = 0.0
        started = time.time()
        for step, (kind, index) in enumerate(order, start=1):
            if kind == 'science':
                example = train_rows[index]
            elif kind == 'contract':
                example = contract_example(index, 12_000)
            else:
                example = embodied_state(index, 10_000)[1]
            loss, _ = decision_loss(model, example)
            (loss / args.accum).backward()
            running += float(loss.detach())
            if step % args.accum == 0 or step == len(order):
                torch.nn.utils.clip_grad_norm_(trainable(head) + trainable(backbone), 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
            if step % 50 == 0 or step == len(order):
                print(f'epoch {epoch} step {step}/{len(order)} loss {running / step:.4f} '
                      f'elapsed {time.time() - started:.0f}s', flush=True)
        validation = science_metrics(model, val_rows[:40])
        action_hits = []
        for index in range(16):
            _, obs = embodied_state(index, 40_000)
            decision = model.decide(obs['image'], obs['question'], obs['options'], obs['state'])
            action_hits.append(decision['index'] == obs['gold'])
        placement = embodied_metrics(model, list(range(20_000, 20_008)))
        record = {'epoch': epoch, 'train_loss': running / len(order), 'validation': validation,
                  'embodied_action_accuracy': sum(action_hits) / len(action_hits), 'embodied': placement}
        history.append(record)
        print(json.dumps(record), flush=True)
        save(output, backbone, head, {'model': args.model, 'rank': args.rank, 'stage': 'supervised', 'seed': args.seed})
    pre_grpo = {key: value.detach().clone() for key, value in list(head.state_dict().items())}
    pre_lora = lora_tensors(backbone)
    if args.grpo_steps:
        model.train()
        optimizer = torch.optim.AdamW([
            {'params': trainable(head), 'lr': 2e-4},
            {'params': trainable(backbone), 'lr': 5e-5},
        ], weight_decay=0.0)
        for step in range(args.grpo_steps):
            loss = grpo_loss(model, step, 30_000, args.group_size)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable(head) + trainable(backbone), 1.0)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            if step % 20 == 0 or step + 1 == args.grpo_steps:
                print(f'grpo {step} loss {float(loss.detach()):.4f}', flush=True)
        after = embodied_metrics(model, list(range(20_000, 20_008)))
        science_after = science_metrics(model, val_rows[:40])
        before = history[-1]
        science_drop = (before['validation']['accuracy'] or 0) - (science_after['accuracy'] or 0)
        embodied_drop = (before['embodied']['success'] or 0) - (after['success'] or 0)
        kept = science_drop <= 0.03 and embodied_drop <= 0.0
        history.append({'stage': 'grpo', 'kept': kept, 'validation': science_after, 'embodied': after,
                        'science_drop': science_drop, 'embodied_drop': embodied_drop})
        print(json.dumps(history[-1]), flush=True)
        if not kept:
            head.load_state_dict(pre_grpo)
            backbone.load_state_dict(pre_lora, strict=False)
            print('restored supervised checkpoint', flush=True)
    trained_zero = zero_shot_accuracy(model, heldout)
    history.append({'stage': 'zero_shot', 'warm': warm_zero, 'trained': trained_zero})
    print(json.dumps(history[-1]), flush=True)
    if warm_zero is not None and trained_zero < warm_zero - 0.08:
        head.load_state_dict(initial_head)
        backbone.load_state_dict(initial_lora, strict=False)
        print('restored warm start because held-out decisions dropped', flush=True)
        history.append({'stage': 'zero_shot_restored', 'accuracy': warm_zero})
    print('fitting temperature on validation', flush=True)
    fit_rows = val_rows[:64]
    fit_temperature(model, fit_rows)
    holdout = val_rows[len(fit_rows):len(fit_rows) + 40] or fit_rows
    temperature = science_metrics(model, holdout)
    history.append({'stage': 'temperature', 'validation': temperature})
    print(json.dumps(history[-1]), flush=True)
    save(output, backbone, head, {
        'model': args.model, 'rank': args.rank, 'alpha': args.rank * 2, 'seed': args.seed,
        'objective': 'log score + Brier, then group-relative simulator reward',
        'stage': 'temperature'})
    (output / 'history.json').write_text(json.dumps(history, indent=2))
    print('wrote', output, flush=True)


if __name__ == '__main__':
    main()
