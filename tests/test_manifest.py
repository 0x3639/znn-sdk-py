import importlib
import json
import os
from pathlib import Path

import pytest


def resolve(symbol):
    parts = symbol.split(".")
    for index in range(len(parts), 0, -1):
        try:
            value = importlib.import_module(".".join(parts[:index]))
        except ImportError:
            continue
        for part in parts[index:]:
            value = getattr(value, part)
        return value
    raise ImportError(symbol)


def test_every_manifest_symbol_resolves():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "conformance/manifest.json").read_text())
    failures = {}
    for capability, record in manifest["capabilities"].items():
        try:
            resolve(record["symbol"])
        except (ImportError, AttributeError) as error:
            failures[capability] = str(error)
    assert failures == {}


def test_generated_inventories_match_pinned_spec(tmp_path):
    configured = os.environ.get("ZNN_SPEC_ROOT")
    spec = Path(configured) if configured else Path(__file__).resolve().parents[2] / "zenon-sdk-spec"
    if not spec.exists():
        pytest.skip("stable specification checkout is not available")

    from tools.generate_models import generate as generate_models
    from tools.generate_rpc_responses import generate as generate_responses

    assert generate_models(spec / "spec/models.json") == (
        Path(__file__).resolve().parents[1] / "znn/model/models.py"
    ).read_text()
    assert generate_responses(spec / "spec/rpc.json") == (
        Path(__file__).resolve().parents[1] / "znn/api/_response.py"
    ).read_text()
