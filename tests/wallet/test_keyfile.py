import json
from pathlib import Path

from znn.wallet.keyfile import decrypt, encrypt, needs_upgrade
from znn.wallet.keystore import KeyStore


def test_keyfile_round_trip_and_upgrade_fields():
    store = KeyStore.from_entropy("42" * 32)
    document = encrypt(store, "password", timestamp=1)
    assert needs_upgrade(document) is False
    restored = decrypt(document, "password")
    assert restored.entropy == store.entropy
    assert str(restored.get_key_pair().address) == document["baseAddress"]
    assert set(document["crypto"]["argon2Params"]) == {
        "salt", "timeCost", "memoryCost", "hashLength", "parallelism"
    }


def test_legacy_keyfile_vectors():
    root = Path(__file__).resolve().parents[3] / "znn-ts-sdk-spec"
    if not root.exists():
        return
    vectors = json.loads((root / "conformance/vectors/keyfile.json").read_text())
    for case in vectors["cases"]:
        store = decrypt(case["input"]["keyFile"], case["input"]["password"])
        assert store.entropy == case["expected"]["entropyHex"]
        assert needs_upgrade(case["input"]["keyFile"])
