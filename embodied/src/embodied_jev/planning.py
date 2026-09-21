from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .physics import TRAVEL_Z, RobotWorld

PHASES = {
    "approach": "Move above object", "descend": "Lower to align", "grasp": "Close the gripper",
    "lift": "Lift object", "carry": "Move toward target", "lower": "Lower to place",
    "release": "Release the gripper", "withdraw": "Withdraw upward", "recover": "Open and retry", "finish": "Complete",
}

PHASE_GUIDANCE = {
    "approach": "Move the open gripper to 0.14 m above the object, aligned in XY.",
    "descend": "Move the open gripper down to the object's height, ready to grasp it.",
    "grasp": "Close the fingers around the object at the current position.",
    "lift": "Raise the held object to the travel height, keeping the same XY position.",
    "carry": "Move the held object above the destination at travel height.",
    "lower": "Lower the held object onto the destination, keeping the fingers closed.",
    "release": "Open the fingers to release the object onto its destination support.",
    "withdraw": "Raise the empty open gripper away from the placed object.",
    "recover": "Open the empty fingers after an unsuccessful grasp.",
    "finish": "Finish the task after physical success has been verified.",
}


def eligible_phases(world: RobotWorld, observation=None):
    s = world.observe() if observation is None else observation
    p, cube, target = (np.asarray(s[key], dtype=float) for key in ("tcp", "object", "destination"))
    closed = s["gripper"] == "closed"
    travel_z = s.get("relative_geometry", {}).get("travel_tcp_height_m", TRAVEL_Z)
    near_destination = np.linalg.norm(cube[:2] - target[:2]) < .025
    if s["success"]:
        return ["finish"]
    if not closed and near_destination and s["support_contact"]:
        return ["withdraw"]
    if s["held"]:
        if np.linalg.norm(p[:2] - target[:2]) < .02:
            return ["lower", "release"] if abs(cube[2] - target[2]) < .012 else ["lower", "carry"]
        if cube[2] < travel_z - .045:
            return ["lift"]
        return ["carry", "lift"]
    if closed:
        return ["recover", "grasp"]
    if np.linalg.norm(p[:2] - cube[:2]) > .007:
        return ["approach"]
    if abs(p[2] - cube[2]) > .006:
        return ["descend", "approach"]
    return ["grasp", "approach"]


def baseline_phase(world, observation=None):
    s = world.observe() if observation is None else observation
    eligible = eligible_phases(world, s)
    if "release" in eligible and abs(s["object"][2] - s["destination"][2]) < .012:
        return "release"
    return eligible[0]


def phase_options(world, phases, observation=None):
    """Describe planned effects without recommending or dropping any offered phase."""
    options = {}
    for phase in phases:
        option = candidates(world, phase, preview=False, observation=observation)[0]
        position = world.position if observation is None else np.asarray(observation["tcp"])
        delta = np.asarray(option.target) - position
        moves = []
        for axis, value in zip(("X", "Y", "Z"), delta):
            if abs(value) >= .002:
                moves.append(f"{axis} {value:+.3f} m")
        motion = ", ".join(moves) if moves else "no TCP displacement"
        fingers = option.gripper or "unchanged"
        options[phase] = f"{PHASE_GUIDANCE[phase]} Planned change: {motion}; fingers {fingers}."
    return options


@dataclass
class Candidate:
    id: str
    label: str
    phase: str
    target: list[float] | None
    gripper: str | None
    seconds: float
    admitted: bool = True
    rejection: str | None = None
    preview: dict | None = None

    def serialise(self):
        return asdict(self)


def candidates(world, phase, preview=True, observation=None):
    state = world.observe() if observation is None else observation
    p, cube, dest = (np.asarray(state[key], dtype=float) for key in ("tcp", "object", "destination"))
    travel_z = float(state.get("relative_geometry", {}).get("travel_tcp_height_m", TRAVEL_Z))
    if not np.isfinite(travel_z) or not .02 <= travel_z <= .42:
        raise ValueError("Safety transfer height in observation exceeds workspace")
    target, grip, duration = p.copy(), None, .8
    if phase == "approach":
        target = cube + [0, 0, .14]
        grip = "open"
    elif phase == "descend":
        target = cube + [0, 0, .001]
    elif phase == "grasp":
        grip, duration = "close", .65
    elif phase == "lift":
        target = np.r_[p[:2], travel_z]
        duration = 1.1
    elif phase == "carry":
        target = np.r_[dest[:2] + (p - cube)[:2], travel_z]
        duration = 1.6
    elif phase == "lower":
        target = dest + (p - cube) + [0, 0, .002]
        duration = 1.2
    elif phase in {"release", "recover"}:
        grip, duration = "open", .8
    elif phase == "withdraw":
        target = np.r_[p[:2], travel_z]
        duration = 1.0
    elif phase != "finish":
        raise ValueError("Unknown phase")
    result = [Candidate("direct", PHASES[phase], phase, target.tolist(), grip, duration)]
    if np.linalg.norm(target - p) > .03:
        result.append(Candidate("gentle", "Decelerated execution", phase, target.tolist(), grip, duration * 1.5))
    result.append(Candidate("hold", "Maintain current pose", phase, p.tolist(), None, .3))
    if preview:
        for option in result:
            shadow = world.clone()
            before_bad = shadow.unsafe_contacts
            initial_z = shadow.cube[2]
            try:
                for _ in shadow.motion(option.target, option.gripper, option.seconds, emit=False):
                    pass
                state = shadow.observe()
                option.preview = {"tcp": state["tcp"], "object": state["object"], "held": state["held"],
                                  "support_contact": state["support_contact"],
                                  "target_error_m": round(float(np.linalg.norm(shadow.cube - shadow.target)), 4)}
                if shadow.unsafe_contacts > before_bad:
                    option.admitted, option.rejection = False, "Preview detected contact between the robotic arm and the tabletop or obstacle"
                elif phase in {"lift", "carry"} and (observation or world.observe())["held"] and not state["held"]:
                    option.admitted, option.rejection = False, "Preview lost bilateral grasp contact"
                elif phase == "carry" and shadow.cube[2] < initial_z - .045:
                    option.admitted, option.rejection = False, "Preview object falling"
            except (ValueError, RuntimeError) as exc:
                option.admitted, option.rejection = False, str(exc)
            if observation is not None and observation.get("perception"):
                # This remains an explicit simulator safety filter. Do not give
                # visual policies the oracle's predicted positions or goal error.
                option.preview = {"source": "simulator_safety_filter", "safe": option.admitted}
    return result
