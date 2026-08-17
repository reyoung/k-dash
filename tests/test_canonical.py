from __future__ import annotations

import pytest
import json
from pathlib import Path

from k_dash.canonical import build_key, build_tag, canonical_json, loads_no_duplicates, normalize_args
from k_dash.errors import ContractError
from k_dash.model import BuildSpec


SCHEMA = {
    "type": "object",
    "properties": {
        "block_size": {"type": "integer", "default": 256},
        "nested": {
            "type": "object",
            "default": {},
            "properties": {"enabled": {"type": "boolean", "default": True}},
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


def test_args_defaults_and_stable_build_key() -> None:
    args = normalize_args({}, SCHEMA)
    assert args == {"block_size": 256, "nested": {"enabled": True}}
    spec = BuildSpec("sha256:" + "0" * 64, args, {"cc": "sm_90a"})
    key = build_key(spec)
    assert key == "sha256:8c41ffc6d344a36a7effed9f7f6196ccf38784789b705360f1a384fda0d107eb"
    assert build_tag(key) == "build-sha256-" + key.split(":", 1)[1]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.0, 2**53])
def test_i_json_rejections(value: object) -> None:
    with pytest.raises(ContractError):
        canonical_json({"bad": value})


def test_unknown_args_fail() -> None:
    with pytest.raises(ContractError):
        normalize_args({"other": 1}, SCHEMA)


def test_duplicate_json_keys_fail() -> None:
    with pytest.raises(ContractError, match="duplicate JSON object key"):
        loads_no_duplicates('{"block_size":128,"block_size":256}', stage="test")


def test_cross_language_buildspec_golden_vector() -> None:
    vector = json.loads((Path(__file__).parent / "golden/buildspec-v1.json").read_text())
    assert canonical_json(vector["buildspec"]).decode() == vector["canonical_json"]
    assert build_key(vector["buildspec"]) == vector["build_key"]
