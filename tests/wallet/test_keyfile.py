import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

import znn.wallet.keyfile as keyfile
from znn.wallet.keyfile import KeyFile, KeyFileError, decrypt, encrypt, needs_upgrade
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


def test_keyfile_validation_matrix_and_facade_without_expensive_kdf(monkeypatch):
    monkeypatch.setattr(keyfile, "_argon2", lambda *_args: b"k" * 32)
    monkeypatch.setattr(keyfile.secrets, "token_bytes", lambda size: bytes(range(size)))
    monkeypatch.setattr(keyfile.time, "time", lambda: 123)
    store = KeyStore.from_entropy("5a" * 32)
    facade = KeyFile.set_password("password")
    document = facade.encrypt(store)
    assert document["timestamp"] == 123
    assert facade.decrypt(document).entropy == store.entropy
    assert facade.needs_upgrade(document) is False

    invalid_configs = [
        "not-an-object",
        {"future": 1},
        {"timeCost": True},
        {"timeCost": 0},
        {"hashLength": 16},
    ]
    for config in invalid_configs:
        with pytest.raises(KeyFileError):
            encrypt(store, "password", kdf_config=config)

    for value in (None, []):
        with pytest.raises(KeyFileError, match="JSON object"):
            needs_upgrade(value)
    for field, value, message in [
        ("crypto", "bad", "crypto"),
        ("argon2Params", "bad", "argon2Params"),
    ]:
        malformed = deepcopy(document)
        if field == "crypto":
            malformed[field] = value
        else:
            malformed["crypto"][field] = value
        with pytest.raises(KeyFileError, match=message):
            needs_upgrade(malformed)
    legacy = deepcopy(document)
    legacy["crypto"]["argon2Params"].pop("timeCost")
    assert needs_upgrade(legacy)
    malformed = deepcopy(document)
    malformed["crypto"]["argon2Params"]["timeCost"] = "invalid"
    assert needs_upgrade(malformed)

    for value in (None, 1):
        with pytest.raises(KeyFileError, match="password"):
            decrypt(document, value)
    with pytest.raises(KeyFileError, match="JSON object"):
        decrypt([], "password")
    with pytest.raises(KeyFileError, match="KeyStore"):
        encrypt(object(), "password")
    with pytest.raises(KeyFileError, match="password"):
        encrypt(store, None)
    for timestamp in (-1, True, "1"):
        with pytest.raises(KeyFileError, match="timestamp"):
            encrypt(store, "password", timestamp=timestamp)

    mutations = [
        (lambda item: item.update(version=2), "version"),
        (lambda item: item.update(baseAddress=1), "baseAddress"),
        (lambda item: item.update(timestamp=-1), "timestamp"),
        (lambda item: item.update(crypto="bad"), "crypto"),
        (lambda item: item["crypto"].update(cipherName="future"), "cipher"),
        (lambda item: item["crypto"].update(kdf="future"), "KDF"),
        (lambda item: item["crypto"].update(argon2Params="bad"), "argon2Params"),
        (lambda item: item["crypto"]["argon2Params"].pop("salt"), "cryptographic"),
        (lambda item: item["crypto"].update(nonce=1), "cryptographic"),
        (lambda item: item["crypto"].update(nonce="00"), "lowercase hex"),
        (lambda item: item["crypto"].update(nonce="0x0"), "lowercase hex"),
        (lambda item: item["crypto"].update(nonce="0xgg"), "hexadecimal"),
        (lambda item: item["crypto"].update(nonce="0x00"), "length"),
        (
            lambda item: item["crypto"]["argon2Params"].update(hashLength=16),
            "32-byte",
        ),
    ]
    for mutate, message in mutations:
        malformed = deepcopy(document)
        mutate(malformed)
        with pytest.raises(KeyFileError, match=message):
            decrypt(malformed, "password")

    malformed = deepcopy(document)
    malformed["crypto"]["argon2Params"]["parallelism"] = False
    with pytest.raises(KeyFileError, match="positive integer"):
        decrypt(malformed, "password")

    corrupted = deepcopy(document)
    payload = corrupted["crypto"]["cipherData"]
    corrupted["crypto"]["cipherData"] = payload[:-2] + ("00" if payload[-2:] != "00" else "01")
    with pytest.raises(KeyFileError, match="password or corrupted"):
        decrypt(corrupted, "password")

    wrong_address = deepcopy(document)
    wrong_address["baseAddress"] = str(KeyStore.from_entropy("6b" * 32).get_key_pair().address)
    with pytest.raises(KeyFileError, match="baseAddress"):
        decrypt(wrong_address, "password")

    monkeypatch.setattr(
        keyfile,
        "_argon2",
        lambda *_args: (_ for _ in ()).throw(ValueError("bad parameters")),
    )
    with pytest.raises(KeyFileError, match="Argon2"):
        decrypt(document, "password")
