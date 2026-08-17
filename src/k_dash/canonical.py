"""Args normalization and RFC 8785 BuildKey calculation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

import jsonschema
import rfc8785

from .errors import ContractError
from .model import BuildSpec

MAX_SAFE_INTEGER = (1 << 53) - 1


def loads_no_duplicates(payload: str | bytes, *, stage: str) -> Any:
    def pairs(pairs_value: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs_value:
            if key in output:
                raise ContractError(
                    "duplicate JSON object key",
                    stage=stage,
                    context={"key": key},
                )
            output[key] = value
        return output

    try:
        return json.loads(payload, object_pairs_hook=pairs)
    except json.JSONDecodeError as error:
        raise ContractError("invalid JSON", stage=stage) from error


def _apply_defaults(instance: Any, schema: dict[str, Any]) -> Any:
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key not in instance and "default" in subschema:
                instance[key] = copy.deepcopy(subschema["default"])
            if key in instance:
                instance[key] = _apply_defaults(instance[key], subschema)
    elif isinstance(instance, list):
        item_schema = schema.get("items", {})
        for index, value in enumerate(instance):
            instance[index] = _apply_defaults(value, item_schema)
    return instance


def _validate_i_json(value: Any, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise ContractError(
                "integer is outside the I-JSON exact range",
                stage="args",
                context={"path": path, "value": value},
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0):
            raise ContractError(
                "non-finite and negative-zero numbers are forbidden",
                stage="args",
                context={"path": path},
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_i_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError("object keys must be strings", stage="args", context={"path": path})
            _validate_i_json(item, f"{path}.{key}")
        return
    raise ContractError("value is not JSON-compatible", stage="args", context={"path": path})


def normalize_args(raw: dict[str, Any] | None, schema: dict[str, Any]) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ContractError("kernel args must be a JSON object", stage="args")
    normalized = _apply_defaults(copy.deepcopy(raw), schema)
    try:
        jsonschema.Draft202012Validator(schema).validate(normalized)
    except jsonschema.ValidationError as error:
        raise ContractError(
            error.message,
            stage="args",
            context={"path": ".".join(str(part) for part in error.absolute_path) or "$"},
        ) from error
    _validate_i_json(normalized)
    return normalized


def canonical_json(value: Any) -> bytes:
    _validate_i_json(value)
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError) as error:
        raise ContractError(str(error), stage="canonical-json") from error


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_key(spec: BuildSpec | dict[str, Any]) -> str:
    value = spec.as_dict() if isinstance(spec, BuildSpec) else spec
    return digest_bytes(canonical_json(value))


def build_tag(key: str) -> str:
    if not key.startswith("sha256:") or len(key) != 71:
        raise ContractError("invalid BuildKey", stage="build-key", context={"build_key": key})
    return "build-sha256-" + key.removeprefix("sha256:")
