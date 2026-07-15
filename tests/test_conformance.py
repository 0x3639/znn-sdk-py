import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from znn.amount import from_base_units, to_base_units
from znn.conformance import dispatch, run
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard
from znn.model.models import WIRE_SCHEMAS, wire_model_round_trip
from znn.pow import verify


def test_primitive_rejection_boundaries():
    with pytest.raises(ValueError):
        Address.from_core(bytes(19))
    with pytest.raises(ValueError):
        Hash(bytes(31))
    with pytest.raises(ValueError):
        TokenStandard.from_core(bytes(9))
    with pytest.raises(ValueError):
        HashHeight(Hash(bytes(32)), -1)
    with pytest.raises(ValueError):
        HashHeight(Hash(bytes(32)), 1 << 64)


def test_amounts_and_pow_are_exact():
    assert to_base_units("123.456", 2) == 12345
    assert to_base_units("-123.456", 2) == -12345
    assert from_base_units(1, 8) == "0.00000001"
    assert verify("22" * 32, 10, "dd2ecc1761c4f332")


def test_complete_portable_vector_corpus():
    configured = os.environ.get("ZNN_SPEC_ROOT")
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "zenon-sdk-spec"
    vectors = root / "conformance" / "vectors"
    if not vectors.exists():
        pytest.skip("stable specification checkout is not available")
    report = run(vectors)
    expected = {}
    for path in vectors.glob("*.json"):
        for case in json.loads(path.read_text())["cases"]:
            expected[case["id"]] = case["expected"]
    assert report["complete"] is True
    assert len(report["results"]) == 764
    errors = [item for item in report["results"] if "error" in item]
    if errors and all("PermissionError" in item["error"] for item in errors):
        pytest.skip("sandbox does not permit binding the live localhost transport fixture")
    assert not errors
    assert not [item for item in report["results"] if item["actual"] != expected[item["id"]]]


def test_non_transport_vectors_are_independently_dispatched():
    configured = os.environ.get("ZNN_SPEC_ROOT")
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "zenon-sdk-spec"
    vectors = root / "conformance" / "vectors"
    if not vectors.exists():
        pytest.skip("stable specification checkout is not available")
    live = {"transport.publish-null", "transport.pagination-error", "transport.reconnect"}
    for path in vectors.glob("*.json"):
        for case in json.loads(path.read_text())["cases"]:
            if case["operation"] not in live:
                assert dispatch(case) == case["expected"], case["id"]


def test_model_schema_rejects_every_removable_required_wire_field():
    configured = os.environ.get("ZNN_SPEC_ROOT")
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "zenon-sdk-spec"
    path = root / "conformance/vectors/models.json"
    if not path.exists():
        pytest.skip("stable specification checkout is not available")

    checked = 0
    for case in json.loads(path.read_text())["cases"]:
        name = case["input"]["model"]
        fields = WIRE_SCHEMAS[name]
        if name == "AccountBlock":
            fields = WIRE_SCHEMAS["AccountBlockTemplate"] + fields
        for field in fields:
            wire_path, required = field[1], field[5]
            if not required or not wire_path:
                continue
            value = deepcopy(case["input"]["json"])
            current = value
            try:
                parts = wire_path.split(".")
                for part in parts[:-1]:
                    current = current[part]
                current.pop(parts[-1])
            except (KeyError, TypeError):
                continue
            checked += 1
            with pytest.raises((TypeError, ValueError), match="Missing required"):
                wire_model_round_trip(name, value)
    assert checked == 305
