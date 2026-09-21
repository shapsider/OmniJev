"""Reusable decision API. Stable action IDs are independent of token labels."""
from dataclasses import dataclass
from typing import Optional
import math
import time
from .core import decide


@dataclass(frozen=True)
class Policy:
    """Optional uncalibrated gates. Not a statistical risk guarantee."""
    min_margin: Optional[float] = None
    min_candidate_mass: Optional[float] = None
    max_latency_ms: Optional[float] = None

    def __post_init__(self):
        for value in (self.min_margin, self.min_candidate_mass):
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError('Score gates must be finite values between 0 and 1.')
        if self.max_latency_ms is not None and (not math.isfinite(self.max_latency_ms) or self.max_latency_ms <= 0):
            raise ValueError('max_latency_ms must be positive and finite.')


class OmniJev:
    def __init__(self, model='omnijev-nemotron', base_url='http://127.0.0.1:1234', timeout=60):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def decide(self, question, options, *, images=(), state='', request_id=None,
               policy=None, mode='letter'):
        """options: [{id, description, abstain?}]. Returns a decision, never executes it."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError('question is required')
        if not isinstance(state, str):
            raise ValueError('state must be text')
        if not isinstance(options, list) or not 2 <= len(options) <= 26:
            raise ValueError('Provide 2–26 options.')
        ids, descriptions, abstentions = [], [], set()
        for option in options:
            if not isinstance(option, dict):
                raise ValueError('Each option must have id and description.')
            id, description = option.get('id'), option.get('description')
            if not isinstance(id, str) or not id.strip() or not isinstance(description, str) or not description.strip():
                raise ValueError('Option id and description must be nonempty text.')
            if not isinstance(option.get('abstain',False), bool):
                raise ValueError('abstain must be boolean')
            ids.append(id); descriptions.append(description)
            if option.get('abstain'):abstentions.add(id)
        if len(set(ids)) != len(ids) or len(set(descriptions)) != len(descriptions):
            raise ValueError('Option IDs and descriptions must be distinct.')
        if isinstance(images, str):
            raise ValueError('images must be a sequence, not a string')
        policy = policy or Policy()
        started = time.perf_counter()
        case = dict(id=request_id, question=question, options=descriptions, images=list(images), state=state)
        raw = decide(case, self.model, self.base_url, mode, timeout=self.timeout)
        elapsed_ms = (time.perf_counter()-started)*1000
        selected = ids[ord(raw['choice'])-65] if raw['valid'] else None
        scores = raw['scores']
        probabilities = scores.get('probabilities')
        mapped = {ids[ord(k)-65]:v for k,v in probabilities.items()} if probabilities else None
        status, reason = 'decided', 'model_choice'
        if not raw['valid']:
            status,reason='invalid','invalid_model_output'
        elif selected in abstentions:
            status,reason='abstained','model_selected_abstention'
        elif policy.min_margin is not None or policy.min_candidate_mass is not None:
            if probabilities is None:
                status,reason='abstained','scores_unavailable'
            elif policy.min_margin is not None and scores['margin'] < policy.min_margin:
                status,reason='abstained','low_margin'
            elif policy.min_candidate_mass is not None and scores['candidate_mass'] < policy.min_candidate_mass:
                status,reason='abstained','low_candidate_mass'
        if policy.max_latency_ms is not None and elapsed_ms > policy.max_latency_ms:
            status,reason='stale','latency_budget_exceeded'
        return dict(request_id=request_id, status=status, reason=reason,
                    action=selected if status=='decided' else None, selected=selected,
                    scores=mapped, score_status=scores['status'], calibrated=False,
                    margin=scores.get('margin'), candidate_mass=scores.get('candidate_mass'),
                    elapsed_ms=elapsed_ms, model=self.model, mode=mode,
                    usage=raw.get('usage'), raw_text=raw['raw_text'])

    def decide_many(self, requests):
        """Sequential independent decisions; does not claim shared-prefill execution."""
        return [self.decide(**request) for request in requests]
