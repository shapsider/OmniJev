"""Portable task/scene presets contain data, never executable plugins or credentials."""
import json
from pathlib import Path

from .evidence import reject_credential_fields, validate_user_context
from .scenarios import validate_scene_config


def validate_preset(value):
    reject_credential_fields(value)
    allowed = {"format", "name", "task", "scene_config", "user_context"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Preset can only contain format, name, task, scene_config, user_context")
    if value.get("format") != "embodied-jev-preset-v1":
        raise ValueError("Preset format should be embodied-jev-preset-v1")
    name = value.get("name", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Preset name must be 1–80 characters")
    task = value.get("task")
    if task not in {"transfer", "stack", "barrier"}:
        raise ValueError("Please select existing physical task template; new task types require code adaptation")
    return {"format": value["format"], "name": name.strip(), "task": task,
            "scene_config": validate_scene_config(task, value.get("scene_config")),
            "user_context": validate_user_context(value.get("user_context"))}


def load_preset(path):
    content = Path(path).read_text(encoding="utf-8")
    if len(content.encode("utf-8")) > 16384:
        raise ValueError("Preset file cannot exceed 16 KB")
    return validate_preset(json.loads(content))
