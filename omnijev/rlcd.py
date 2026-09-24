"""Training objectives for calibrated finite-choice decisions.

The published RLCD target is a probability that matches realized outcomes.
Proper scores (log score and Brier) train that distribution directly when the
outcome is observed. Group-relative policy gradients use the same distribution
when the reward arrives from a simulator step rather than a class index.
"""
import torch
import torch.nn.functional as F


def masked_logits(logits, cand_mask):
    fill = torch.finfo(logits.dtype).min
    return logits.masked_fill(~cand_mask, fill)


def proper_score_loss(logits, target, cand_mask, brier_weight=0.5):
    """Log score plus Brier score. Both are proper scores of the outcome."""
    if logits.ndim != 2:
        raise ValueError('logits must be [batch, candidates]')
    safe = masked_logits(logits, cand_mask)
    if not torch.all(cand_mask[torch.arange(target.shape[0], device=target.device), target]):
        raise ValueError('target points at a masked candidate')
    log_loss = F.cross_entropy(safe, target)
    probabilities = torch.softmax(safe, dim=-1)
    one_hot = torch.zeros_like(probabilities).scatter_(1, target[:, None], 1.0)
    brier = ((probabilities - one_hot).square() * cand_mask.to(probabilities.dtype)).sum(dim=-1).mean()
    return log_loss + brier_weight * brier, {
        'log_loss': float(log_loss.detach()),
        'brier': float(brier.detach()),
    }


def corrective_loss(logits, target, cand_mask, brier_weight=0.5):
    """Proper score, with extra weight and a lead penalty when the top option is wrong.

    The lead penalty is the gap between the highest probability and the true option.
    It is zero when the true option already leads, so correct peaked answers are left alone.
    """
    safe = masked_logits(logits, cand_mask)
    log_each = F.cross_entropy(safe, target, reduction='none')
    probabilities = torch.softmax(safe, dim=-1)
    one_hot = torch.zeros_like(probabilities).scatter_(1, target[:, None], 1.0)
    brier = ((probabilities - one_hot).square() * cand_mask.to(probabilities.dtype)).sum(dim=-1)
    true_probability = probabilities.gather(1, target[:, None]).squeeze(1)
    lead = probabilities.max(dim=-1).values - true_probability
    with torch.no_grad():
        wrong = safe.argmax(dim=-1).ne(target).to(log_each.dtype)
    loss = ((1.0 + 2.0 * wrong) * log_each + brier_weight * brier + lead).mean()
    return loss, {
        'log_loss': float(log_each.mean().detach()),
        'brier': float(brier.mean().detach()),
        'lead': float(lead.mean().detach()),
        'wrong_rate': float(wrong.mean().detach()),
    }


def group_relative_loss(log_probabilities, rewards):
    """One-state group baseline. Advantages are detached from the reward."""
    if log_probabilities.shape != rewards.shape or log_probabilities.ndim != 1:
        raise ValueError('log_probabilities and rewards must share shape [group]')
    centered = rewards - rewards.mean()
    scale = rewards.std(unbiased=False)
    advantages = centered / (scale + 1e-6) if float(scale) > 1e-6 else centered
    return -(advantages.detach() * log_probabilities).mean()
