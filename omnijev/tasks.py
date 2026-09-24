"""Shared multimodal tasks for native RLCD training and comparison."""
import io
import random

from PIL import Image

from omnijev.vision_env import MAX_STEPS, VisualTableEnv


def as_image(value):
    if value is None:
        return None
    if isinstance(value, Image.Image):
        return value.convert('RGB')
    if isinstance(value, dict) and value.get('bytes'):
        return Image.open(io.BytesIO(value['bytes'])).convert('RGB')
    if isinstance(value, dict) and value.get('path'):
        return Image.open(value['path']).convert('RGB')
    return None


def shuffle_options(question, options, gold, seed):
    order = list(range(len(options)))
    material = '\n'.join([str(seed), question, *options])
    random.Random(material).shuffle(order)
    shuffled = [options[index] for index in order]
    return shuffled, order.index(gold)


def select_scienceqa(split, limit, seed):
    from datasets import load_dataset
    dataset = load_dataset('derek-thomas/ScienceQA', split=split)
    rows = []
    for row in dataset:
        image = as_image(row.get('image'))
        if image is not None:
            image.load()
            image = image.copy()
        choices = [str(choice) for choice in (row.get('choices') or [])]
        answer = row.get('answer')
        if image is None or not 2 <= len(choices) <= 8 or len(set(choices)) != len(choices):
            continue
        try:
            answer = int(answer)
        except (TypeError, ValueError):
            continue
        if not 0 <= answer < len(choices):
            continue
        hint = row.get('hint') or ''
        rows.append({
            'image': image,
            'question': str(row['question']),
            'options': choices,
            'state': str(hint),
            'gold_text': choices[answer],
            'source': 'scienceqa',
            'split': split,
        })
    random.Random(seed).shuffle(rows)
    selected = rows[:limit]
    prepared = []
    for row in selected:
        options, gold = shuffle_options(row['question'], row['options'], row['options'].index(row['gold_text']), seed)
        prepared.append({**row, 'options': options, 'gold': gold})
    return prepared


def embodied_state(index, seed):
    """A non-terminal state along an oracle trajectory. Physics match the returned menu."""
    env = VisualTableEnv()
    obs = env.reset(seed + index)
    for _ in range(index % 6):
        if env.done:
            break
        action = obs['oracle']
        _, _, finished, _ = env.clone().step(action)
        if finished:
            break
        obs, _, _, _ = env.step(action)
    obs['source'] = 'embodied'
    return env, obs


def rollout(policy, seed):
    env = VisualTableEnv()
    obs = env.reset(seed)
    blank = obs['blank']
    steps = 0
    info = {'success': False, 'reason': 'not_started'}
    while not env.done and steps < MAX_STEPS:
        action = policy(obs)
        obs, _, done, info = env.step(action)
        steps += 1
        if done:
            break
    return {'success': bool(info.get('success')), 'steps': steps, 'blank': blank, 'reason': info.get('reason')}
