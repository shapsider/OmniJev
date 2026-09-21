"""Frozen-model strategies shared by the real MuJoCo workbench and evaluation.

Candidate scores are incomplete top-k readouts, never calibrated success odds.
No provider falls back to the rule controller on failure.
"""
import base64
import hashlib
import json
import os
import re
import time

from . import core

PROVIDERS = ('omnijev', 'omni_direct', 'omni_reasoning', 'omni_adaptive')
NAMES = ('OmniJev · Fast decision', 'Direct · Direct short answer', 'Reasoning · Budgeted reasoning', 'Adaptive · Experimental on-demand reasoning')


def connection():
    base = os.getenv('OMNIJEV_BASE_URL', 'http://127.0.0.1:1234').rstrip('/')
    if base.endswith('/v1'):base = base[:-3]
    return {'url': base + '/v1/chat/completions', 'model': os.getenv('OMNIJEV_MODEL', 'omnijev-nemotron'), 'key': ''}


def final_choice(text, labels):
    lines = [x.strip().replace('**', '').replace('`', '') for x in (text or '').splitlines() if x.strip()]
    if not lines:return None
    match = re.fullmatch(r'(?:(?:Final answer|Answer|Option)\s*[:=]?\s*)?\(?([A-Z])\)?[.]?', lines[-1], re.I)
    return match[1].upper() if match and match[1].upper() in labels else None


def choose(policy, state, spec, started, images=None):
    ids = list(spec['criteria'])
    case = {'question': spec['instructions'],
            'state': json.dumps(state, ensure_ascii=False, separators=(',', ':')),
            'options': [f'{key}: {spec["criteria"][key]}' for key in ids],
            'images': ['data:image/png;base64,' + base64.b64encode(x['rgb']).decode('ascii') for x in (images or [])]}
    if images:case['state'] += '\nCamera images, in order: ' + ', '.join(x['view'] for x in images)
    labels = [chr(65 + i) for i in range(len(ids))]
    # The incremental action vocabulary has 21 choices; do not fabricate a
    # complete distribution from a backend that returns only top-10 tokens.
    message = core.messages(case, 'letter')
    prompt_hash = hashlib.sha256(json.dumps(message, sort_keys=True).encode()).hexdigest()
    if not hasattr(policy, 'omni_records'):policy.omni_records = []

    def invoke(reasoning=False, logprobs=False):
        payload = {'model': policy.connection['model'], 'messages': message, 'seed': 20260919,
                   'temperature': .6 if reasoning else 0,
                   'reasoning_effort': 'medium' if reasoning else 'none',
                   'max_tokens': int(os.getenv('OMNIJEV_REASONING_TOKENS', '4096')) if reasoning else 4}
        if reasoning:payload['top_p'] = .95
        if logprobs:payload.update(logprobs=True, top_logprobs=10)
        record = {'route': 'reasoning' if reasoning else 'fast', 'provider': policy.provider,
                  'messages_sha256': prompt_hash, 'action_ids': ids, 'image_count': len(images or []),
                  'request_config': {k:v for k,v in payload.items() if k != 'messages'}}
        tick = time.perf_counter()
        try:
            response = policy._post(policy.connection['url'], json=payload,
                                    timeout=float(os.getenv('OMNIJEV_REQUEST_TIMEOUT', '180')),
                                    follow_redirects=False)
            response.raise_for_status()
            body = response.json()
            policy._response_metadata(body, input_key='prompt_tokens', output_key='completion_tokens')
            item = body['choices'][0]
            raw = item['message'].get('content') or ''
            selected = final_choice(raw, labels)
            thought = item['message'].get('reasoning_content') or ''
            scores = core.candidate_scores(item.get('logprobs'), labels) if logprobs else {'status':'not_requested','probabilities':None}
            record.update(usage=body.get('usage'), response_model=body.get('model'), final_text=raw,
                          finish_reason=item.get('finish_reason'), reasoning_detected=bool(thought),
                          selected_letter=selected, scores=scores,
                          usage_complete=all(isinstance((body.get('usage') or {}).get(k), int)
                                             for k in ('prompt_tokens','completion_tokens','total_tokens')))
            if not selected or item.get('finish_reason') != 'stop' or (not reasoning and thought):
                raise ValueError('Invalid, truncated or unexpectedly reasoning decision; no rule fallback')
            record['status'] = 'ok'
            return selected, scores
        except Exception as exc:
            record.update(status='error', error_type=type(exc).__name__)
            raise
        finally:
            record['latency_ms'] = (time.perf_counter() - tick) * 1000
            policy.latencies.append(record['latency_ms'])
            policy.omni_records.append(record)
            if os.getenv('OMNIJEV_REQUEST_LOG'):
                with open(os.environ['OMNIJEV_REQUEST_LOG'], 'a') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')

    reasoning = policy.provider == 'omni_reasoning'
    selected, scores = invoke(reasoning, policy.provider in ('omnijev','omni_adaptive'))
    route = 'reasoning' if reasoning else 'fast'
    if policy.provider == 'omni_adaptive' and (scores.get('margin', 0) < float(os.getenv('OMNIJEV_MARGIN', '.2'))):
        policy.calls += 1
        selected, scores = invoke(True, False)
        route = 'fast_then_reasoning'
    probabilities = {ids[labels.index(k)]:v for k,v in (scores.get('probabilities') or {}).items()}
    chosen = ids[labels.index(selected)]
    return {'choice': chosen, 'probabilities': probabilities,
            'selected_probability': probabilities.get(chosen), 'provider_confidence': None,
            'latency_ms': (time.perf_counter()-started)*1000, 'model_call': True,
            'provider': policy.provider, 'model': policy.model, 'route': route,
            'readout': 'candidate_token_softmax' if probabilities else 'generated_label',
            'score_status': scores['status'], 'calibrated': False,
            'request_tokens': (policy.omni_records[-1].get('usage') or {}),
            'messages_sha256': prompt_hash}
