from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import threading
import time
import uuid
from urllib.parse import urlsplit
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .physics import TASKS
from .policies import DecisionPolicy, configurations, environment_connection
from .runtime import Session, validate_intervention
from .comparison import Comparison, resolve_lanes, resolve_model
from .connection_store import memory_storage

logger = logging.getLogger(__name__)


def _bounded_json(value, limit=8192):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise ValueError("Please provide valid with limited numeric values JSON.") from None
    if len(encoded) > limit:
        raise ValueError(f"JSON Content cannot exceed {limit // 1024} KB.")
    return value


class ScenarioInput(BaseModel):
    scene_config: dict | None = None
    user_context: dict | None = None
    camera_views: list[Literal["external", "wrist"]] | None = None
    intervention: dict | None = None
    shuffle_candidates: bool = False

    @model_validator(mode="after")
    def validate_scenario(self):
        self.intervention = validate_intervention(self.intervention)
        _bounded_json(self.scene_config)
        _bounded_json(self.user_context)
        if self.user_context is not None:
            from .evidence import validate_user_context
            self.user_context = validate_user_context(self.user_context)
        if self.scene_config is not None:
            from .scenarios import validate_scene_config
            self.scene_config = validate_scene_config(self.task, self.scene_config)
        return self


class Setup(ScenarioInput):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    task: Literal["transfer", "stack", "barrier"] = "transfer"
    seed: int = Field(default=0, ge=0, le=99999)
    provider: Literal["baseline", "jev", "minicpm", "local", "chat", "claude", "omnijev", "omni_direct", "omni_reasoning", "omni_adaptive"] = "baseline"
    observation_mode: Literal["privileged", "rgbd", "vision"] = "privileged"
    control_mode: Literal["skills", "incremental"] = "skills"
    preview: bool = True
    threshold: float = Field(default=.55, ge=0, le=1)
    max_cycles: int = Field(default=30, ge=1, le=200)
    speed: float = Field(default=1.5, ge=.25, le=4)
    expected_episode_id: str | None = Field(default=None, min_length=1, max_length=64)
    profile_id: str | None = Field(default=None, min_length=1, max_length=64)


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    threshold: float | None = Field(default=None, ge=0, le=1)
    episode_id: str | None = Field(default=None, min_length=1, max_length=64)


class ComparisonLane(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["baseline", "jev", "minicpm", "local", "chat", "claude", "omnijev", "omni_direct", "omni_reasoning", "omni_adaptive"]
    model: str | None = Field(default=None, min_length=1, max_length=256)
    profile_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("model", mode="before")
    @classmethod
    def strip_model(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class ComparisonSetup(ScenarioInput):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    lanes: list[ComparisonLane] = Field(min_length=2, max_length=3)
    task: Literal["transfer", "stack", "barrier"] = "transfer"
    seed: int = Field(default=0, ge=0, le=99999)
    observation_mode: Literal["privileged", "rgbd", "vision"] = "privileged"
    control_mode: Literal["skills", "incremental"] = "skills"
    preview: bool = True
    threshold: float = Field(default=.55, ge=0, le=1)
    max_cycles: int = Field(default=30, ge=1, le=200)
    speed: float = Field(default=1.5, ge=.25, le=4)
    mode: Literal["sequential", "parallel"] = "sequential"
    expected_comparison_id: str | None = Field(default=None, min_length=1, max_length=64)


class ComparisonControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_id: str = Field(min_length=1, max_length=64)


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["jev", "chat", "local", "claude"]
    url: str = Field(min_length=1, max_length=2048)
    model: str = Field(min_length=1, max_length=256)
    api_key: SecretStr = SecretStr("")
    json_mode: bool = True

    @field_validator("model")
    @classmethod
    def validate_model(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Model name must not be blank")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use an HTTP(S) URL without credentials, query or fragment")
        return value.rstrip("/")


class ModelProfileInput(ConnectionInput):
    id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if not value.strip():
            raise ValueError("Model configuration name cannot be empty.")
        return value.strip()


class DecisionProbe(ComparisonLane):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    observation: dict
    question: str = Field(min_length=1, max_length=4000)
    options: dict[str, str] = Field(min_length=2, max_length=12)

    @field_validator("observation")
    @classmethod
    def validate_observation(cls, value):
        return _bounded_json(value)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value):
        if not value.strip():
            raise ValueError("Decision problem cannot be empty.")
        return value.strip()

    @field_validator("options")
    @classmethod
    def validate_options(cls, value):
        if any(not 1 <= len(key) <= 80 or key != key.strip() or any(ord(char) < 32 for char in key)
               or not description.strip() or len(description) > 1000 for key, description in value.items()):
            raise ValueError("Candidate name needs to be 1–80 visible characters, description needs to be 1–1000 characters.")
        return value


def _connection_settings(value, previous):
    url = value.url
    if value.provider == "jev" and url != "https://api.typesafe.ai/v1/systemone":
        raise HTTPException(422, "TypeSafe Jev uses its official endpoint")
    if value.provider == "chat" and not url.endswith("/chat/completions"):
        url += "/chat/completions"
    if value.provider == "claude" and not url.endswith("/messages"):
        url += "/messages"
    key = value.api_key.get_secret_value().strip()
    if not key and previous.get("url") == url and previous.get("provider", value.provider) == value.provider:
        key = previous.get("key", "")
    if value.provider in {"jev", "claude"} and not key:
        raise HTTPException(422, f"{value.provider} API key is required")
    return {"url": url, "model": value.model, "key": key, "json_mode": value.json_mode}


def _without_keys(value, secrets):
    if isinstance(value, str):
        for key in secrets:
            if key:
                value = value.replace(key, "[Hidden]")
        return value
    if isinstance(value, dict):
        return {_without_keys(key, secrets): _without_keys(item, secrets) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_without_keys(item, secrets) for item in value]
    return value


def _reject_saved_keys(value, secrets):
    encoded = json.dumps(value, ensure_ascii=False)
    if any(key and key in encoded for key in secrets):
        raise HTTPException(422, "Input contains saved API Key, Please remove credentials before submitting.")


def _public_profile(profile):
    return _without_keys({key: profile[key] for key in ("id", "name", "provider", "url", "model", "json_mode")}
                         | {"key_configured": bool(profile["key"])}, [profile["key"]])


def _connection_error_message(exc):
    # Do not include exception text, URLs, headers, or provider response bodies.
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        messages = {
            401: "Authentication failed ( HTTP 401): Please check API Key Is it correct or expired.",
            403: "Access denied ( HTTP 403): Please confirm the account has been API access permission to the selected model",
            404: "Interface or model not found ( HTTP 404): Please check API Address and model name.",
            429: "Request limited ( HTTP 429): Check quota and request frequency, retry later.",
        }
        if status in messages:
            return messages[status]
        if status >= 500:
            return f"Service temporarily unavailable ( HTTP {status}): Please try again later."
        return f"Service refused connection test ( HTTP {status}): Check address, model and API Configuration."
    if isinstance(exc, httpx.TimeoutException):
        return "Connection test timeout: please check network or model service load and retry later."
    if isinstance(exc, httpx.RequestError):
        return "Unable to connect to model service: please check API Address, network, and local services are started."
    if isinstance(exc, (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError)):
        return "Response format does not match decision interface: please check selected interface type, model, and structured output support."
    return "Connection test not completed: please check the model service status and retry."


def _untested_connection():
    return {"status": "untested", "checked_at": None, "model": None, "latency_ms": None,
            "message": "Not tested. Saving configuration will not verify API."}


def _public_model(model, connection, *, required=True):
    if not isinstance(model, str) or not model.strip() or len(model) > 256:
        if required:
            raise ValueError("Invalid model in provider response")
        return None
    key = connection.get("key", "")
    return model.replace(key, "[Hidden]") if key else model


def create_app(store=None):
    @asynccontextmanager
    async def lifespan(app):
        yield
        app.state.session.stop()
        if app.state.comparison is not None:
            app.state.comparison.stop()

    app = FastAPI(title="EmbodiedJev", lifespan=lifespan)
    app.state.session = Session()
    app.state.lock = threading.Lock()
    app.state.persistence_lock = threading.Lock()
    app.state.connections = {}
    app.state.model_profiles = {}
    app.state.connection_storage = {}
    app.state.profile_storage = {}
    app.state.storage = memory_storage()
    app.state.store = store
    if store is not None:
        try:
            restored = store.load()
            app.state.connections = restored["connections"]
            app.state.model_profiles = restored["profiles"]
            app.state.connection_storage = restored["connection_storage"]
            app.state.profile_storage = restored["profile_storage"]
            app.state.storage = restored["storage"]
        except Exception:
            app.state.storage = memory_storage("Unable to recover the system-saved connection, currently using memory mode; no other credentials read, nor plaintext written Key.")
    app.state.verifications = {}
    app.state.connection_test_ids = {}
    app.state.connection_test_slots = threading.BoundedSemaphore(2)
    app.state.comparison = None
    app.state.comparison_lock = threading.Lock()

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(request, exc):
        # Invalid JSON can include credentials or non-finite numbers. Returning
        # Pydantic's raw `input` both exposes those values and can break JSON encoding.
        return JSONResponse(public_result({"detail": [{key: error[key] for key in ("loc", "type", "msg")}
                                                       for error in exc.errors()]}), status_code=422)

    def current_session():
        with app.state.lock:
            return app.state.session

    def current_comparison(comparison_id):
        with app.state.comparison_lock:
            comparison = app.state.comparison
            if comparison is None:
                raise HTTPException(404, "Model comparison not yet created.")
            if comparison.id != comparison_id:
                raise HTTPException(409, "Compare updated, please refresh comparison status before operating.")
            return comparison

    def check_episode(expected, session):
        if expected is not None and expected != session.id:
            logger.info("stale_episode_request episode_id=%s", session.id,
                        extra={"event": "stale_episode_request", "episode_id": session.id})
            raise HTTPException(409, "The experiment has been reset by other pages; please refresh the current experiment state before operating.")

    def connection_snapshot(provider):
        item = app.state.connections.get(provider, environment_connection(provider))
        return {"url": item["url"], "model": item["model"], "key": item.get("key", ""),
                "json_mode": item.get("json_mode", True)}

    def configured_secrets():
        # Caller holds app.state.lock. Inspect only this service's configured values.
        keys = [item.get("key") for item in app.state.connections.values()]
        keys += [item.get("key") for item in app.state.model_profiles.values()]
        keys += [environment_connection(provider).get("key") for provider in ("jev", "chat", "local", "claude")]
        return tuple(sorted({key for key in keys if key}, key=len, reverse=True))

    def public_result(value, extra_secrets=()):
        with app.state.lock:
            secrets = tuple(sorted(set(configured_secrets()) | set(extra_secrets), key=len, reverse=True))
        return _without_keys(value, secrets)

    def persist_configuration(kind, value, provider=None):
        storage = memory_storage()
        if app.state.store is not None:
            try:
                storage = (app.state.store.save_connection(provider, value) if kind == "connection"
                           else app.state.store.save_profile(value))
            except Exception:
                storage = memory_storage("Security storage not completed, this modification retains only memory; not written in plaintext Key, After restart, this change will not be restored.")
        with app.state.lock:
            app.state.storage = storage
            if kind == "connection":
                app.state.connection_storage[provider] = storage
            else:
                app.state.profile_storage[value["id"]] = storage
        return storage

    def verification_snapshot(provider, connection):
        saved = app.state.verifications.get(provider)
        if saved and saved["connection"] == connection:
            return dict(saved["result"])
        return _untested_connection()

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            allowed = {f"http://127.0.0.1:{request.url.port}", f"http://localhost:{request.url.port}"}
            if origin and origin not in allowed:
                return JSONResponse({"detail": "Cross-origin control is disabled"}, status_code=403)
        return await call_next(request)

    @app.get("/api/config")
    def config():
        return {"name": "EmbodiedJev", "chinese_name": "Xingzhi", "version": "0.1.0", "tasks": TASKS,
                "providers": configurations(app.state.connections), "robot": "Franka Panda", "physics": "MuJoCo 3.13"}

    @app.get("/api/connections")
    def connections():
        result = {}
        with app.state.lock:
            for provider in ("jev", "chat", "local", "claude"):
                item = connection_snapshot(provider)
                result[provider] = {"url": item["url"], "model": item["model"],
                                    "key_configured": bool(item["key"]), "json_mode": item["json_mode"],
                                    "storage": app.state.connection_storage.get(provider, memory_storage()),
                                    "verification": verification_snapshot(provider, item)}
        return public_result(result)

    @app.post("/api/connections")
    def save_connection(value: ConnectionInput):
        # Serialize saves without blocking stop/state requests while the OS asks
        # for Keychain permission. This also keeps disk commits in request order.
        with app.state.persistence_lock:
            with app.state.lock:
                previous = connection_snapshot(value.provider)
                updated = _connection_settings(value, previous)
                _reject_saved_keys({"url": updated["url"], "model": updated["model"]},
                                   (*configured_secrets(), updated["key"]))
                if previous != updated:
                    app.state.verifications.pop(value.provider, None)
                    app.state.connection_test_ids[value.provider] = app.state.connection_test_ids.get(value.provider, 0) + 1
                app.state.connections[value.provider] = updated
                verification = verification_snapshot(value.provider, updated)
            storage = persist_configuration("connection", updated, value.provider)
        return public_result({"saved": True, "provider": value.provider, "key_configured": bool(updated["key"]),
                              "verification": verification, "storage": storage})

    @app.get("/api/model-profiles")
    def model_profiles():
        with app.state.lock:
            result = {"profiles": [{**_public_profile(profile), "storage": app.state.profile_storage.get(profile["id"], memory_storage())}
                                    for profile in app.state.model_profiles.values()], "storage": app.state.storage}
        return public_result(result)

    @app.post("/api/model-profiles")
    def save_model_profile(value: ModelProfileInput):
        with app.state.persistence_lock:
            with app.state.lock:
                previous = app.state.model_profiles.get(value.id) if value.id else None
                if value.id and previous is None:
                    raise HTTPException(404, "Model configuration not found, please refresh the configuration list.")
                profile = {**_connection_settings(value, previous or {}), "id": value.id or uuid.uuid4().hex[:12],
                           "name": value.name, "provider": value.provider}
                _reject_saved_keys({key: profile[key] for key in ("url", "model", "name")},
                                   (*configured_secrets(), profile["key"]))
                app.state.model_profiles[profile["id"]] = profile
            storage = persist_configuration("profile", profile)
        return public_result({**_public_profile(profile), "storage": storage})

    @app.post("/api/decision/probe")
    def decision_probe(value: DecisionProbe):
        if not app.state.connection_test_slots.acquire(blocking=False):
            raise HTTPException(429, "Two connection or decision tests are already running; please try again later.", headers={"Retry-After": "1"})
        policy = None
        try:
            with app.state.lock:
                try:
                    selected = resolve_model(value.provider, app.state.connections, model=value.model,
                                             profile_id=value.profile_id, profiles=app.state.model_profiles)
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from None
                secrets = configured_secrets()
                _reject_saved_keys({"observation": value.observation, "question": value.question,
                                    "options": value.options, "model": value.model}, secrets)
            logger.info("decision_probe_started provider=%s", value.provider,
                        extra={"event": "decision_probe_started", "provider": value.provider})
            try:
                policy = DecisionPolicy(value.provider, selected["connection"])
                decision = policy.choose(value.observation, value.question, value.options, next(iter(value.options)), [])
                result = {"provider": value.provider, "profile_id": value.profile_id, "model": policy.model,
                          "decision": decision, "decision_input": policy.last_input,
                          "message": "The rule baseline always selects the first candidate; no model is called and semantics are not verified." if value.provider == "baseline"
                          else "Only candidate decisions were made this time, no robot actions were executed."}
                logger.info("decision_probe_finished provider=%s", value.provider,
                            extra={"event": "decision_probe_finished", "provider": value.provider})
                return public_result(result, secrets)
            except Exception as exc:
                raise HTTPException(502, _connection_error_message(exc).replace("Connection test", "Decision test")) from None
        finally:
            try:
                if policy is not None:
                    policy.close()
            finally:
                app.state.connection_test_slots.release()

    @app.post("/api/presets/validate")
    def validate_preset_input(value: dict):
        from .presets import validate_preset
        try:
            _bounded_json(value, 16384)
            with app.state.lock:
                _reject_saved_keys(value, configured_secrets())
            return public_result(validate_preset(value))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    def run_connection_test(provider):
        with app.state.lock:
            connection = connection_snapshot(provider)
            secrets = configured_secrets()
            test_id = app.state.connection_test_ids.get(provider, 0) + 1
            app.state.connection_test_ids[provider] = test_id
        started = time.perf_counter()
        logger.info("connection_test_started provider=%s", provider,
                    extra={"event": "connection_test_started", "provider": provider})
        message = None
        policy = None
        try:
            if not connection["url"] or not connection["model"] or (provider in {"jev", "claude"} and not connection["key"]):
                message = "Please fill in and save the API address, model, and required API Key before testing the connection."
                raise ValueError("Missing connection configuration")
            policy = DecisionPolicy(provider, connection)
            result = policy.choose({"purpose": "Connection test; no robot command will execute"},
                                   "Choose ready for a connection test", {"ready": "Ready", "hold": "Hold"}, "ready", [])
            model = _without_keys(_public_model(policy.model, connection), secrets)
            latency = result["latency_ms"]
            if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
                raise ValueError("Invalid connection test latency")
            verification = {"status": "passed", "checked_at": datetime.now(timezone.utc).isoformat(),
                            "model": model, "latency_ms": round(latency),
                            "message": "Connection test passed, model returned valid candidate actions; robot did not execute actions."}
        except Exception as exc:
            message = message or _connection_error_message(exc)
            verification = {"status": "failed", "checked_at": datetime.now(timezone.utc).isoformat(),
                            "model": _without_keys(_public_model(connection["model"], connection, required=False), secrets),
                            "latency_ms": round((time.perf_counter() - started) * 1000), "message": message}
        finally:
            if policy is not None:
                policy.close()
        with app.state.lock:
            if app.state.connection_test_ids[provider] != test_id or connection_snapshot(provider) != connection:
                logger.info("connection_test_superseded provider=%s", provider,
                            extra={"event": "connection_test_superseded", "provider": provider})
                raise HTTPException(409, "Configuration or connection test updated, this result discarded, please check current status then retry.")
            app.state.verifications[provider] = {"connection": connection, "result": verification}
        logger.info("connection_test_finished provider=%s status=%s latency_ms=%s",
                    provider, verification["status"], verification["latency_ms"],
                    extra={"event": "connection_test_finished", "provider": provider,
                           "verification_status": verification["status"], "latency_ms": verification["latency_ms"]})
        if verification["status"] == "failed":
            raise HTTPException(502, verification["message"]) from None
        return public_result({"ok": True, "model": verification["model"], "latency_ms": verification["latency_ms"],
                              "verification": verification}, secrets)

    @app.post("/api/connections/{provider}/test")
    def test_connection(provider: Literal["jev", "chat", "local", "claude"]):
        if not app.state.connection_test_slots.acquire(blocking=False):
            logger.info("connection_test_busy provider=%s", provider,
                        extra={"event": "connection_test_busy", "provider": provider})
            raise HTTPException(429, "Two connection tests are currently running, please wait for one to complete before retrying.", headers={"Retry-After": "1"})
        try:
            return run_connection_test(provider)
        finally:
            app.state.connection_test_slots.release()

    @app.get("/api/scene")
    def scene():
        session = current_session()
        with session.lock:
            result = session.world.scene()
        return public_result(result)

    @app.get("/api/state")
    def state():
        return public_result(current_session().snapshot())

    def cached_perception(episode_id, capture_id=None, view=None):
        session = current_session()
        check_episode(episode_id, session)
        if view is not None and hasattr(session, "camera_views") and view not in session.camera_views:
            raise HTTPException(404, "Selected camera view not enabled for this experiment")
        snapshot = session.camera_snapshot()
        if not snapshot:
            raise HTTPException(404, "Current experiment has no camera observations, please enable camera first.")
        if capture_id is not None and str(snapshot["metadata"]["capture_id"]) != capture_id:
            raise HTTPException(409, "Camera frame updated, please read latest observations.")
        return snapshot

    @app.get("/api/perception")
    def perception(episode_id: str = Query(min_length=1, max_length=64),
                   capture_id: str | None = Query(default=None, max_length=64)):
        return public_result(cached_perception(episode_id, capture_id)["metadata"])

    @app.get("/api/perception/{image_name}.png")
    def perception_image(image_name: Literal["rgb", "depth"],
                         episode_id: str = Query(min_length=1, max_length=64),
                         capture_id: str | None = Query(default=None, max_length=64),
                         view: Literal["external", "wrist"] = "external"):
        snapshot = cached_perception(episode_id, capture_id, view)
        views = snapshot.get("views")
        # Legacy single-camera caches predate the views map. An explicit map is
        # authoritative: never substitute its top-level image for a missing view.
        selected = snapshot if views is None and view == "external" else (views or {}).get(view)
        if selected is None:
            raise HTTPException(404, "Perception frame does not have selected camera view")
        data = selected["rgb"] if image_name == "rgb" else selected.get("depth_display", selected["depth"])
        return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.post("/api/reset")
    def reset(setup: Setup):
        with app.state.lock:
            previous = app.state.session
            check_episode(setup.expected_episode_id, previous)
            _reject_saved_keys({"scene_config": setup.scene_config, "user_context": setup.user_context}, configured_secrets())
            try:
                selected = resolve_model(setup.provider, app.state.connections, profile_id=setup.profile_id,
                                         profiles=app.state.model_profiles)
                new = Session(**setup.model_dump(exclude={"expected_episode_id", "profile_id"}), connection=selected["connection"])
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            previous.stop()
            app.state.session = new
        logger.info("episode_reset episode_id=%s previous_episode_id=%s provider=%s task=%s",
                    new.id, previous.id, setup.provider, setup.task,
                    extra={"event": "episode_reset", "episode_id": new.id, "previous_episode_id": previous.id,
                           "provider": setup.provider, "task": setup.task})
        return public_result(new.snapshot())

    @app.post("/api/control/{action}")
    def control(action: Literal["start", "step", "pause", "stop"], options: Control = Control()):
        try:
            with app.state.lock:
                session = app.state.session
                check_episode(options.episode_id, session)
                if action in {"start", "step"}:
                    session.start(single_step=action == "step", threshold=options.threshold)
                else:
                    getattr(session, action)()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        logger.info("episode_control episode_id=%s action=%s", session.id, action,
                    extra={"event": "episode_control", "episode_id": session.id, "action": action})
        return public_result(session.snapshot())

    @app.get("/api/replay/{index}")
    def replay(index: int):
        session = current_session()
        try:
            result = session.replay_frame(index)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return public_result(result)

    @app.get("/api/export")
    def export():
        session = current_session()
        return JSONResponse(public_result(session.export()), headers={"Content-Disposition": f'attachment; filename="embodied-jev-{session.id}.json"'})

    @app.get("/api/export/cameras.zip")
    def export_cameras(episode_id: str = Query(min_length=1, max_length=64)):
        session = current_session()
        check_episode(episode_id, session)
        return Response(session.camera_archive(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{session.id}-cameras.zip"',
                                 "Cache-Control": "no-store"})

    @app.get("/api/comparison")
    def comparison_state():
        with app.state.comparison_lock:
            comparison = app.state.comparison
        return public_result(comparison.snapshot()) if comparison is not None else {"id": None, "status": "empty", "lanes": []}

    @app.post("/api/comparison")
    def create_comparison(setup: ComparisonSetup):
        with app.state.lock:
            saved_connections = {provider: dict(value) for provider, value in app.state.connections.items()}
            profiles = {profile_id: dict(value) for profile_id, value in app.state.model_profiles.items()}
            secrets = configured_secrets()
            _reject_saved_keys({"scene_config": setup.scene_config, "user_context": setup.user_context,
                                "models": [lane.model for lane in setup.lanes]}, secrets)
        try:
            lanes = resolve_lanes([lane.model_dump() for lane in setup.lanes], saved_connections, profiles)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        with app.state.comparison_lock:
            previous = app.state.comparison
            expected = setup.expected_comparison_id
            if (previous is not None and expected != previous.id) or (previous is None and expected is not None):
                raise HTTPException(409, "Comparison updated, please refresh comparison status before creating.")
            if previous is not None:
                previous.stop()
                if previous.has_live_workers():
                    raise HTTPException(409, "Comparison stopped, still waiting for previous request to end, please try later.")
            try:
                comparison = Comparison(lanes, **setup.model_dump(exclude={"lanes", "expected_comparison_id"}), secrets=secrets)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            app.state.comparison = comparison
        return public_result(comparison.snapshot())

    @app.post("/api/comparison/control/{action}")
    def comparison_control(action: Literal["start", "pause", "stop"], options: ComparisonControl):
        with app.state.comparison_lock:
            comparison = app.state.comparison
            if comparison is None:
                raise HTTPException(404, "Model comparison not yet created.")
            if comparison.id != options.comparison_id:
                raise HTTPException(409, "Compare updated, please refresh comparison status before operating.")
            try:
                getattr(comparison, action)()
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
        return public_result(comparison.snapshot())

    @app.get("/api/comparison/scene/{lane_id}")
    def comparison_scene(lane_id: str, comparison_id: str = Query(min_length=1, max_length=64)):
        comparison = current_comparison(comparison_id)
        try:
            result = comparison.scene(lane_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None
        return public_result(result)

    @app.get("/api/comparison/replay")
    def comparison_replay(time: float = Query(ge=0, allow_inf_nan=False), comparison_id: str = Query(min_length=1, max_length=64)):
        comparison = current_comparison(comparison_id)
        try:
            result = comparison.replay(time)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return public_result(result)

    @app.get("/api/comparison/export")
    def comparison_export(comparison_id: str = Query(min_length=1, max_length=64)):
        comparison = current_comparison(comparison_id)
        return JSONResponse(public_result(comparison.export()), headers={
            "Content-Disposition": f'attachment; filename="embodied-jev-comparison-{comparison.id}.json"'})

    from omnijev.embodied_web import install_routes
    install_routes(app)
    web = Path(__file__).parent / "web"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="workbench")
    return app
