import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from znn.model.nom.account_block import AccountBlock


def test_complete_account_block_wire_round_trip():
    configured = os.environ.get("ZNN_SPEC_ROOT")
    root = Path(configured) if configured else Path(__file__).resolve().parents[4] / "znn-ts-sdk-spec"
    if not root.exists():
        pytest.skip("stable specification checkout is not available")
    cases = json.loads((root / "conformance/vectors/models.json").read_text())["cases"]
    fixture = next(case for case in cases if case["input"]["model"] == "AccountBlock")
    value = deepcopy(fixture["input"]["json"])
    value["nonce"] = "0000000000000000"
    value["momentumAcknowledged"] = {"hash": "0" * 64, "height": 0}
    value.pop("token")
    value.pop("confirmationDetail")
    value.pop("pairedAccountBlock")
    block = AccountBlock.from_json(value)
    assert isinstance(block.amount, int)
    assert block.to_json() == value


def test_account_block_rejects_invalid_nonce_at_parse_boundary():
    value = AccountBlock().to_json()
    value["nonce"] = "fixture"
    with pytest.raises(ValueError, match="nonce"):
        AccountBlock.from_json(value)


def test_account_block_accepts_padded_and_unpadded_standard_base64():
    value = AccountBlock().to_json()
    value["data"] = "SGVsbG8"
    value["publicKey"] = "AA"
    value["signature"] = "AQI"

    block = AccountBlock.from_json(value)

    assert block.data == b"Hello"
    assert block.public_key == b"\x00"
    assert block.signature == b"\x01\x02"
    assert block.to_json()["data"] == "SGVsbG8="


@pytest.mark.parametrize("invalid", ["A", "AA=", "AA===", "AA-_", "AAAA="])
def test_account_block_rejects_malformed_standard_base64(invalid):
    value = AccountBlock().to_json()
    value["data"] = invalid
    with pytest.raises(ValueError, match="base64"):
        AccountBlock.from_json(value)
