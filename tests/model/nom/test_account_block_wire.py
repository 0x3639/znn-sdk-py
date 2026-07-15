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


def test_account_block_validation_and_nested_response_matrix():
    value = AccountBlock().to_json()
    with pytest.raises(TypeError, match="object"):
        AccountBlock.from_json([])
    incomplete = dict(value)
    incomplete.pop("height")
    with pytest.raises(ValueError, match="Missing required"):
        AccountBlock.from_json(incomplete)

    for field, invalid, message in [
        ("height", True, "integer"),
        ("height", -1, "unsigned"),
        ("amount", "01", "canonical"),
        ("nonce", "AA" * 8, "lowercase"),
        ("nonce", "g" * 16, "hexadecimal"),
    ]:
        malformed = dict(value)
        malformed[field] = invalid
        with pytest.raises((TypeError, ValueError), match=message):
            AccountBlock.from_json(malformed)

    response = dict(value)
    response.update({
        "descendantBlocks": [],
        "basePlasma": 1,
        "usedPlasma": 2,
        "changesHash": "0" * 64,
        "pairedAccountBlock": dict(value),
    })
    block = AccountBlock.from_json(response, require_response=False)
    assert isinstance(block._extra_fields["pairedAccountBlock"], AccountBlock)
    assert block.to_json() == response

    for field, invalid, message in [
        ("descendantBlocks", {}, "array"),
        ("basePlasma", True, "unsigned"),
        ("changesHash", 1, "hash string"),
        ("token", [], "object"),
        ("confirmationDetail", [], "object"),
        ("pairedAccountBlock", [], "object"),
    ]:
        malformed = dict(response)
        malformed[field] = invalid
        with pytest.raises((TypeError, ValueError), match=message):
            AccountBlock.from_json(malformed)

    receive = AccountBlock.receive(AccountBlock().hash)
    assert receive.block_type == 3
    invalid_nonce = AccountBlock()
    invalid_nonce.nonce = b"short"
    with pytest.raises(ValueError, match="nonce"):
        invalid_nonce.get_hash()
    invalid_amount = AccountBlock()
    invalid_amount.amount = -1
    with pytest.raises(ValueError, match="amount"):
        invalid_amount.get_hash()
