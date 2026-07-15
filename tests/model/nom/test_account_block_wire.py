import json
from pathlib import Path

from znn.model.nom.account_block import AccountBlock


def test_complete_account_block_wire_round_trip():
    root = Path(__file__).resolve().parents[4] / "znn-ts-sdk-spec"
    if not root.exists():
        return
    cases = json.loads((root / "conformance/vectors/models.json").read_text())["cases"]
    fixture = next(case for case in cases if case["input"]["model"] == "AccountBlock")
    block = AccountBlock.from_json(fixture["input"]["json"])
    assert isinstance(block.amount, int)
    assert block.to_json() == fixture["expected"]
