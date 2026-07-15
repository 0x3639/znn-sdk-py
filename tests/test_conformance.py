import json
import os
from pathlib import Path

import pytest

from znn.amount import from_base_units, to_base_units
from znn.conformance import run
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard
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
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "znn-ts-sdk-spec"
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
    assert not [item for item in report["results"] if "error" in item]
    assert not [item for item in report["results"] if item["actual"] != expected[item["id"]]]
