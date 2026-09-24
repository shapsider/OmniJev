"""Weights live inside the repo so a machine that only shares this directory can load them."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models' / 'Qwen3.5-9B'
RUNS = ROOT / 'models' / 'runs'
CHECKPOINT = RUNS / 'qwen35-rlcd-v4'
V2 = RUNS / 'qwen35-rlcd-v2'
V3 = RUNS / 'qwen35-rlcd-v3'
BASE_MODEL_ID = 'Qwen/Qwen3.5-9B'
COMPARE = ROOT / 'models' / 'compare'
NEOHORSE = COMPARE / 'NeoHorse-Jev-4B'
TINNEL_CKPT = COMPARE / 'tinnel-OmniJev'
TINNEL_BASE = COMPARE / 'Qwen3.5-4B'
TINNEL_SRC = COMPARE / 'tinnel-src'
