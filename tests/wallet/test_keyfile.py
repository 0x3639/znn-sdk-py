import json
import os
from pathlib import Path

import pytest

from znn.wallet.keyfile import KeyFileError, decrypt, encrypt, needs_upgrade
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


def test_keyfile_custom_kdf_configuration_and_required_fields():
    store = KeyStore.from_entropy("24" * 32)
    target = {"timeCost": 2, "memoryCost": 8192, "hashLength": 32, "parallelism": 1}
    document = encrypt(store, "password", timestamp=1, kdf_config=target)
    assert all(document["crypto"]["argon2Params"][key] == value for key, value in target.items())
    assert needs_upgrade(document, target) is False
    assert decrypt(document, "password").entropy == store.entropy

    for path in (("timestamp",), ("crypto", "kdf")):
        malformed = json.loads(json.dumps(document))
        parent = malformed
        for key in path[:-1]:
            parent = parent[key]
        parent.pop(path[-1])
        with pytest.raises(KeyFileError, match="Missing required"):
            decrypt(malformed, "password")

    malformed = json.loads(json.dumps(document))
    malformed["crypto"]["nonce"] = malformed["crypto"]["nonce"].upper()
    with pytest.raises(KeyFileError, match="lowercase hex"):
        decrypt(malformed, "password")

    malformed = json.loads(json.dumps(document))
    malformed["crypto"]["argon2Params"]["timeCost"] = True
    with pytest.raises(KeyFileError, match="positive integer"):
        decrypt(malformed, "password")


def test_legacy_keyfile_vectors():
    configured = os.environ.get("ZNN_SPEC_ROOT")
    root = Path(configured) if configured else Path(__file__).resolve().parents[3] / "znn-ts-sdk-spec"
    if not root.exists():
        pytest.skip("stable specification checkout is not available")
    vectors = json.loads((root / "conformance/vectors/keyfile.json").read_text())
    for case in vectors["cases"]:
        store = decrypt(case["input"]["keyFile"], case["input"]["password"])
        assert store.entropy == case["expected"]["entropyHex"]
        assert needs_upgrade(case["input"]["keyFile"])


@pytest.mark.parametrize(
    "document",
    [
        {"version": 1, "crypto": {"cipherName": "aes-256-gcm", "argon2Params": {}}},
        {"version": 1, "crypto": {"cipherName": "aes-256-gcm", "argon2Params": {"salt": "xx"}, "nonce": "00", "cipherData": "00"}},
    ],
)
def test_malformed_keyfiles_raise_keyfile_error(document):
    with pytest.raises(KeyFileError):
        decrypt(document, "password")
