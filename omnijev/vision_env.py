"""Closed-loop visual placement task with an image observation and a finite action menu.

Geometry stays in this simulator. The model only sees a frame, a short state, and
the action menu. Labels for supervised training are the oracle action; outcome
rewards for RL do not reveal that action.
"""
from copy import deepcopy

from PIL import Image, ImageDraw

ACTIONS = (
    'move north',
    'move south',
    'move east',
    'move west',
    'grasp',
    'release',
    'insufficient evidence',
)
QUESTION = 'Which action should the gripper take next? Use the image.'
SIZE = 224
MARGIN = 40
STEP = 20
REACH = 28
MAX_STEPS = 24


def _chebyshev(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by))


class VisualTableEnv:
    def __init__(self):
        self.done = False

    def reset(self, seed, blank=None, lie=None):
        import random
        rng = random.Random(seed)
        self.rng = rng
        self.blank = rng.random() < 0.18 if blank is None else blank
        self.lie = (not self.blank) and (rng.random() < 0.30 if lie is None else lie)
        self.holding = False
        self.steps = 0
        self.done = False
        self.gx = self.gy = self.bx = self.by = self.tx = self.ty = SIZE // 2
        if not self.blank:
            for _ in range(40):
                self.gx, self.gy = rng.randrange(MARGIN, SIZE - MARGIN), rng.randrange(MARGIN, SIZE - MARGIN)
                self.bx, self.by = rng.randrange(MARGIN, SIZE - MARGIN), rng.randrange(MARGIN, SIZE - MARGIN)
                self.tx, self.ty = rng.randrange(MARGIN, SIZE - MARGIN), rng.randrange(MARGIN, SIZE - MARGIN)
                separated = _chebyshev(self.bx, self.by, self.tx, self.ty) > REACH + 8
                visible = _chebyshev(self.gx, self.gy, self.bx, self.by) > 8
                if separated and visible:
                    break
        return self.observation()

    def oracle_action(self):
        if self.blank:
            return 'insufficient evidence'
        if not self.holding:
            if _chebyshev(self.gx, self.gy, self.bx, self.by) <= REACH:
                return 'grasp'
            return self._move_toward(self.bx, self.by)
        if _chebyshev(self.bx, self.by, self.tx, self.ty) <= REACH:
            return 'release'
        return self._move_toward(self.tx, self.ty)

    def _move_toward(self, tx, ty):
        dx, dy = tx - self.gx, ty - self.gy
        if abs(dx) >= abs(dy) and dx != 0:
            return 'move east' if dx > 0 else 'move west'
        if dy != 0:
            return 'move south' if dy > 0 else 'move north'
        return 'grasp' if not self.holding else 'release'

    def _subgoal(self):
        if self.holding:
            return self.tx, self.ty
        return self.bx, self.by

    def observation(self):
        options = list(ACTIONS)
        self.rng.shuffle(options)
        oracle = self.oracle_action()
        if self.blank:
            state = 'No camera frame was captured.'
        else:
            state = 'The gripper is holding the red block.' if self.holding else 'The gripper is empty.'
            if self.lie:
                state += ' A supplied caption claims: the red block is already inside the green goal.'
        return {
            'image': self.render(),
            'question': QUESTION,
            'options': options,
            'state': state,
            'oracle': oracle,
            'gold': options.index(oracle),
            'blank': self.blank,
        }

    def render(self):
        image = Image.new('RGB', (SIZE, SIZE), (245, 245, 245) if self.blank else (248, 246, 240))
        if self.blank:
            return image
        draw = ImageDraw.Draw(image)
        draw.rectangle((self.tx - 30, self.ty - 30, self.tx + 30, self.ty + 30), fill=(186, 220, 176))
        draw.rectangle((self.bx - 12, self.by - 12, self.bx + 12, self.by + 12), fill=(210, 48, 48))
        color = (232, 148, 36) if self.holding else (36, 92, 210)
        draw.ellipse((self.gx - 11, self.gy - 11, self.gx + 11, self.gy + 11), outline=color, width=4)
        return image

    def clone(self):
        other = VisualTableEnv()
        other.__dict__ = deepcopy(self.__dict__)
        return other

    def step(self, action):
        if action not in ACTIONS:
            raise ValueError(f'unknown action {action}')
        if self.done:
            raise RuntimeError('episode already finished')
        if self.blank:
            self.done = True
            success = action == 'insufficient evidence'
            return self.observation(), (1.0 if success else -1.0), True, {
                'success': success, 'reason': 'abstain' if success else 'acted_without_image'}
        sx, sy = self._subgoal()
        previous = _chebyshev(self.gx, self.gy, sx, sy)
        reward = 0.0
        success = False
        reason = 'continue'
        if action == 'insufficient evidence':
            reward -= 0.5
        elif action == 'move north':
            self.gy = max(MARGIN, self.gy - STEP)
        elif action == 'move south':
            self.gy = min(SIZE - MARGIN, self.gy + STEP)
        elif action == 'move west':
            self.gx = max(MARGIN, self.gx - STEP)
        elif action == 'move east':
            self.gx = min(SIZE - MARGIN, self.gx + STEP)
        elif action == 'grasp':
            if not self.holding and _chebyshev(self.gx, self.gy, self.bx, self.by) <= REACH:
                self.holding = True
                self.bx, self.by = self.gx, self.gy
                reward += 0.5
            else:
                reward -= 0.2
        elif action == 'release':
            if self.holding and _chebyshev(self.bx, self.by, self.tx, self.ty) <= REACH:
                self.holding = False
                success = True
                self.done = True
                reason = 'placed'
                reward += 1.0
            elif self.holding:
                self.holding = False
                reward -= 0.4
            else:
                reward -= 0.2
        if self.holding:
            self.bx, self.by = self.gx, self.gy
        if action.startswith('move'):
            nx, ny = self._subgoal()
            reward += 0.15 * (previous - _chebyshev(self.gx, self.gy, nx, ny)) / STEP
        self.steps += 1
        if not self.done and self.steps >= MAX_STEPS:
            self.done = True
            reason = 'timeout'
        return self.observation(), reward, self.done, {'success': success, 'reason': reason}


def oracle_success(seed, blank=None, lie=None):
    env = VisualTableEnv()
    obs = env.reset(seed, blank=blank, lie=lie)
    info = {'success': False, 'reason': 'not_started'}
    for _ in range(MAX_STEPS + 1):
        if env.done:
            break
        obs, _, done, info = env.step(obs['oracle'])
        if done:
            break
    return info['success']
