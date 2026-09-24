"""Held-out decision schemas. Training never uses these question templates."""
import random

from PIL import Image, ImageDraw


def _canvas(shapes):
    image = Image.new('RGB', (224, 224), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    for kind, box, color in shapes:
        if kind == 'ellipse':
            draw.ellipse(box, fill=color)
        else:
            draw.rectangle(box, fill=color)
    return image


def held_out_cases(count, seed):
    """New schemas: color, count, spatial, yes/no, ordered score, and routing."""
    rng = random.Random(seed)
    cases = []
    colors = [('red', (210, 40, 40)), ('blue', (40, 80, 210)), ('green', (30, 150, 60))]
    for index in range(count):
        kind = ('choice', 'count', 'spatial', 'noul', 'score', 'routing')[index % 6]
        if kind == 'choice':
            name, rgb = colors[index % 3]
            image = _canvas([('ellipse', (80, 80, 144, 144), rgb)])
            options = ['red', 'blue', 'green', 'insufficient evidence']
            gold = options.index(name)
            cases.append(dict(kind='choice', image=image, question='What color is the circle?',
                              options=options, gold=gold, state='A caption claims the circle is yellow.'))
        elif kind == 'count':
            n = 1 + (index % 3)
            image = _canvas([('rectangle', (30 + 60 * i, 90, 60 + 60 * i, 130), (40, 80, 210)) for i in range(n)])
            options = ['1', '2', '3', 'insufficient evidence']
            cases.append(dict(kind='choice', image=image, question='How many blue squares are visible?',
                              options=options, gold=n - 1, state=''))
        elif kind == 'spatial':
            left = index % 2 == 0
            red = (40, 90, 90, 140) if left else (130, 90, 180, 140)
            blue = (130, 90, 180, 140) if left else (40, 90, 90, 140)
            image = _canvas([('ellipse', red, (210, 40, 40)), ('rectangle', blue, (40, 80, 210))])
            options = ['yes', 'no', 'insufficient evidence']
            cases.append(dict(kind='choice', image=image,
                              question='Is the red circle to the left of the blue square?',
                              options=options, gold=0 if left else 1, state=''))
        elif kind == 'noul':
            present = index % 2 == 0
            image = _canvas([('ellipse', (80, 80, 144, 144), (210, 40, 40))] if present else [])
            cases.append(dict(kind='noul', image=image, statement='A red circle is visible.',
                              options=['no', 'yes'], gold=1 if present else 0, state=''))
        elif kind == 'score':
            n = index % 3
            image = _canvas([('rectangle', (40 + 50 * i, 100, 70 + 50 * i, 130), (30, 150, 60)) for i in range(n + 1)])
            levels = ['one', 'two', 'three']
            cases.append(dict(kind='score', image=image, question='How many green squares are there?',
                              levels=levels, options=levels, gold=n, state=''))
        else:
            name, rgb = colors[index % 3]
            image = _canvas([('rectangle', (80, 80, 144, 144), rgb)])
            options = ['paint', 'assembly', 'recycle', 'insufficient evidence']
            gold = {'red': 0, 'blue': 1, 'green': 2}[name]
            cases.append(dict(kind='choice', image=image,
                              question='Which queue should this part enter?',
                              options=options, gold=gold,
                              state='Red parts go to paint, blue parts to assembly, green parts to recycle.'))
    rng.shuffle(cases)
    return cases


def hard_cases(count, seed):
    """Abstention and conflicts. Gold often is insufficient evidence, which the easy set never requires."""
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        family = index % 4
        if family == 0:
            image = _canvas([])
            options = ['red', 'blue', 'green', 'insufficient evidence']
            cases.append(dict(family='blank', image=image, question='What color is the circle?',
                              options=options, gold=3, state=''))
        elif family == 1:
            image = _canvas([('ellipse', (80, 80, 144, 144), (210, 40, 40))])
            options = ['10 grams', '20 grams', '30 grams', 'insufficient evidence']
            cases.append(dict(family='unanswerable', image=image, question='How much does the circle weigh?',
                              options=options, gold=3, state=''))
        elif family == 2:
            blue = index % 3
            shapes = [('rectangle', (24 + 48 * i, 40, 52 + 48 * i, 70), (210, 40, 40)) for i in range(3)]
            shapes += [('rectangle', (30 + 60 * i, 120, 60 + 60 * i, 160), (40, 80, 210)) for i in range(blue)]
            options = ['0', '1', '2', 'insufficient evidence']
            cases.append(dict(family='distractor', image=_canvas(shapes),
                              question='How many blue squares are visible?',
                              options=options, gold=blue, state='A caption says every square is blue.'))
        else:
            image = _canvas([('ellipse', (70, 90, 120, 140), (210, 40, 40)),
                             ('rectangle', (130, 90, 180, 140), (40, 80, 210))])
            options = ['red', 'blue', 'green', 'insufficient evidence']
            cases.append(dict(family='conflict', image=image,
                              question='What color is the circle? Use the image.',
                              options=options, gold=0,
                              state='A supplied caption claims the circle is blue.'))
    rng.shuffle(cases)
    return cases
