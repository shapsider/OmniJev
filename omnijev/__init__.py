"""Finite-choice decisions. The client adapts a frozen model.
Native RLCD training is imported from omnijev.native and does not load with the client."""
from .client import OmniJev, Policy

__all__ = ['OmniJev', 'Policy']
__version__ = '0.3.0'
